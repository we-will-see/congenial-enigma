import json

from anthropic import Anthropic

from app.core.config import settings

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

Role category rules:
- MD, CEO, CFO, COO, CS (Company Secretary), CTO -> kmp
- Whole-time Director, Executive Director -> board_executive
- Non-Executive Non-Independent Director -> board_non_executive
- Independent Director -> board_independent

Do NOT infer reason if not explicitly stated. Do NOT assume effective date from filing date.
"""


def extract_management_changes(text: str) -> list[dict]:
    if not settings.anthropic_api_key:
        return []
    client = Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=1000,
        system=MGMT_CHANGE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text[:12000]}],
    )
    payload = response.content[0].text
    return json.loads(payload)
