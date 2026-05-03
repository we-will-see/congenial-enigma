from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class PressReleaseSectionItem:
    section_type: str
    section_order: int
    text: str


class PressReleaseParser:
    def parse(self, text: str) -> list[PressReleaseSectionItem]:
        blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if len(block.strip()) > 20]
        if not blocks:
            return []
        sections: list[PressReleaseSectionItem] = []
        for idx, block in enumerate(blocks):
            lower = block.lower()
            if any(term in lower for term in ["financial highlight", "revenue", "ebitda", "profit after tax", "pat"]):
                section_type = "financial_highlights"
            elif any(term in lower for term in ["comment", "outlook", "guidance", "management"]):
                section_type = "management_commentary"
            elif any(term in lower for term in ["operational", "capacity", "utilisation", "utilization"]):
                section_type = "operational_highlights"
            else:
                section_type = "other"
            sections.append(PressReleaseSectionItem(section_type, idx, block))
        return sections
