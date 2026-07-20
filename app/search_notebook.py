"""Stable Python entry point for consumers such as glowing-garbanzo."""

from app.schemas.notebooks import EvidencePack, NotebookSearchRequest
from app.services.notebook_search import QueryEmbeddingProvider, search_notebook

__all__ = ["EvidencePack", "NotebookSearchRequest", "QueryEmbeddingProvider", "search_notebook"]
