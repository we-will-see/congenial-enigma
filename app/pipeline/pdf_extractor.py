import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import fitz
import pytesseract
from PIL import Image

from app.core.config import settings


@dataclass
class ExtractionResult:
    text: str
    page_texts: list[str]
    page_count: int
    pdf_type: str
    method: str
    quality_score: float
    quality_flags: list[str]


def clean_text(text: str) -> str:
    replacements = {"\ufb01": "fi", "\ufb02": "fl", "\u2019": "'", "\u2013": "-", "\u2014": "-"}
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def quality_score(text: str) -> float:
    if not text:
        return 0.0
    printable = sum(1 for char in text if char.isprintable() or char in "\n\t")
    words = re.findall(r"[A-Za-z][A-Za-z\-']+", text)
    non_ascii = sum(1 for char in text if ord(char) > 127)
    printable_ratio = printable / len(text)
    word_ratio = min(1.0, len(words) / max(1, len(text) / 8))
    ascii_ratio = 1.0 - (non_ascii / len(text))
    return round(max(0.0, min(1.0, (printable_ratio * 0.45) + (word_ratio * 0.4) + (ascii_ratio * 0.15))), 4)


def detect_pdf_type(pdf_path: str | Path) -> tuple[str, list[str], float, int]:
    doc = fitz.open(pdf_path)
    page_texts = [page.get_text("text") for page in doc]
    page_count = len(page_texts)
    avg_chars = sum(len(text) for text in page_texts) / max(1, page_count)
    score = quality_score("\n".join(page_texts))
    scanned_pages = sum(1 for text in page_texts if len(text.strip()) < settings.min_chars_per_page)
    if avg_chars < settings.min_chars_per_page:
        pdf_type = "scanned"
    elif scanned_pages / max(1, page_count) > 0.3:
        pdf_type = "mixed"
    else:
        pdf_type = "text"
    flags = []
    if score < settings.min_text_quality_score:
        flags.append("LOW_TEXT_QUALITY")
    return pdf_type, flags, score, page_count


def extract_text_pymupdf(pdf_path: str | Path) -> list[str]:
    doc = fitz.open(pdf_path)
    return [clean_text(page.get_text("text")) for page in doc]


def extract_text_tesseract(pdf_path: str | Path) -> list[str]:
    doc = fitz.open(pdf_path)
    texts = []
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        texts.append(clean_text(pytesseract.image_to_string(image, lang="eng")))
    return texts


def extract_pdf(pdf_path: str | Path) -> ExtractionResult:
    pdf_type, flags, initial_score, page_count = detect_pdf_type(pdf_path)
    if pdf_type == "text" and initial_score >= settings.min_text_quality_score:
        page_texts = extract_text_pymupdf(pdf_path)
        method = "pymupdf"
    else:
        page_texts = extract_text_tesseract(pdf_path)
        method = "tesseract"
    text = clean_text("\n\n".join(page_texts))
    score = quality_score(text)
    word_counts = [len(page.split()) for page in page_texts]
    if any(count < 50 for count in word_counts):
        flags.append("LOW_WORD_COUNT_PAGE")
    non_ascii_ratio = (sum(1 for char in text if ord(char) > 127) / max(1, len(text))) if text else 1.0
    if non_ascii_ratio > 0.15:
        flags.append("HIGH_NON_ASCII_RATIO")
    if score < settings.min_text_quality_score:
        flags.append("LOW_QUALITY_EXTRACTION")
    return ExtractionResult(text=text, page_texts=page_texts, page_count=page_count, pdf_type=pdf_type, method=method, quality_score=score, quality_flags=sorted(set(flags)))
