import html
import time
from dataclasses import dataclass

from elasticsearch import Elasticsearch
from sqlalchemy import Select, and_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.company import Company
from app.models.document import Document
from app.models.embedding import Embedding
from app.models.event import Event
from app.schemas.search import SearchRequest, SearchResponse, SearchResult


ES_MAPPING = {
    "mappings": {
        "properties": {
            "text": {"type": "text", "analyzer": "english", "fields": {"keyword": {"type": "keyword"}}},
            "company_id": {"type": "integer"},
            "company_name": {"type": "keyword"},
            "quarter": {"type": "keyword"},
            "fy_year": {"type": "integer"},
            "event_date": {"type": "date"},
            "document_type": {"type": "keyword"},
            "speaker_role": {"type": "keyword"},
            "speaker_name": {"type": "keyword"},
            "section_type": {"type": "keyword"},
            "turn_id": {"type": "long"},
            "slide_id": {"type": "long"},
            "section_id": {"type": "long"},
            "document_id": {"type": "integer"},
        }
    },
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "english": {
                    "tokenizer": "standard",
                    "filter": ["lowercase", "english_stop", "english_stemmer"],
                }
            },
            "filter": {
                "english_stop": {"type": "stop", "stopwords": "_english_"},
                "english_stemmer": {"type": "stemmer", "language": "english"},
            },
        },
    },
}


def get_es_client() -> Elasticsearch:
    return Elasticsearch(settings.es_host)


def ensure_index(client: Elasticsearch | None = None) -> None:
    es = client or get_es_client()
    if not es.indices.exists(index=settings.es_index_name):
        es.indices.create(index=settings.es_index_name, **ES_MAPPING)


def _filter_clauses(request: SearchRequest) -> list[dict]:
    filters: list[dict] = []
    if request.companies:
        filters.append({"terms": {"company_id": request.companies}})
    if request.document_types:
        filters.append({"terms": {"document_type": request.document_types}})
    if request.speaker_roles:
        filters.append({"terms": {"speaker_role": request.speaker_roles}})
    if request.quarter_from or request.quarter_to:
        # Quarter strings are stored as keywords; callers should prefer date filters once UI adds them.
        if request.quarter_from:
            filters.append({"range": {"quarter": {"gte": request.quarter_from}}})
        if request.quarter_to:
            filters.append({"range": {"quarter": {"lte": request.quarter_to}}})
    return filters


def keyword_search(request: SearchRequest) -> SearchResponse:
    started = time.perf_counter()
    es = get_es_client()
    body = {
        "from": (request.page - 1) * request.page_size,
        "size": request.page_size,
        "query": {
            "bool": {
                "must": [{"match": {"text": request.query}}],
                "filter": _filter_clauses(request),
            }
        },
        "highlight": {"fields": {"text": {"fragment_size": 300, "number_of_fragments": 1}}},
    }
    response = es.search(index=settings.es_index_name, body=body)
    hits = response["hits"]["hits"]
    results = []
    for hit in hits:
        source = hit["_source"]
        content_id = source.get("turn_id") or source.get("slide_id") or source.get("section_id")
        content_type = "turn" if source.get("turn_id") else "slide" if source.get("slide_id") else "section"
        highlight = hit.get("highlight", {}).get("text", [None])[0]
        snippet = highlight or html.escape(source.get("text", "")[:300])
        results.append(
            SearchResult(
                id=content_id,
                content_type=content_type,
                company_id=source["company_id"],
                company_name=source["company_name"],
                quarter=source.get("quarter"),
                event_date=source.get("event_date"),
                document_type=source["document_type"],
                speaker_name=source.get("speaker_name"),
                speaker_role=source.get("speaker_role"),
                snippet=snippet,
                score=float(hit["_score"]),
                document_id=source["document_id"],
            )
        )
    return SearchResponse(
        total=response["hits"]["total"]["value"],
        page=request.page,
        results=results,
        took_ms=int((time.perf_counter() - started) * 1000),
    )


@dataclass
class EmbeddingProvider:
    def embed_query(self, text: str) -> list[float]:
        from openai import OpenAI

        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for semantic search")
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.embeddings.create(model="text-embedding-3-small", input=text)
        return response.data[0].embedding


def _semantic_stmt(request: SearchRequest, vector: list[float]) -> Select:
    distance = Embedding.embedding.cosine_distance(vector).label("distance")
    stmt = (
        select(Embedding, Company.name.label("company_name"), distance)
        .join(Company, Company.id == Embedding.company_id)
        .join(Document, Document.id == Embedding.document_id)
        .join(Event, Event.id == Document.event_id)
        .order_by(distance)
        .limit(request.page_size)
        .offset((request.page - 1) * request.page_size)
    )
    clauses = []
    if request.companies:
        clauses.append(Embedding.company_id.in_(request.companies))
    if request.document_types:
        clauses.append(Embedding.document_type.in_(request.document_types))
    if request.speaker_roles:
        clauses.append(Embedding.speaker_role.in_(request.speaker_roles))
    if request.quarter_from:
        clauses.append(Embedding.quarter >= request.quarter_from)
    if request.quarter_to:
        clauses.append(Embedding.quarter <= request.quarter_to)
    if clauses:
        stmt = stmt.where(and_(*clauses))
    return stmt


def semantic_search(db: Session, request: SearchRequest, provider: EmbeddingProvider | None = None) -> SearchResponse:
    started = time.perf_counter()
    vector = (provider or EmbeddingProvider()).embed_query(request.query)
    rows = db.execute(_semantic_stmt(request, vector)).all()
    results = []
    for embedding, company_name, distance in rows:
        source_id = embedding.turn_id or embedding.slide_id or embedding.section_id or embedding.id
        content_type = "turn" if embedding.turn_id else "slide" if embedding.slide_id else "section"
        results.append(
            SearchResult(
                id=source_id,
                content_type=content_type,
                company_id=embedding.company_id,
                company_name=company_name,
                quarter=embedding.quarter,
                event_date=embedding.event_date,
                document_type=embedding.document_type,
                speaker_name=None,
                speaker_role=embedding.speaker_role,
                snippet=html.escape(embedding.chunk_text[:300]),
                score=max(0.0, 1.0 - float(distance or 0.0)),
                document_id=embedding.document_id,
            )
        )
    return SearchResponse(total=len(results), page=request.page, results=results, took_ms=int((time.perf_counter() - started) * 1000))
