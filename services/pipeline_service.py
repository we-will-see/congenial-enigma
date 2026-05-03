from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from api.db.models import Company, Document, Event, Financial, ManagementChange, PressReleaseSection, Slide, Turn
from extraction.financial_extractor import FinancialExtractor
from extraction.mgmt_change_parser import ManagementChangeParser
from extraction.press_release_parser import PressReleaseParser
from extraction.text_extractor import TextExtractor
from extraction.transcript_parser import TranscriptParser
from indexing.embedding_indexer import EmbeddingIndexer
from indexing.es_indexer import ESIndexer


class PipelineService:
    def __init__(self) -> None:
        self.text_extractor = TextExtractor()
        self.transcript_parser = TranscriptParser()
        self.press_parser = PressReleaseParser()
        self.financial_extractor = FinancialExtractor()
        self.mgmt_parser = ManagementChangeParser()
        self.embedding_indexer = EmbeddingIndexer()

    def process_document(self, db: Session, document: Document) -> None:
        document.extraction_status = "processing"
        db.commit()
        try:
            result = self._extract_text(document)
            document.page_count = result.page_count
            document.pdf_type = result.pdf_type
            document.extraction_method = result.method
            document.quality_score = result.quality_score
            document.quality_flags = result.quality_flags
            if document.document_type == "concall_transcript":
                self._store_turns(db, document, result.text)
            elif document.document_type == "investor_presentation":
                self._store_slides(db, document, result.text)
            elif document.document_type == "results_press_release":
                self._store_press_release(db, document, result.text)
            elif document.document_type == "management_change":
                self._store_management_changes(db, document, result.text)
            elif document.document_type in {"board_meeting_outcome", "other"}:
                document.extraction_status = "skipped"
                db.commit()
                return
            document.extraction_status = "low_quality" if result.quality_flags and not result.text else "complete"
            document.processed_at = datetime.now()
            db.commit()
            self.embedding_indexer.index_document_content(db, document)
            try:
                ESIndexer().index_document_content(db, document)
            except Exception:
                pass
        except Exception as exc:
            document.extraction_status = "failed"
            document.error_message = str(exc)
            db.commit()

    def _extract_text(self, document: Document):
        path = Path(document.storage_path)
        if path.suffix.lower() == ".txt":
            text = path.read_text(errors="ignore")
            from extraction.text_extractor import ExtractionResult

            return ExtractionResult(text=text, pdf_type="text", method="fixture", page_count=1, quality_score=1.0, quality_flags=[])
        return self.text_extractor.extract(document.storage_path)

    def _store_turns(self, db: Session, document: Document, text: str) -> None:
        db.execute(delete(Turn).where(Turn.document_id == document.id))
        turns = self.transcript_parser.parse(text)
        db.add_all([Turn(document_id=document.id, **turn.__dict__) for turn in turns])

    def _store_slides(self, db: Session, document: Document, text: str) -> None:
        db.execute(delete(Slide).where(Slide.document_id == document.id))
        for idx, block in enumerate(text.split("\f") if "\f" in text else text.split("\n\n")):
            if block.strip():
                lines = block.strip().splitlines()
                db.add(Slide(document_id=document.id, slide_number=idx + 1, title=lines[0][:200], body_text="\n".join(lines[1:])))

    def _store_press_release(self, db: Session, document: Document, text: str) -> None:
        db.execute(delete(PressReleaseSection).where(PressReleaseSection.document_id == document.id))
        for section in self.press_parser.parse(text):
            db.add(PressReleaseSection(document_id=document.id, section_type=section.section_type, section_order=section.section_order, text=section.text))
        event = db.scalar(select(Event).where(Event.id == document.event_id))
        row = self.financial_extractor.extract_from_text(text)
        if row and event:
            existing = db.scalar(select(Financial).where(Financial.company_id == event.company_id, Financial.period == row["period"], Financial.period_type == row["period_type"]))
            payload = {key: value for key, value in row.items() if hasattr(Financial, key)}
            if existing:
                for key, value in payload.items():
                    setattr(existing, key, value)
            else:
                db.add(Financial(company_id=event.company_id, document_id=document.id, **payload))

    def _store_management_changes(self, db: Session, document: Document, text: str) -> None:
        event = db.scalar(select(Event).where(Event.id == document.event_id))
        if not event:
            return
        for item in self.mgmt_parser.parse(text, event.event_date):
            exists = db.scalar(
                select(ManagementChange).where(
                    ManagementChange.company_id == event.company_id,
                    ManagementChange.person_name == item["person_name"],
                    ManagementChange.change_type == item["change_type"],
                    ManagementChange.effective_date == item.get("effective_date"),
                )
            )
            if not exists:
                db.add(
                    ManagementChange(
                        company_id=event.company_id,
                        document_id=document.id,
                        filing_date=event.event_date,
                        effective_date=item.get("effective_date"),
                        change_type=item["change_type"],
                        person_name=item["person_name"],
                        role=item["role"],
                        role_category=item["role_category"],
                        reason=item.get("reason"),
                        din=item.get("din"),
                        raw_text=item.get("raw_text") or text[:4000],
                        extraction_confidence=item.get("confidence"),
                    )
                )


