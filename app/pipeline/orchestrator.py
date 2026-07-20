import hashlib
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.company import Company
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.event import Event
from app.models.financial import Financial
from app.models.management_change import ManagementChange
from app.models.pipeline_run import PipelineRun
from app.models.press_release import PressReleaseSection
from app.models.slide import Slide
from app.models.turn import Turn
from app.pipeline.bse_client import BSEClient, BSEFiling
from app.pipeline.classifier import classify_filing, event_type_for_document
from app.pipeline.document_indexer import rebuild_chunks_for_document
from app.pipeline.financial_extractor import extract_financial_row_from_text
from app.pipeline.management_extractor import extract_management_changes
from app.pipeline.pdf_extractor import ExtractionResult, clean_text, extract_pdf, quality_score
from app.pipeline.presentation_parser import parse_slides
from app.pipeline.press_release_parser import parse_press_release_sections
from app.pipeline.storage import download_pdf
from app.pipeline.transcript_parser import parse_transcript
from app.pipeline.universe import TARGET_COMPANIES


def seed_companies(db: Session) -> int:
    count = 0
    for company in TARGET_COMPANIES:
        stmt = (
            insert(Company)
            .values(scrip_code=company["scrip_code"], name=company["name"], sector=company["sector"], active=True)
            .on_conflict_do_update(index_elements=[Company.scrip_code], set_={"name": company["name"], "sector": company["sector"], "active": True})
        )
        db.execute(stmt)
        count += 1
    db.commit()
    return count


async def ingest_filings(db: Session, start_date: date, end_date: date) -> PipelineRun:
    run = PipelineRun(run_type="backfill", status="running", errors=[], metrics={})
    db.add(run)
    db.commit()
    seed_companies(db)
    client = BSEClient()
    for company in db.scalars(select(Company).where(Company.active.is_(True)).order_by(Company.scrip_code)):
        try:
            filings = await client.fetch_filings(company.scrip_code, start_date, end_date)
            for filing in filings:
                try:
                    document = await upsert_filing(db, company, filing)
                    if document and document.extraction_status in {"pending", "failed"}:
                        process_document(db, document.id)
                        run.documents_processed += 1
                        db.commit()
                except Exception as exc:
                    run.documents_failed += 1
                    run.errors = [
                        *run.errors,
                        {"company": company.scrip_code, "filing": filing.bse_filing_id, "error": str(exc)},
                    ]
                    db.commit()
        except Exception as exc:
            run.documents_failed += 1
            run.errors = [*run.errors, {"company": company.scrip_code, "error": str(exc)}]
            db.commit()
    run.status = "partial" if run.documents_failed else "complete"
    run.completed_at = datetime.now(UTC)
    run.metrics = {
        "documents_processed": run.documents_processed,
        "documents_failed": run.documents_failed,
    }
    db.commit()
    return run


async def upsert_filing(db: Session, company: Company, filing: BSEFiling) -> Document | None:
    document_type = classify_filing(filing.category, filing.subcategory, filing.headline)
    if not filing.attachment_url:
        return None
    existing = db.scalar(select(Event).where(Event.bse_filing_id == filing.bse_filing_id))
    if existing:
        return db.scalar(select(Document).where(Document.event_id == existing.id))
    path, file_hash = await download_pdf(filing.attachment_url, company.scrip_code, filing.bse_filing_id)
    if db.scalar(select(Document).where(Document.file_hash == file_hash)):
        return None
    event = Event(company_id=company.id, bse_filing_id=filing.bse_filing_id, event_date=filing.filing_date, event_type=event_type_for_document(document_type), filing_url=filing.attachment_url)
    db.add(event)
    db.flush()
    document = Document(
        event_id=event.id,
        document_type=document_type,
        title=filing.headline,
        original_filename=path.name,
        mime_type="application/pdf",
        source_type="bse",
        source_url=filing.attachment_url,
        storage_path=str(path),
        file_hash=file_hash,
        file_size_bytes=path.stat().st_size,
    )
    db.add(document)
    db.commit()
    return document


