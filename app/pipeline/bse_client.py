import asyncio
from dataclasses import dataclass
from datetime import date, datetime

import httpx

from app.core.config import settings

BSE_ENDPOINT = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
BSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 IndiaIR MVP",
    "Referer": "https://www.bseindia.com/",
    "Accept": "application/json,text/plain,*/*",
}


@dataclass(frozen=True)
class BSEFiling:
    bse_filing_id: str
    filing_datetime: datetime
    filing_date: date
    category: str
    subcategory: str
    headline: str
    attachment_url: str | None
    scrip_code: str
    company_name: str


def parse_bse_datetime(value: str) -> datetime:
    return datetime.strptime(value, "%d-%b-%Y %H:%M:%S")


class BSEClient:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def fetch_filings(self, scrip_code: str, start_date: date, end_date: date) -> list[BSEFiling]:
        params = {
            "strCat": "-1",
            "strPrevDate": start_date.strftime("%Y%m%d"),
            "strToDate": end_date.strftime("%Y%m%d"),
            "strScrip": scrip_code,
            "strSearch": "P",
            "strType": "C",
        }
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=30, headers=BSE_HEADERS)
        try:
            for attempt in range(settings.max_retries):
                response = await client.get(BSE_ENDPOINT, params=params)
                if response.status_code == 429:
                    await asyncio.sleep(60)
                    continue
                if response.status_code >= 500 and attempt < settings.max_retries - 1:
                    await asyncio.sleep(settings.retry_backoff_seconds * (2**attempt))
                    continue
                response.raise_for_status()
                payload = response.json()
                return [self._parse_row(row) for row in payload.get("Table", [])]
            return []
        finally:
            if owns_client:
                await client.aclose()
            await asyncio.sleep(settings.bse_request_delay_seconds)

    def _parse_row(self, row: dict) -> BSEFiling:
        filing_datetime = parse_bse_datetime(row["DT_TM"])
        return BSEFiling(
            bse_filing_id=str(row["NEWSID"]),
            filing_datetime=filing_datetime,
            filing_date=filing_datetime.date(),
            category=row.get("CATEGORYNAME") or "",
            subcategory=row.get("SUBCATEGORYNAME") or "",
            headline=row.get("HEADLINE") or "",
            attachment_url=row.get("ATTACHMENT") or None,
            scrip_code=str(row.get("SCRIP_CD") or ""),
            company_name=row.get("COMPANY_NAME") or "",
        )
