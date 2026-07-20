from datetime import date
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.document import Document
from app.models.event import Event
from app.models.notebook import Notebook, NotebookDocument
from app.pipeline.classifier import event_type_for_document
from app.pipeline.orchestrator import process_document
from app.pipeline.storage import store_text_document, store_uploaded_document


def add_uploaded_document(
    db: Session,
    *,
    company_id: int,
    content: bytes,
    filename: str,
    content_type: str | None,
    title: str | None,
    document_type: str,
    publication_date: date,
    quarter: str | None = None,
    fy_year: int | None = None,
    source_url: str | None = None,
    rights_scope: str = "private",
    uploaded_by: str | None = None,
    notebook_ids: list[int] | None = None,
    process_now: bool = True,
    embed: bool = True,
) -> tuple[Document, bool]:
    company, notebooks = _validate_targets(db, company_id, notebook_ids or [])
    path, file_hash, safe_name, normalized_type = store_uploaded_document(
        content,
        filename,
        content_type,
        company.scrip_code,
    )
    return _create_or_reuse_document(
        db,
        company=company,
        notebooks=notebooks,
        path=str(path),
        file_hash=file_hash,
        original_filename=safe_name,
        mime_type=normalized_type,
        file_size_bytes=len(content),
        title=title or safe_name,
        document_type=document_type,
        publication_date=publication_date,
        quarter=quarter,
        fy_year=fy_year,
        source_url=source_url,
        rights_scope=rights_scope,
        uploaded_by=uploaded_by,
        process_now=process_now,
        embed=embed,
    )


def add_text_document(
    db: Session,
    *,
    company_id: int,
    title: str,
    text: str,
    document_type: str,
    publication_date: date,
    quarter: str | None = None,
    fy_year: int | None = None,
    source_url: str | None = None,
    rights_scope: str = "private",
    uploaded_by: str | None = None,
    notebook_ids: list[int] | None = None,
    process_now: bool = True,
    embed: bool = True,
) -> tuple[Document, bool]:
    company, notebooks = _validate_targets(db, company_id, notebook_ids or [])
    path, file_hash, safe_name, normalized_type = store_text_document(text, title, company.scrip_code)
    return _create_or_reuse_document(
        db,
        company=company,
        notebooks=notebooks,
        path=str(path),
        file_hash=file_hash,
        original_filename=safe_name,
        mime_type=normalized_type,
        file_size_bytes=len(text.encode("utf-8")),
        title=title,
        document_type=document_type,
        publication_date=publication_date,
        quarter=quarter,
        fy_year=fy_year,
        source_url=source_url,
        rights_scope=rights_scope,
        uploaded_by=uploaded_by,
        process_now=process_now,
        embed=embed,
    )


def _validate_targets(db: Session, company_id: int, notebook_ids: list[int]) -> tuple[Company, list[Notebook]]:
    company = db.get(Company, company_id)
    if not company:
        raise ValueError(f"company {company_id} not found")
    unique_ids = list(dict.fromkeys(notebook_ids))
    notebooks = list(db.scalars(select(Notebook).where(Notebook.id.in_(unique_ids)))) if unique_ids else []
    found_ids = {notebook.id for notebook in notebooks}
    missing_ids = [notebook_id for notebook_id in unique_ids if notebook_id not in found_ids]
    if missing_ids:
        raise ValueError(f"notebooks not found: {missing_ids}")
    return company, notebooks


def _create_or_reuse_document(
    db: Session,
    *,
    company: Company,
    notebooks: list[Notebook],
    path: str,
    file_hash: str,
    original_filename: str,
    mime_type: str,
    file_size_bytes: int,
    title: str,
    document_type: str,
    publication_date: date,
    quarter: str | None,
    fy_year: int | None,
    source_url: str | None,
    rights_scope: str,
    uploaded_by: str | None,
    process_now: bool,
    embed: bool,
) -> tuple[Document, bool]:
    existing = db.scalar(
        select(Document)
        .join(Event, Event.id == Document.event_id)
        .where(Event.company_id == company.id, Document.file_hash == file_hash)
        .order_by(Document.id)
    )
    if existing:
        _attach_to_notebooks(db, existing, notebooks, uploaded_by)
        db.commit()
        if process_now and existing.extraction_status in {"pending", "failed"}:
            existing = process_document(db, existing.id, embed=embed)
        return existing, True

    event = Event(
        company_id=company.id,
        bse_filing_id=f"manual:{uuid4().hex}",
        event_date=publication_date,
        event_type=event_type_for_document(document_type),
        quarter=quarter,
        fy_year=fy_year,
        filing_url=source_url,
    )
    db.add(event)
    db.flush()
    document = Document(
        event_id=event.id,
        document_type=document_type,
        title=title,
        original_filename=original_filename,
        mime_type=mime_type,
        source_type="manual",
        source_url=source_url,
        rights_scope=rights_scope,
        uploaded_by=uploaded_by,
        file_size_bytes=file_size_bytes,
        storage_path=path,
        file_hash=file_hash,
        extraction_status="pending",
    )
    db.add(document)
    db.flush()
    _attach_to_notebooks(db, document, notebooks, uploaded_by)
    db.commit()
    if process_now:
        document = process_document(db, document.id, embed=embed)
    return document, False


def _attach_to_notebooks(
    db: Session,
    document: Document,
    notebooks: list[Notebook],
    added_by: str | None,
) -> None:
    for notebook in notebooks:
        membership = db.get(NotebookDocument, (notebook.id, document.id))
        if not membership:
            db.add(NotebookDocument(notebook_id=notebook.id, document_id=document.id, added_by=added_by))
