from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from anthropic import Anthropic

from api.core.config import get_settings

MGMT_CHANGE_SYSTEM_PROMPT = """
You extract structured management change records from Indian listed company regulatory filings.
Respond ONLY with a JSON array. No preamble, no markdown, no explanation.

For each change mentioned, return one object with these exact fields:
{
    "person_name": string,
    "role": string,
    "role_category": string,
    "change_type": string,
    "effective_date": string | null,
    "reason": string | null,
    "din": string | null,
    "confidence": float
}
"""


class ManagementChangeParser:
    def parse(self, text: str, filing_date: date) -> list[dict[str, Any]]:
        settings = get_settings()
        if settings.anthropic_api_key:
            try:
                client = Anthropic(api_key=settings.anthropic_api_key)
                message = client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=1000,
                    system=MGMT_CHANGE_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": text[:12000]}],
                )
                payload = message.content[0].text
                return json.loads(payload)
            except Exception:
                pass
        return self._regex_fallback(text, filing_date)

    def _regex_fallback(self, text: str, filing_date: date) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        change_type = "appointment" if re.search(r"appoint", text, re.I) else "resignation" if re.search(r"resign", text, re.I) else "cessation"
        role_match = re.search(r"(Chief Financial Officer|Chief Executive Officer|Managing Director|Company Secretary|Independent Director|Director|CFO|CEO|MD)", text, re.I)
        person_match = re.search(r"(?:Mr\.|Ms\.|Mrs\.|Dr\.)\s+([A-Z][A-Za-z .]+)", text)
        if person_match and role_match:
            role = role_match.group(1)
            records.append(
                {
                    "person_name": person_match.group(0).strip(),
                    "role": role,
                    "role_category": self._role_category(role),
                    "change_type": change_type,
                    "effective_date": None,
                    "reason": None,
                    "din": None,
                    "confidence": 0.55,
                    "raw_text": text[:4000],
                    "filing_date": filing_date,
                }
            )
        return records

    def _role_category(self, role: str) -> str:
        probe = role.lower()
        if any(token in probe for token in ["md", "ceo", "cfo", "company secretary", "chief"]):
            return "kmp"
        if "independent" in probe:
            return "board_independent"
        if "executive" in probe:
            return "board_executive"
        return "board_non_executive"
