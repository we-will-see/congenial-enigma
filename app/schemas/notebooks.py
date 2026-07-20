from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NotebookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    namespace_id: str = Field(default="default", min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    owner_id: str | None = Field(default=None, max_length=200)


class NotebookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    namespace_id: str
    name: str
    description: str | None
    owner_id: str | None
    created_at: datetime
    updated_at: datetime
    document_count: int = 0


class NotebookDocumentAdd(BaseModel):
    tags: list[str] = Field(default_factory=list, max_length=20)
    added_by: str | None = Field(default=None, max_length=200)


class NotebookDocumentOut(BaseModel):
    notebook_id: int
    document_id: int
    title: str | None
    document_type: str
    source_type: str
    extraction_status: str
    tags: list[str]
    added_by: str | None
    added_at: datetime


class NotebookSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    mode: Literal["hybrid", "keyword", "semantic"] = "hybrid"
    top_k: int = Field(default=10, ge=1, le=50)
    company_ids: list[int] | None = None
    document_types: list[str] | None = None
    source_types: list[str] | None = None
    tags: list[str] | None = None
    date_from: date | None = None
    date_to: date | None = None

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        query = value.strip()
        if len(query) < 2:
            raise ValueError("query must contain at least two non-whitespace characters")
        return query


class EvidenceItem(BaseModel):
    chunk_id: int
    chunk_ordinal: int
    document_id: int
    document_content_version: int
    company_id: int
    company_name: str
    document_title: str | None
    document_type: str
    source_type: str
    source_url: str | None
    rights_scope: str
    quality_score: float | None
    event_date: date
    page_start: int
    page_end: int
    citation: str
    text: str
    chunker_version: str
    embedding_model: str | None
    score: float
    retrieval_methods: list[Literal["keyword", "semantic"]]


class EvidencePack(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    notebook_id: int
    query: str
    retrieval_mode: Literal["hybrid", "keyword", "semantic", "keyword_fallback"]
    generated_at: datetime
    total_candidates: int
    evidence: list[EvidenceItem]
