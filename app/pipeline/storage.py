import hashlib
import mimetypes
import re
from pathlib import Path

import httpx

from app.core.config import settings


ALLOWED_UPLOADS = {
    ".pdf": {"application/pdf", "application/x-pdf", "application/octet-stream"},
    ".txt": {"text/plain", "application/octet-stream"},
    ".md": {"text/markdown", "text/x-markdown", "text/plain", "application/octet-stream"},
}


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sanitize_filename(filename: str) -> str:
    """Return a display-safe filename with no path components."""
    name = Path(filename.replace("\\", "/")).name.strip()
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:240] or "document"


def validate_upload(filename: str, content_type: str | None, content: bytes) -> tuple[str, str]:
    safe_name = sanitize_filename(filename)
    suffix = Path(safe_name).suffix.lower()
    if suffix not in ALLOWED_UPLOADS:
        raise ValueError("Only PDF, TXT, and Markdown documents are supported")
    if not content:
        raise ValueError("The uploaded document is empty")
    if len(content) > settings.max_upload_bytes:
        max_mb = settings.max_upload_bytes // (1024 * 1024)
        raise ValueError(f"The uploaded document exceeds the {max_mb} MB limit")
    normalized_type = (content_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream").split(";", 1)[0].lower()
    if normalized_type not in ALLOWED_UPLOADS[suffix]:
        raise ValueError(f"Content type {normalized_type!r} does not match the {suffix} file extension")
    if suffix == ".pdf" and not content.startswith(b"%PDF-"):
        raise ValueError("The uploaded file does not contain a valid PDF header")
    if suffix in {".txt", ".md"}:
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Text and Markdown uploads must use UTF-8 encoding") from exc
    return safe_name, normalized_type


def store_uploaded_document(
    content: bytes,
    filename: str,
    content_type: str | None,
    company_key: str,
) -> tuple[Path, str, str, str]:
    """Validate and persist a manual upload under a content-addressed path."""
    safe_name, normalized_type = validate_upload(filename, content_type, content)
    file_hash = sha256_bytes(content)
    suffix = Path(safe_name).suffix.lower()
    safe_company_key = sanitize_filename(company_key)
    path = settings.local_storage_path / "manual" / safe_company_key / file_hash[:2] / f"{file_hash}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(content)
    return path, file_hash, safe_name, normalized_type


def store_text_document(text: str, title: str, company_key: str) -> tuple[Path, str, str, str]:
    filename = f"{sanitize_filename(title)}.txt"
    return store_uploaded_document(text.encode("utf-8"), filename, "text/plain", company_key)


async def download_pdf(url: str, company_scrip: str, filing_id: str) -> tuple[Path, str]:
    company_key = sanitize_filename(company_scrip)
    filing_key = sanitize_filename(filing_id)
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(url)
        response.raise_for_status()
    content = response.content
    if len(content) > settings.max_upload_bytes:
        max_mb = settings.max_upload_bytes // (1024 * 1024)
        raise ValueError(f"BSE filing {filing_key} exceeds the {max_mb} MB document limit")
    if not content.startswith(b"%PDF-"):
        raise ValueError(f"BSE filing {filing_key} did not return a valid PDF")
    file_hash = sha256_bytes(content)
    path = settings.local_storage_path / "bse" / company_key / file_hash[:2] / f"{file_hash}.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(content)
    return path, file_hash
