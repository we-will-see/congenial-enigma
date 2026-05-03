from pydantic import BaseModel, Field


class QARequest(BaseModel):
    question: str = Field(min_length=1)
    company_ids: list[int] | None = None
    quarter_from: str | None = None
    quarter_to: str | None = None
    session_id: str | None = None
