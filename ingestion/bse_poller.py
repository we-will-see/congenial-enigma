from __future__ import annotations

import asyncio
import hashlib
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.core.config import get_settings
from api.db.models import Company, Document, Event
from ingestion.document_classifier import DocumentClassifier

log = structlog.get_logger(__name__)
BSE_ENDPOINT = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"


def parse_bse_datetime(value: str) -> datetime:
    return datetime.strptime(value, "%d-%b-%Y %H:%M:%S")


def event_type_for_document(document_type: str) -> str:
    return {
        "concall_transcript": "concall",
        "investor_presentation": "presentation",
        "results_press_release": "results",
        "management_change": "mgmt_change",
    }.get(document_type, "other")


class BSEPoller:
    def __init__(self, db: Session, client: httpx.AsyncClient | None = None) -> None:
        self.db = db
        self.settings = get_settings()
        self.client = client
        self.classifier = DocumentClassifier()

    async def poll_company(self, company: Company, start_date: date, end_date: date, mock: bool = False) -> list[Document]:
        rows = self._mock_rows(company) if mock else await self._fetch_filings(company.scrip_code, start_date, end_date)
        documents: list[Document] = []
        for row in rows:
            documents.append(await self._upsert_filing(company, row, mock=mock))
            await asyncio.sleep(self.settings.bse_request_delay_seconds)
        self.db.commit()
        return documents

    async def poll_all_companies(self, start_date: date, end_date: date, mock: bool = False) -> list[Document]:
        companies = self.db.scalars(select(Company).where(Company.active.is_(True))).all()
        out: list[Document] = []
        for company in companies:
            try:
                out.extend(await self.poll_company(company, start_date, end_date, mock=mock))
            except Exception as exc:
                log.error("bse_poll_company_failed", scrip_code=company.scrip_code, error=str(exc))
        return out

    async def _fetch_filings(self, scrip_code: str, start_date: date, end_date: date) -> list[dict[str, Any]]:
        params = {
            "strCat": "-1",
            "strPrevDate": start_date.strftime("%Y%m%d"),
            "strToDate": end_date.strftime("%Y%m%d"),
            "strScrip": scrip_code,
            "strSearch": "P",
            "strType": "C",
        }
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.bseindia.com/"}
        client = self.client or httpx.AsyncClient(timeout=30, headers=headers)
        close_client = self.client is None
        try:
            for attempt in range(self.settings.max_retries):
                try:
                    response = await client.get(BSE_ENDPOINT, params=params)
                    response.raise_for_status()
                    payload = response.json()
                    return payload.get("Table", []) or []
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 429:
                        await asyncio.sleep(60)
                    elif exc.response.status_code >= 500:
                        await asyncio.sleep(self.settings.retry_backoff_seconds * (2**attempt))
                    else:
                        raise
                except httpx.TimeoutException:
                    await asyncio.sleep(self.settings.retry_backoff_seconds * (2**attempt))
            return []
        finally:
            if close_client:
                await client.aclose()

    async def _upsert_filing(self, company: Company, row: dict[str, Any], mock: bool = False) -> Document:
        filing_id = str(row.get("NEWSID"))
        existing = self.db.scalar(select(Document).join(Event).where(Event.bse_filing_id == filing_id))
        if existing:
            return existing
        document_type = self.classifier.classify(row.get("CATEGORYNAME"), row.get("SUBCATEGORYNAME"), row.get("HEADLINE"))
        event_date = parse_bse_datetime(row["DT_TM"]).date() if row.get("DT_TM") else date.today()
        event = Event(
            company_id=company.id,
            bse_filing_id=filing_id,
            event_date=event_date,
            event_type=event_type_for_document(document_type),
            filing_url=row.get("ATTACHMENT"),
        )
        self.db.add(event)
        self.db.flush()
        storage_path = await self._download_pdf(company.scrip_code, filing_id, row.get("ATTACHMENT"), mock)
        file_hash = self._hash_file(storage_path) if Path(storage_path).exists() else None
        document = Document(
            event_id=event.id,
            document_type=document_type,
            bse_url=row.get("ATTACHMENT"),
            storage_path=storage_path,
            file_hash=file_hash,
        )
        self.db.add(document)
        self.db.flush()
        return document

    async def _download_pdf(self, scrip_code: str, filing_id: str, url: str | None, mock: bool) -> str:
        folder = self.settings.local_storage_path / scrip_code
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{filing_id}.pdf"
        if path.exists():
            return str(path)
        if mock or not url:
            path.write_bytes(b"%PDF-1.4\n% IndiaIR mock filing\n")
            return str(path)
        async with httpx.AsyncClient(timeout=30, headers={"User-Agent": "Mozilla/5.0"}) as client:
            response = await client.get(url)
            response.raise_for_status()
            path.write_bytes(response.content)
        return str(path)

    def _hash_file(self, path: str) -> str:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def _mock_rows(self, company: Company) -> list[dict[str, Any]]:
        now = datetime.now().strftime("%d-%b-%Y %H:%M:%S").upper()
        return [
            {
                "NEWSID": f"MOCK-{company.scrip_code}-TRANSCRIPT",
                "DT_TM": now,
                "CATEGORYNAME": "Concall",
                "SUBCATEGORYNAME": "Transcript",
                "HEADLINE": f"{company.name} Earnings Call Transcript",
                "ATTACHMENT": "",
                "SCRIP_CD": company.scrip_code,
                "COMPANY_NAME": company.name,
            }
        ]
