from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.config import settings
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.pipeline.orchestrator import process_document
from app.schemas.documents import (
    CoverageRow,
    DocumentOut,
    DocumentPageOut,
    DocumentProcessRequest,
    ManualDocumentResult,
    ManualTextDocumentCreate,
    TranscriptTurnOut,
)
from app.services.document_service import coverage_dashboard, list_event_documents, list_transcript_turns
from app.services.manual_document_service import add_text_document, add_uploaded_document

router = APIRouter(tags=["documents"])


@router.post("/documents/upload", response_model=ManualDocumentResult, status_code=201)
def upload_document(
    file: Annotated[UploadFile, File(description="PDF, TXT, or Markdown document")],
    company_id: Annotated[int, Form(gt=0)],
    document_type: Annotated[str, Form(max_length=50)] = "other",
    title: Annotated[str | None, Form(max_length=500)] = None,
    publication_date: Annotated[date | None, Form()] = None,
    quarter: Annotated[str | None, Form(max_length=10)] = None,
    fy_year: Annotated[int | None, Form(ge=1900, le=2200)] = None,
    source_url: Annotated[str | None, Form()] = None,
    rights_scope: Annotated[Literal["public", "licensed", "internal", "private"], Form()] = "private",
    uploaded_by: Annotated[str | None, Form(max_length=200)] = None,
    notebook_ids: Annotated[str | None, Form(description="Comma-separated notebook IDs")] = None,
    process_now: Annotated[bool, Form()] = True,
    embed: Annotated[bool, Form()] = True,
    db: Session = Depends(get_db),
) -> ManualDocumentResult:
    try:
        content = file.file.read(settings.max_upload_bytes + 1)
        document, deduplicated = add_uploaded_document(
            db,
            company_id=company_id,
            content=content,
            filename=file.filename or "document",
            content_type=file.content_type,
            title=title,
            document_type=document_type,
            publication_date=publication_date or date.today(),
            quarter=quarter,
            fy_year=fy_year,
            source_url=source_url,
            rights_scope=rights_scope,
            uploaded_by=uploaded_by,
            notebook_ids=_parse_notebook_ids(notebook_ids),
            process_now=process_now,
            embed=embed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc), "code": "DOCUMENT_UPLOAD_INVALID"}) from exc
    return ManualDocumentResult(document=DocumentOut.model_validate(document), deduplicated=deduplicated)


@router.post("/documents/add-text", response_model=ManualDocumentResult, status_code=201)
def add_document_text(request: ManualTextDocumentCreate, db: Session = Depends(get_db)) -> ManualDocumentResult:
    try:
        document, deduplicated = add_text_document(db, **request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc), "code": "DOCUMENT_TEXT_INVALID"}) from exc
    return ManualDocumentResult(document=DocumentOut.model_validate(document), deduplicated=deduplicated)


@router.get("/documents/{document_id}", response_model=DocumentOut)
def document_detail(document_id: int, db: Session = Depends(get_db)) -> DocumentOut:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail={"error": "Document not found", "code": "DOCUMENT_NOT_FOUND"})
    return DocumentOut.model_validate(document)


@router.get("/documents/{document_id}/pages", response_model=list[DocumentPageOut])
def document_pages(document_id: int, db: Session = Depends(get_db)) -> list[DocumentPageOut]:
    if not db.get(Document, document_id):
        raise HTTPException(status_code=404, detail={"error": "Document not found", "code": "DOCUMENT_NOT_FOUND"})
    pages = db.scalars(
        select(DocumentPage).where(DocumentPage.document_id == document_id).order_by(DocumentPage.page_number)
    )
    return [DocumentPageOut.model_validate(page) for page in pages]


@router.post("/documents/{document_id}/process", response_model=DocumentOut)
def process_stored_document(
    document_id: int,
    request: DocumentProcessRequest,
    db: Session = Depends(get_db),
) -> DocumentOut:
    if not db.get(Document, document_id):
        raise HTTPException(status_code=404, detail={"error": "Document not found", "code": "DOCUMENT_NOT_FOUND"})
    try:
        return DocumentOut.model_validate(process_document(db, document_id, embed=request.embed))
    except Exception as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc), "code": "DOCUMENT_PROCESSING_FAILED"}) from exc


@router.get("/events/{event_id}/documents", response_model=list[DocumentOut])
def event_documents(event_id: int, db: Session = Depends(get_db)) -> list[DocumentOut]:
    return [DocumentOut.model_validate(document) for document in list_event_documents(db, event_id)]


@router.get("/documents/{document_id}/transcript", response_model=list[TranscriptTurnOut])
def transcript(document_id: int, db: Session = Depends(get_db)) -> list[TranscriptTurnOut]:
    turns = list_transcript_turns(db, document_id)
    if not turns:
        raise HTTPException(status_code=404, detail={"error": "Transcript not found", "code": "TRANSCRIPT_NOT_FOUND"})
    return [TranscriptTurnOut.model_validate(turn) for turn in turns]


@router.get("/coverage", response_model=list[CoverageRow])
def coverage(db: Session = Depends(get_db)) -> list[CoverageRow]:
    return coverage_dashboard(db)


def _parse_notebook_ids(value: str | None) -> list[int]:
    if not value:
        return []
    try:
        ids = [int(part.strip()) for part in value.split(",") if part.strip()]
    except ValueError as exc:
        raise ValueError("notebook_ids must be a comma-separated list of integers") from exc
    if any(notebook_id <= 0 for notebook_id in ids):
        raise ValueError("notebook IDs must be positive integers")
    return ids
