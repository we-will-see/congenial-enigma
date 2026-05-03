import re

SPEAKER_PATTERNS = [
    re.compile(r"^([A-Z][A-Za-z\s\.\-]+?):\s(.*)", re.IGNORECASE),
    re.compile(r"^([A-Z][A-Z\s\.]+):\s(.*)"),
    re.compile(r"^([A-Za-z\s\.\-]+?)\s*\(([A-Za-z\s&\.]+?)\):\s(.*)", re.IGNORECASE),
    re.compile(r"^(Management|Analyst|Moderator|Operator):\s(.*)", re.IGNORECASE),
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
MODERATOR_SIGNALS = ["moderator", "operator", "good morning", "good evening", "welcome", "next question", "next participant"]


def _split_speaker(raw: str) -> tuple[str, str | None]:
    match = re.match(r"^(.*?)\s*\((.*?)\)$", raw.strip())
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return raw.strip(), None


def classify_speaker(raw: str, text: str, speaker_org: str | None = None) -> str:
    blob = f"{raw} {text[:180]}".lower()
    if any(signal in blob for signal in MODERATOR_SIGNALS):
        return "moderator"
    if any(signal in blob for signal in MANAGEMENT_SIGNALS):
        return "management"
    if any(signal in blob for signal in ANALYST_SIGNALS):
        return "analyst"
    if speaker_org:
        return "analyst"
    if raw.lower() in {"management", "analyst", "moderator", "operator"}:
        return "moderator" if raw.lower() in {"moderator", "operator"} else raw.lower()
    return "unknown"


def parse_transcript(text: str) -> list[dict]:
    turns: list[dict] = []
    current: dict | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        matched = None
        for pattern in SPEAKER_PATTERNS:
            matched = pattern.match(stripped)
            if matched:
                break
        if matched:
            if current and current["text"].strip():
                turns.append(current)
            if len(matched.groups()) == 3:
                raw = f"{matched.group(1).strip()} ({matched.group(2).strip()})"
                body = matched.group(3)
            else:
                raw = matched.group(1).strip()
                body = matched.group(2)
            speaker_name, speaker_org = _split_speaker(raw)
            speaker_role = classify_speaker(raw, body, speaker_org=speaker_org)
            current = {
                "turn_index": len(turns),
                "speaker_raw": raw,
                "speaker_name": speaker_name,
                "speaker_role": speaker_role,
                "speaker_org": speaker_org,
                "speaker_title": None,
                "text": body.strip(),
                "word_count": 0,
            }
        elif current:
            current["text"] += " " + stripped
    if current and current["text"].strip():
        turns.append(current)
    for index, turn in enumerate(turns):
        turn["turn_index"] = index
        turn["word_count"] = len(turn["text"].split())
    return turns
