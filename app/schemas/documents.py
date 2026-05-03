from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    document_type: str
    bse_url: str | None
    storage_path: str
    page_count: int | None
    pdf_type: str | None
    extraction_status: str
    extraction_method: str | None
    quality_score: float | None
    quality_flags: list[str] | None
    error_message: str | None


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
