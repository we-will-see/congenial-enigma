from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    document_type: str
    title: str | None
    original_filename: str | None
    mime_type: str | None
    source_type: str
    source_url: str | None
    rights_scope: str
    uploaded_by: str | None
    file_size_bytes: int | None
    content_version: int
    page_count: int | None
    pdf_type: str | None
    extraction_status: str
    extraction_method: str | None
    quality_score: float | None
    quality_flags: list[str] | None
    error_message: str | None
    created_at: datetime
    processed_at: datetime | None


class DocumentPageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    page_number: int
    text: str
    extraction_method: str
    confidence: float | None
    text_hash: str


class ManualTextDocumentCreate(BaseModel):
    company_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1)
    document_type: str = Field(default="other", min_length=1, max_length=50)
    publication_date: date = Field(default_factory=date.today)
    quarter: str | None = Field(default=None, max_length=10)
    fy_year: int | None = Field(default=None, ge=1900, le=2200)
    source_url: str | None = None
    rights_scope: Literal["public", "licensed", "internal", "private"] = "private"
    uploaded_by: str | None = Field(default=None, max_length=200)
    notebook_ids: list[int] = Field(default_factory=list)
    process_now: bool = True
    embed: bool = True


class ManualDocumentResult(BaseModel):
    document: DocumentOut
    deduplicated: bool


class DocumentProcessRequest(BaseModel):
    embed: bool = True


class TranscriptTurnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    turn_index: int
    speaker_raw: str | None
    speaker_name: str | None
    speaker_role: str
    speaker_org: str | None
    speaker_title: str | None
    text: str
    word_count: int | None


class CoverageRow(BaseModel):
    company_id: int
    company_name: str
    document_type: str | None
    extraction_status: str | None
    documents: int
    avg_quality: float | None
