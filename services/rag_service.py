from __future__ import annotations

import json
from collections.abc import Iterator

from anthropic import Anthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.core.config import get_settings
from api.db.models import Company, Financial
from api.schemas.contracts import QARequest, SearchRequest
from services.search_service import SearchService

RAG_SYSTEM_PROMPT = """
You are IndiaIR, a research assistant for Indian equity analysts.
You answer questions about Indian listed companies using their public IR filings.

RULES:
1. Answer only from the provided context. Do not use general knowledge about these companies.
2. If context is insufficient, say: "I could not find relevant information for this question in the available filings."
3. Every factual claim must be attributable to a specific passage. Use inline citations: [Company, Quarter, Speaker].
4. For financial figures, always state the unit (Crores INR unless otherwise noted).
5. When comparing companies, structure your answer with one paragraph per company.
6. Do not speculate about future performance beyond what management has explicitly stated.
7. If financial data is provided in the FINANCIALS section, use it to ground commentary in actual numbers.
8. Keep answers concise - 200-400 words unless the question requires more.

FORMAT:
- Write in plain prose, no bullet points.
- Citations inline: [Laurus Labs, 3QFY25, Management]
- Financial figures: "Rs 1,547 Cr" format

CONTEXT:
{context}

FINANCIALS (if relevant):
{financials}
"""


class RAGService:
    def __init__(self) -> None:
        self.search = SearchService()

    def stream_answer(self, db: Session, request: QARequest) -> Iterator[str]:
        search_request = SearchRequest(query=request.question, companies=request.company_ids, quarter_from=request.quarter_from, quarter_to=request.quarter_to, page_size=10)
        retrieval = self.search.semantic(db, search_request)
        financials = self._financials(db, request)
        context = "\n\n".join(f"[{item.company_name}, {item.quarter or 'n/a'}, {item.speaker_name or item.speaker_role or item.document_type}] {item.snippet}" for item in retrieval.results)
        settings = get_settings()
        if settings.anthropic_api_key and retrieval.results:
            client = Anthropic(api_key=settings.anthropic_api_key)
            prompt = RAG_SYSTEM_PROMPT.format(context=context, financials=json.dumps(financials, default=str))
            with client.messages.stream(model="claude-3-5-sonnet-20240620", max_tokens=900, system=prompt, messages=[{"role": "user", "content": request.question}]) as stream:
                for text in stream.text_stream:
                    yield self._event("token", {"content": text})
        else:
            answer = self._fallback_answer(retrieval.results)
            for token in answer.split(" "):
                yield self._event("token", {"content": token + " "})
        yield self._event("citations", {"citations": [item.model_dump(mode="json") for item in retrieval.results[:10]]})
        if financials:
            yield self._event("financials", {"data": financials})
        yield self._event("done", {})

    def _financials(self, db: Session, request: QARequest) -> list[dict]:
        signals = ["revenue", "margin", "profit", "pat", "ebitda", "growth", "financial"]
        if not any(signal in request.question.lower() for signal in signals):
            return []
        stmt = select(Financial, Company.name).join(Company, Company.id == Financial.company_id).order_by(Financial.period)
        if request.company_ids:
            stmt = stmt.where(Financial.company_id.in_(request.company_ids))
        return [
            {
                "company_name": company_name,
                "period": fin.period,
                "period_type": fin.period_type,
                "revenue": fin.revenue,
                "ebitda": fin.ebitda,
                "ebitda_margin": fin.ebitda_margin,
                "pat": fin.pat,
            }
            for fin, company_name in db.execute(stmt).all()
        ]

    def _fallback_answer(self, results) -> str:
        if not results:
            return "I could not find relevant information for this question in the available filings."
        top = results[0]
        return f"The available filings include a relevant passage from {top.company_name} {top.quarter or ''}: {top.snippet} [{top.company_name}, {top.quarter or 'n/a'}, {top.speaker_name or top.speaker_role or 'Source'}]"

    def _event(self, event_type: str, payload: dict) -> str:
        return f"data: {json.dumps({'type': event_type, **payload}, default=str)}\n\n"
