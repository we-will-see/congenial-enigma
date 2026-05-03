from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import fitz
import pytesseract
from PIL import Image

from api.core.config import get_settings


@dataclass
class ExtractionResult:
    text: str
    pdf_type: str
    method: str
    page_count: int
    quality_score: float
    quality_flags: list[str]


class TextExtractor:
    def __init__(self) -> None:
        self.settings = get_settings()

    def extract(self, pdf_path: str) -> ExtractionResult:
        try:
            text, page_count, page_lengths = self._extract_pymupdf(pdf_path)
        except Exception as exc:
            return ExtractionResult("", "scanned", "pymupdf", 0, 0.0, [f"PYMUPDF_FAILED:{exc}"])
        quality_score = self._quality_score(text)
        avg_chars = sum(page_lengths) / max(len(page_lengths), 1)
        pdf_type = "text"
        flags: list[str] = []
        if avg_chars < self.settings.min_chars_per_page:
            pdf_type = "scanned"
            flags.append("LOW_CHARS_PER_PAGE")
        if quality_score < self.settings.min_text_quality_score:
            flags.append("LOW_TEXT_QUALITY")
        if flags:
            ocr_text = self._extract_ocr(pdf_path)
            if len(ocr_text) > len(text):
                text = ocr_text
                quality_score = self._quality_score(text)
                return ExtractionResult(self._clean(text), pdf_type, "tesseract", page_count, quality_score, flags)
        return ExtractionResult(self._clean(text), pdf_type, "pymupdf", page_count, quality_score, flags)

    def _extract_pymupdf(self, pdf_path: str) -> tuple[str, int, list[int]]:
        doc = fitz.open(pdf_path)
        page_texts = [page.get_text("text") for page in doc]
        return "\n".join(page_texts), doc.page_count, [len(text) for text in page_texts]

    def _extract_ocr(self, pdf_path: str) -> str:
        try:
            doc = fitz.open(pdf_path)
            texts: list[str] = []
            for page in doc:
                pix = page.get_pixmap(dpi=300)
                image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                texts.append(pytesseract.image_to_string(image, lang="eng"))
            return "\n".join(texts)
        except Exception:
            return Path(pdf_path).read_text(errors="ignore") if Path(pdf_path).exists() else ""

    def _clean(self, text: str) -> str:
        text = unicodedata.normalize("NFKC", text)
        text = text.replace("\ufb01", "fi").replace("\ufb02", "fl")
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    def _quality_score(self, text: str) -> float:
        if not text:
            return 0.0
        printable = sum(1 for ch in text if ch.isprintable() or ch.isspace())
        wordish = len(re.findall(r"[A-Za-z0-9₹%.,-]{2,}", text))
        return round(min((printable / len(text)) * min(wordish / max(len(text.split()), 1), 1.0), 1.0), 4)
