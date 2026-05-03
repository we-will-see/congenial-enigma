import json
from collections.abc import AsyncIterator

from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.company import Company
from app.models.embedding import Embedding
from app.models.financial import Financial
from app.rag.prompts import RAG_SYSTEM_PROMPT
from app.schemas.qa import QARequest
from app.schemas.search import SearchRequest
from app.services.search_service import EmbeddingProvider, _semantic_stmt


def _question_mentions_financials(question: str) -> bool:
    terms = ["revenue", "ebitda", "margin", "pat", "profit", "eps", "financial", "grew", "growth"]
    lowered = question.lower()
    return any(term in lowered for term in terms)


def retrieve_context(db: Session, request: QARequest, limit: int = 10) -> tuple[list[dict], list[dict]]:
    vector = EmbeddingProvider().embed_query(request.question)
    search_request = SearchRequest(
        query=request.question,
        companies=request.company_ids,
        quarter_from=request.quarter_from,
        quarter_to=request.quarter_to,
        page=1,
        page_size=limit,
    )
    rows = db.execute(_semantic_stmt(search_request, vector)).all()
    citations = []
    for embedding, company_name, _distance in rows:
        citations.append(
            {
                "id": embedding.turn_id or embedding.slide_id or embedding.section_id or embedding.id,
                "company_name": company_name,
                "quarter": embedding.quarter,
                "speaker_name": embedding.speaker_role or "n_a",
                "document_type": embedding.document_type,
                "snippet": embedding.chunk_text[:500],
                "document_id": embedding.document_id,
            }
        )
    financials = []
    if _question_mentions_financials(request.question):
        stmt = select(Financial, Company.name.label("company_name")).join(Company, Company.id == Financial.company_id)
        if request.company_ids:
            stmt = stmt.where(Financial.company_id.in_(request.company_ids))
        financials = [
            {
                "company_name": row.company_name,
                "period": row.Financial.period,
                "revenue": str(row.Financial.revenue) if row.Financial.revenue is not None else None,
                "ebitda": str(row.Financial.ebitda) if row.Financial.ebitda is not None else None,
                "ebitda_margin": str(row.Financial.ebitda_margin) if row.Financial.ebitda_margin is not None else None,
                "pat": str(row.Financial.pat) if row.Financial.pat is not None else None,
            }
            for row in db.execute(stmt.order_by(Financial.period.desc()).limit(30)).all()
        ]
    return citations, financials


async def stream_answer(db: Session, request: QARequest) -> AsyncIterator[str]:
    if not settings.anthropic_api_key:
        yield f"data: {json.dumps({'type': 'error', 'content': 'ANTHROPIC_API_KEY is required for RAG Q&A'})}\n\n"
        return
    citations, financials = retrieve_context(db, request)
    context = "\n\n".join(
        f"[{c['company_name']}, {c['quarter']}, {c['speaker_name']}]\n{c['snippet']}" for c in citations
    )
    prompt = RAG_SYSTEM_PROMPT.format(context=context, financials=json.dumps(financials, indent=2))
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    async with client.messages.stream(
        model="claude-3-haiku-20240307",
        max_tokens=900,
        system=prompt,
        messages=[{"role": "user", "content": request.question}],
    ) as stream:
        async for text in stream.text_stream:
            yield f"data: {json.dumps({'type': 'token', 'content': text})}\n\n"
    yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"
    if financials:
        yield f"data: {json.dumps({'type': 'financials', 'data': financials})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"
