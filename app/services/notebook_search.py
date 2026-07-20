from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.company import Company
from app.models.document import Document
from app.models.event import Event
from app.models.notebook import Notebook, NotebookDocument
from app.pipeline.embedding_service import embed_texts
from app.schemas.notebooks import EvidenceItem, EvidencePack, NotebookSearchRequest


def reciprocal_rank_fusion(rankings: Iterable[list[int]], k: int = 60) -> dict[int, float]:
    """Fuse ranked chunk IDs without requiring comparable raw search scores."""
    if k < 1:
        raise ValueError("k must be positive")
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + (1.0 / (k + rank))
    return scores


class QueryEmbeddingProvider:
    def embed_query(self, query: str) -> list[float] | None:
        vectors = embed_texts([query])
        return vectors[0] if vectors else None


def search_notebook(
    db: Session,
    notebook_id: int,
    request: NotebookSearchRequest,
    embedding_provider: QueryEmbeddingProvider | None = None,
) -> EvidencePack:
    """Retrieve cited notebook evidence. This function never generates an answer."""
    if not db.get(Notebook, notebook_id):
        raise ValueError(f"notebook {notebook_id} not found")

    candidate_limit = min(200, max(20, request.top_k * 4))
    rows_by_id: dict[int, tuple[Chunk, Document, Event, Company]] = {}
    rankings: list[list[int]] = []
    methods_by_id: dict[int, set[str]] = {}

    if request.mode in {"hybrid", "keyword"}:
        lexical_rows = _keyword_rows(db, notebook_id, request, candidate_limit)
        lexical_ranking = []
        for chunk, document, event, company, _score in lexical_rows:
            rows_by_id[chunk.id] = (chunk, document, event, company)
            lexical_ranking.append(chunk.id)
            methods_by_id.setdefault(chunk.id, set()).add("keyword")
        rankings.append(lexical_ranking)

    vector: list[float] | None = None
    if request.mode in {"hybrid", "semantic"}:
        if embedding_provider is not None or settings.openai_api_key:
            try:
                vector = (embedding_provider or QueryEmbeddingProvider()).embed_query(request.query)
            except Exception as exc:
                if request.mode == "semantic":
                    raise ValueError(f"embedding provider failed: {exc}") from exc
        if request.mode == "semantic" and vector is None:
            raise ValueError("semantic search requires OPENAI_API_KEY or an embedding provider")
        if vector is not None:
            semantic_rows = _semantic_rows(db, notebook_id, request, vector, candidate_limit)
            semantic_ranking = []
            for chunk, document, event, company, _distance in semantic_rows:
                rows_by_id[chunk.id] = (chunk, document, event, company)
                semantic_ranking.append(chunk.id)
                methods_by_id.setdefault(chunk.id, set()).add("semantic")
            rankings.append(semantic_ranking)

    fused_scores = reciprocal_rank_fusion(rankings)
    ranked_ids = sorted(fused_scores, key=lambda chunk_id: (-fused_scores[chunk_id], chunk_id))[: request.top_k]
    evidence = []
    for chunk_id in ranked_ids:
        chunk, document, event, company = rows_by_id[chunk_id]
        methods = sorted(methods_by_id[chunk_id], key=lambda item: (item != "keyword", item))
        evidence.append(
            EvidenceItem(
                chunk_id=chunk.id,
                chunk_ordinal=chunk.ordinal,
                document_id=document.id,
                document_content_version=document.content_version,
                company_id=company.id,
                company_name=company.name,
                document_title=document.title,
                document_type=document.document_type,
                source_type=document.source_type,
                source_url=document.source_url,
                rights_scope=document.rights_scope,
                quality_score=document.quality_score,
                event_date=event.event_date,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                citation=_citation(
                    document.id,
                    document.content_version,
                    chunk.page_start,
                    chunk.page_end,
                    chunk.ordinal,
                ),
                text=chunk.text,
                chunker_version=chunk.chunker_version,
                embedding_model=chunk.embedding_model,
                score=round(fused_scores[chunk_id], 8),
                retrieval_methods=methods,
            )
        )

    effective_mode = request.mode
    if request.mode == "hybrid" and vector is None:
        effective_mode = "keyword_fallback"
    return EvidencePack(
        notebook_id=notebook_id,
        query=request.query,
        retrieval_mode=effective_mode,
        generated_at=datetime.now(UTC),
        total_candidates=len(rows_by_id),
        evidence=evidence,
    )


def _keyword_rows(
    db: Session,
    notebook_id: int,
    request: NotebookSearchRequest,
    limit: int,
) -> list[tuple[Chunk, Document, Event, Company, float]]:
    return list(db.execute(_keyword_stmt(notebook_id, request, limit)))


def _keyword_stmt(notebook_id: int, request: NotebookSearchRequest, limit: int) -> Select:
    query = func.plainto_tsquery("english", request.query)
    vector = func.to_tsvector("english", Chunk.text)
    rank = func.ts_rank_cd(vector, query).label("rank")
    return (
        _base_stmt(notebook_id, request)
        .add_columns(rank)
        .where(vector.op("@@")(query))
        .order_by(rank.desc(), Chunk.id)
        .limit(limit)
    )


def _semantic_rows(
    db: Session,
    notebook_id: int,
    request: NotebookSearchRequest,
    vector: list[float],
    limit: int,
) -> list[tuple[Chunk, Document, Event, Company, float]]:
    return list(db.execute(_semantic_stmt(notebook_id, request, vector, limit)))


def _semantic_stmt(
    notebook_id: int,
    request: NotebookSearchRequest,
    vector: list[float],
    limit: int,
) -> Select:
    distance = Chunk.embedding.cosine_distance(vector).label("distance")
    return (
        _base_stmt(notebook_id, request)
        .add_columns(distance)
        .where(Chunk.embedding.is_not(None))
        .order_by(distance, Chunk.id)
        .limit(limit)
    )


def _base_stmt(notebook_id: int, request: NotebookSearchRequest) -> Select:
    stmt = (
        select(Chunk, Document, Event, Company)
        .join(NotebookDocument, NotebookDocument.document_id == Chunk.document_id)
        .join(Document, Document.id == Chunk.document_id)
        .join(Event, Event.id == Document.event_id)
        .join(Company, Company.id == Event.company_id)
        .where(
            NotebookDocument.notebook_id == notebook_id,
            Document.extraction_status.in_(["complete", "low_quality"]),
        )
    )
    if request.company_ids:
        stmt = stmt.where(Company.id.in_(request.company_ids))
    if request.document_types:
        stmt = stmt.where(Document.document_type.in_(request.document_types))
    if request.source_types:
        stmt = stmt.where(Document.source_type.in_(request.source_types))
    if request.tags:
        normalized_tags = [tag.strip().lower() for tag in request.tags if tag.strip()]
        if normalized_tags:
            stmt = stmt.where(NotebookDocument.tags.overlap(normalized_tags))
    if request.date_from:
        stmt = stmt.where(Event.event_date >= request.date_from)
    if request.date_to:
        stmt = stmt.where(Event.event_date <= request.date_to)
    return stmt


def _citation(
    document_id: int,
    content_version: int,
    page_start: int,
    page_end: int,
    chunk_ordinal: int,
) -> str:
    pages = f"p{page_start}" if page_start == page_end else f"p{page_start}-{page_end}"
    return f"doc:{document_id}:v{content_version}:{pages}:chunk:{chunk_ordinal}"
