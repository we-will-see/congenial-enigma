from __future__ import annotations

import hashlib
import math

from openai import OpenAI

from api.core.config import get_settings


class EmbeddingGenerator:
    model = "text-embedding-3-small"
    dimensions = 1536

    def __init__(self) -> None:
        settings = get_settings()
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    def embed(self, text: str) -> list[float]:
        if self.client:
            response = self.client.embeddings.create(model=self.model, input=text)
            return response.data[0].embedding
        return self._local_embedding(text)

    def _local_embedding(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:2], "big") % self.dimensions
            vector[idx] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]
