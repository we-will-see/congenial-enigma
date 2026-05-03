def parse_slides(page_texts: list[str]) -> list[dict]:
    slides = []
    for index, text in enumerate(page_texts, start=1):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        title = lines[0] if lines else None
        body = "\n".join(lines[1:]) if len(lines) > 1 else text.strip()
        slides.append({"slide_number": index, "title": title, "body_text": body})
    return slides