def create_mock_corpus(db: Session) -> None:
    company = db.scalar(select(Company).where(Company.scrip_code == "540222"))
    if not company:
        return
    sample_path = Path("data/mock_laurus_3qfy25_transcript.txt")
    if not sample_path.exists():
        sample_path.write_text(
            "V.V. Ravi Kumar: Thank you. On margins, we expect to see improvement in Q4 as the new CDMO block comes online and utilization improves.\n\n"
            "Neha Manpuria (JPMorgan): My question is on the CDMO pipeline and capacity utilization for the next two quarters.\n\n"
            "V.V. Ravi Kumar: We have added three new molecules this quarter and see healthy traction in CDMO demand.\n",
            encoding="utf-8",
        )
    event = db.scalar(select(Event).where(Event.bse_filing_id == "MOCK-LAURUS-3QFY25-CALL"))
    if not event:
        event = Event(company_id=company.id, bse_filing_id="MOCK-LAURUS-3QFY25-CALL", event_date=date(2025, 1, 23), event_type="concall", quarter="3QFY25", fy_year=2025, filing_url="")
        db.add(event)
        db.flush()
    document = db.scalar(select(Document).where(Document.event_id == event.id, Document.document_type == "concall_transcript"))
    if not document:
        document = Document(event_id=event.id, document_type="concall_transcript", bse_url="", storage_path=str(sample_path))
        db.add(document)
        db.flush()
    press_path = Path("data/mock_laurus_3qfy25_press_release.txt")
    if not press_path.exists():
        press_path.write_text(Path("sample_press_release.txt").read_text(errors="ignore") + "\nLaurus Labs 3QFY25 revenue 1547 EBITDA 278 PAT 152 basic EPS 2.81\n", encoding="utf-8")
    press_event = db.scalar(select(Event).where(Event.bse_filing_id == "MOCK-LAURUS-3QFY25-RESULTS"))
    if not press_event:
        press_event = Event(company_id=company.id, bse_filing_id="MOCK-LAURUS-3QFY25-RESULTS", event_date=date(2025, 1, 23), event_type="results", quarter="3QFY25", fy_year=2025, filing_url="")
        db.add(press_event)
        db.flush()
    press_doc = db.scalar(select(Document).where(Document.event_id == press_event.id, Document.document_type == "results_press_release"))
    if not press_doc:
        press_doc = Document(event_id=press_event.id, document_type="results_press_release", bse_url="", storage_path=str(press_path))
        db.add(press_doc)
        db.flush()
    db.commit()
    pipeline = PipelineService()
    pipeline.process_document(db, document)
    pipeline.process_document(db, press_doc)
