SECTION_KEYWORDS = {
    "financial_highlights": ["financial highlights", "standalone and consolidated", "statement of results", "quarter ended"],
    "operational_highlights": ["operational highlights", "business highlights", "key highlights"],
    "management_commentary": ["management commentary", "commenting on", "outlook", "management comments", "ceo said", "md said"],
}


def detect_section_type(title: str) -> str:
    lowered = title.lower()
    for section_type, keywords in SECTION_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return section_type
    return "other"


def parse_press_release_sections(text: str) -> list[dict]:
    blocks = [block.strip() for block in text.split("\n\n") if block.strip()]
    sections = []
    for index, block in enumerate(blocks):
        first_line = block.splitlines()[0] if block.splitlines() else ""
        section_type = detect_section_type(first_line + " " + block[:300])
        sections.append({"section_type": section_type, "section_order": index, "text": block})
    if not any(section["section_type"] == "management_commentary" for section in sections) and blocks:
        sections[0]["section_type"] = "management_commentary"
    return sections
