import hashlib
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.core.config import settings


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def download_pdf(url: str, company_scrip: str, filing_id: str) -> tuple[Path, str]:
    settings.local_storage_path.mkdir(parents=True, exist_ok=True)
    suffix = Path(urlparse(url).path).suffix or ".pdf"
    path = settings.local_storage_path / company_scrip / f"{filing_id.replace('/', '_')}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(url)
            response.raise_for_status()
            path.write_bytes(response.content)
    return path, sha256_file(path)
