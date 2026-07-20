from app.core.config import settings


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not settings.openai_api_key or not texts:
        return []
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    vectors: list[list[float]] = []
    for start in range(0, len(texts), 100):
        response = client.embeddings.create(model=settings.embedding_model, input=texts[start : start + 100])
        vectors.extend(item.embedding for item in response.data)
    return vectors