def process_document(db: Session, document_id: int, embed: bool = True) -> Document:
    document = db.get(Document, document_id)
    if not document:
        raise ValueError(f"document {document_id} not found")
    document.extraction_status = "processing"
    db.commit()
    try:
        result = _extract_document(document)
        document.page_count = result.page_count
        document.pdf_type = result.pdf_type
        document.extraction_method = result.method
        document.quality_score = result.quality_score
        document.quality_flags = result.quality_flags
        document.error_message = None

        db.execute(delete(DocumentPage).where(DocumentPage.document_id == document.id))
        for page_number, page_text in enumerate(result.page_texts, start=1):
            db.add(
                DocumentPage(
                    document_id=document.id,
                    page_number=page_number,
                    text=page_text,
                    extraction_method=result.method,
                    confidence=quality_score(page_text),
                    text_hash=hashlib.sha256(page_text.encode("utf-8")).hexdigest(),
                )
            )
        if document.document_type == "concall_transcript":
            db.execute(delete(Turn).where(Turn.document_id == document.id))
            for turn in parse_transcript(result.text):
                db.add(Turn(document_id=document.id, **turn))
        elif document.document_type == "investor_presentation":
            db.execute(delete(Slide).where(Slide.document_id == document.id))
            for slide in parse_slides(result.page_texts):
                db.add(Slide(document_id=document.id, **slide))
        elif document.document_type == "results_press_release":
            db.execute(delete(PressReleaseSection).where(PressReleaseSection.document_id == document.id))
            for section in parse_press_release_sections(result.text):
                db.add(PressReleaseSection(document_id=document.id, **section))
            _upsert_financials(db, document, result.text)
        elif document.document_type == "management_change":
            _upsert_management_changes(db, document, result.text)
        db.flush()
        rebuild_chunks_for_document(db, document.id, embed=embed)
        document.extraction_status = "low_quality" if "LOW_QUALITY_EXTRACTION" in result.quality_flags else "complete"
        document.processed_at = datetime.now(UTC)
        db.commit()
        return document
    except Exception as exc:
        db.rollback()
        document = db.get(Document, document_id)
        if not document:
            raise
        document.extraction_status = "failed"
        document.error_message = str(exc)
        document.processed_at = datetime.now(UTC)
        db.commit()
        raise


def _extract_document(document: Document) -> ExtractionResult:
    path = Path(document.storage_path)
    if not path.is_file():
        raise ValueError(f"stored document is missing: {path}")
    if document.mime_type == "application/pdf" or path.suffix.lower() == ".pdf":
        return extract_pdf(path)

    if path.suffix.lower() not in {".txt", ".md"}:
        raise ValueError(f"unsupported stored document type: {path.suffix or document.mime_type}")
    raw_text = path.read_text(encoding="utf-8")
    page_texts = [clean_text(page) for page in raw_text.split("\f")]
    page_texts = [page for page in page_texts if page]
    text = clean_text("\n\n".join(page_texts))
    score = quality_score(text)
    flags = ["LOW_QUALITY_EXTRACTION"] if score < settings.min_text_quality_score else []
    return ExtractionResult(
        text=text,
        page_texts=page_texts or [""],
        page_count=max(1, len(page_texts)),
        pdf_type="text",
        method="utf8",
        quality_score=score,
        quality_flags=flags,
    )


def _upsert_financials(db: Session, document: Document, text: str) -> None:
    event = db.get(Event, document.event_id)
    if not event or not event.quarter:
        return
    row = extract_financial_row_from_text(text)
    if not any(row.get(field) is not None for field in ["revenue", "ebitda", "pat"]):
        return
    values = {
        "company_id": event.company_id,
        "document_id": document.id,
        "period": event.quarter,
        "period_type": "quarterly",
        **row,
    }
    stmt = insert(Financial).values(**values).on_conflict_do_update(index_elements=[Financial.company_id, Financial.period, Financial.period_type], set_=values)
    db.execute(stmt)


def _upsert_management_changes(db: Session, document: Document, text: str) -> None:
    event = db.get(Event, document.event_id)
    if not event:
        return
    for change in extract_management_changes(text):
        stmt = (
            insert(ManagementChange)
            .values(
                company_id=event.company_id,
                document_id=document.id,
                filing_date=event.event_date,
                effective_date=change.get("effective_date"),
                change_type=change["change_type"],
                person_name=change["person_name"],
                role=change["role"],
                role_category=change["role_category"],
                reason=change.get("reason"),
                din=change.get("din"),
                raw_text=text[:10000],
                extraction_confidence=change.get("confidence"),
            )
            .on_conflict_do_nothing(constraint="uq_mgmt_change_identity")
        )
        db.execute(stmt)
