from __future__ import annotations

import html
import re
import time
from math import sqrt

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ElasticsearchException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from api.core.config import get_settings
from api.db.models import Company, Document, Embedding, Event, PressReleaseSection, Slide, Turn
from api.schemas.contracts import SearchRequest, SearchResponse, SearchResult
from services.embedding_service import EmbeddingGenerator


class SearchService:
    def __init__(self) -> None:
        settings = get_settings()
        self.index = settings.es_index_name
        self.es = Elasticsearch(settings.es_host, request_timeout=3)
        self.embeddings = EmbeddingGenerator()

    def keyword(self, db: Session, request: SearchRequest) -> SearchResponse:
        start = time.perf_counter()
        try:
            return self._keyword_es(request, start)
        except ElasticsearchException:
            return self._keyword_db(db, request, start)

    def semantic(self, db: Session, request: SearchRequest) -> SearchResponse:
        start = time.perf_counter()
        query_vector = self.embeddings.embed(request.query)
        stmt = select(Embedding, Company.name).join(Company, Company.id == Embedding.company_id)
        if request.companies:
            stmt = stmt.where(Embedding.company_id.in_(request.companies))
        if request.document_types:
            stmt = stmt.where(Embedding.document_type.in_(request.document_types))
        rows = db.execute(stmt).all()
        scored = sorted(((self._cosine(query_vector, emb.embedding or []), emb, company_name) for emb, company_name in rows), reverse=True, key=lambda item: item[0])
        offset = (request.page - 1) * request.page_size
        results = [self._embedding_result(db, emb, company_name, score) for score, emb, company_name in scored[offset : offset + request.page_size]]
        return SearchResponse(total=len(scored), page=request.page, results=results, took_ms=int((time.perf_counter() - start) * 1000))

    def _keyword_es(self, request: SearchRequest, start: float) -> SearchResponse:
        filters = []
        if request.companies:
            filters.append({"terms": {"company_id": request.companies}})
        if request.document_types:
            filters.append({"terms": {"document_type": request.document_types}})
        if request.speaker_roles:
            filters.append({"terms": {"speaker_role": request.speaker_roles}})
        body = {
            "query": {"bool": {"must": [{"match": {"text": request.query}}], "filter": filters}},
            "from": (request.page - 1) * request.page_size,
            "size": request.page_size,
            "highlight": {"fields": {"text": {"fragment_size": 300, "number_of_fragments": 1, "pre_tags": ["<mark>"], "post_tags": ["</mark>"]}}},
        }
        response = self.es.search(index=self.index, **body)
        total = response["hits"]["total"]["value"]
        results = []
        for hit in response["hits"]["hits"]:
            src = hit["_source"]
            source_id = src.get("turn_id") or src.get("slide_id") or src.get("section_id")
            content_type = "turn" if src.get("turn_id") else "slide" if src.get("slide_id") else "section"
            results.append(
                SearchResult(
                    id=source_id,
                    content_type=content_type,
                    company_id=src["company_id"],
                    company_name=src["company_name"],
                    quarter=src.get("quarter"),
                    event_date=src.get("event_date"),
                    document_type=src["document_type"],
                    speaker_name=src.get("speaker_name"),
                    speaker_role=src.get("speaker_role"),
                    snippet=(hit.get("highlight", {}).get("text") or [src.get("text", "")[:300]])[0],
                    score=float(hit["_score"]),
                    document_id=src["document_id"],
                )
            )
        return SearchResponse(total=total, page=request.page, results=results, took_ms=int((time.perf_counter() - start) * 1000))

    def _keyword_db(self, db: Session, request: SearchRequest, start: float) -> SearchResponse:
        pattern = f"%{request.query}%"
        rows: list[tuple[str, object, Company, Event, Document]] = []
        turn_stmt = select(Turn, Company, Event, Document).join(Document, Document.id == Turn.document_id).join(Event, Event.id == Document.event_id).join(Company, Company.id == Event.company_id).where(Turn.text.ilike(pattern))
        section_stmt = select(PressReleaseSection, Company, Event, Document).join(Document, Document.id == PressReleaseSection.document_id).join(Event, Event.id == Document.event_id).join(Company, Company.id == Event.company_id).where(PressReleaseSection.text.ilike(pattern))
        slide_stmt = select(Slide, Company, Event, Document).join(Document, Document.id == Slide.document_id).join(Event, Event.id == Document.event_id).join(Company, Company.id == Event.company_id).where(or_(Slide.title.ilike(pattern), Slide.body_text.ilike(pattern)))
        for stmt, content_type in [(turn_stmt, "turn"), (section_stmt, "section"), (slide_stmt, "slide")]:
            if request.companies:
                stmt = stmt.where(Company.id.in_(request.companies))
            if request.document_types:
                stmt = stmt.where(Document.document_type.in_(request.document_types))
            rows.extend((content_type, item, company, event, doc) for item, company, event, doc in db.execute(stmt).all())
        offset = (request.page - 1) * request.page_size
        results = [self._row_result(content_type, item, company, event, doc, request.query) for content_type, item, company, event, doc in rows[offset : offset + request.page_size]]
        return SearchResponse(total=len(rows), page=request.page, results=results, took_ms=int((time.perf_counter() - start) * 1000))

    def _row_result(self, content_type: str, item, company: Company, event: Event, doc: Document, query: str) -> SearchResult:
        text = item.text if content_type == "turn" else item.body_text or item.title or "" if content_type == "slide" else item.text
        return SearchResult(
            id=item.id,
            content_type=content_type,
            company_id=company.id,
            company_name=company.name,
            quarter=event.quarter,
            event_date=event.event_date,
            document_type=doc.document_type,
            speaker_name=getattr(item, "speaker_name", None),
            speaker_role=getattr(item, "speaker_role", None),
            snippet=self._snippet(text, query),
            score=1.0,
            document_id=doc.id,
        )

    def _embedding_result(self, db: Session, emb: Embedding, company_name: str, score: float) -> SearchResult:
        content_type = "turn" if emb.turn_id else "slide" if emb.slide_id else "section"
        source_id = emb.turn_id or emb.slide_id or emb.section_id or emb.id
        return SearchResult(
            id=source_id,
            content_type=content_type,
            company_id=emb.company_id,
            company_name=company_name,
            quarter=emb.quarter,
            event_date=emb.event_date,
            document_type=emb.document_type,
            speaker_role=emb.speaker_role,
            snippet=html.escape(emb.chunk_text[:300]),
            score=score,
            document_id=emb.document_id,
        )

    def _snippet(self, text: str, query: str) -> str:
        text = text or ""
        match = re.search(re.escape(query), text, re.I)
        if not match:
            return html.escape(text[:300])
        start = max(match.start() - 120, 0)
        end = min(match.end() + 180, len(text))
        snippet = html.escape(text[start:end])
        return re.sub(re.escape(html.escape(match.group(0))), f"<mark>{html.escape(match.group(0))}</mark>", snippet, flags=re.I)

    def _cosine(self, a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm = (sqrt(sum(x * x for x in a)) * sqrt(sum(y * y for y in b))) or 1.0
        return dot / norm
