from __future__ import annotations

import re

CATEGORY_MAP: dict[tuple[str, str], str] = {
    ("Concall", "Transcript"): "concall_transcript",
    ("Concall", "Audio"): "other",
    ("Investor Presentation", ""): "investor_presentation",
    ("Investor Presentation", "Investor Presentation"): "investor_presentation",
    ("Results", "Financial Results"): "results_press_release",
    ("Results", "Quarterly Financial Results"): "results_press_release",
    ("Results", "Unaudited Financial Results"): "results_press_release",
    ("Results", "Audited Financial Results"): "results_press_release",
    ("Board Meeting", "Outcome of Board Meeting"): "board_meeting_outcome",
    ("Reg36(1)(2)", "Outcome of Board Meeting"): "board_meeting_outcome",
    ("Change in Directors/Key Managerial Personnel", ""): "management_change",
    ("Change in Directors/Key Managerial Personnel/Auditor/Compliance Officer", ""): "management_change",
    ("Appointment", ""): "management_change",
    ("Resignation", ""): "management_change",
}

HEADLINE_PATTERNS: dict[str, list[str]] = {
    "concall_transcript": ["transcript", "concall", "earnings call transcript"],
    "investor_presentation": ["investor presentation", "analyst day", "investor day"],
    "results_press_release": ["financial results", "quarterly results", "annual results"],
    "management_change": ["appointment", "resignation", "cessation", "director", "kmp", "cfo", "ceo", "md "],
}


class DocumentClassifier:
    def classify(self, category: str | None, subcategory: str | None, headline: str | None) -> str:
        key = ((category or "").strip(), (subcategory or "").strip())
        if key in CATEGORY_MAP:
            return CATEGORY_MAP[key]
        text = (headline or "").lower()
        for document_type, patterns in HEADLINE_PATTERNS.items():
            if any(re.search(rf"\b{re.escape(pattern)}\b", text) for pattern in patterns):
                return document_type
        return "other"
