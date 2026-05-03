from __future__ import annotations

import re
from dataclasses import dataclass

SPEAKER_PATTERNS = [
    re.compile(r"^([A-Z][A-Za-z\s\.\-]+?):\s(.*)", re.I),
    re.compile(r"^([A-Z][A-Z\s\.]+):\s(.*)"),
    re.compile(r"^([A-Za-z\s\.\-]+?)\s*\(([A-Za-z\s]+?)\):\s(.*)", re.I),
    re.compile(r"^(Management|Analyst|Moderator|Operator):\s(.*)", re.I),
]

MANAGEMENT_SIGNALS = [
    "managing director",
    "md &",
    "chief executive",
    "ceo",
    "chief financial",
    "cfo",
    "chief operating",
    "coo",
    "president",
    "vice president",
    "vp ",
    "head of",
    "director",
    "chairman",
    "whole-time director",
]
ANALYST_SIGNALS = ["analyst", "research", "securities", "capital", "asset management", "investments", "fund", "partners", "advisors", "bank", "broking"]
MODERATOR_SIGNALS = ["moderator", "operator", "welcome", "next question", "next participant"]


@dataclass
class ParsedTurn:
    turn_index: int
    speaker_raw: str | None
    speaker_name: str | None
    speaker_role: str
    speaker_org: str | None
    speaker_title: str | None
    text: str
    word_count: int


class TranscriptParser:
    def parse(self, text: str) -> list[ParsedTurn]:
        turns: list[ParsedTurn] = []
        current: dict[str, str | None] | None = None
        body: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            header = self._match_header(line)
            if header:
                if current and body:
                    turns.append(self._build_turn(len(turns), current, " ".join(body)))
                current, first_text = header
                body = [first_text] if first_text else []
            elif current:
                body.append(line)
        if current and body:
            turns.append(self._build_turn(len(turns), current, " ".join(body)))
        return turns

    def _match_header(self, line: str) -> tuple[dict[str, str | None], str] | None:
        parenthetical = SPEAKER_PATTERNS[2].match(line)
        if parenthetical:
            speaker = parenthetical.group(1).strip()
            org = parenthetical.group(2).strip()
            return {"speaker_raw": f"{speaker} ({org})", "speaker_name": speaker, "speaker_org": org}, parenthetical.group(3).strip()
        for pattern in (SPEAKER_PATTERNS[0], SPEAKER_PATTERNS[1], SPEAKER_PATTERNS[3]):
            match = pattern.match(line)
            if match:
                speaker = match.group(1).strip()
                return {"speaker_raw": speaker, "speaker_name": speaker, "speaker_org": None}, match.group(2).strip()
        return None

    def _build_turn(self, index: int, speaker: dict[str, str | None], text: str) -> ParsedTurn:
        role, title = self._classify_role(speaker.get("speaker_raw") or "", text)
        return ParsedTurn(
            turn_index=index,
            speaker_raw=speaker.get("speaker_raw"),
            speaker_name=speaker.get("speaker_name"),
            speaker_role=role,
            speaker_org=speaker.get("speaker_org"),
            speaker_title=title,
            text=text.strip(),
            word_count=len(text.split()),
        )

    def _classify_role(self, speaker: str, text: str) -> tuple[str, str | None]:
        probe = f"{speaker} {text[:240]}".lower()
        if any(sig in probe for sig in MODERATOR_SIGNALS):
            return "moderator", None
        if any(sig in probe for sig in MANAGEMENT_SIGNALS):
            title = "CFO" if "cfo" in probe or "chief financial" in probe else None
            return "management", title
        if any(sig in probe for sig in ANALYST_SIGNALS) or "(" in speaker:
            return "analyst", None
        return "unknown", None
