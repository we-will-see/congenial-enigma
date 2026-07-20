# Repository guide

`app/` is the only application code tree.

## Runtime map

- `app/main.py` — FastAPI bootstrap
- `app/api/v1/` — HTTP routes for documents, notebooks, companies, and deterministic extracts
- `app/models/` — SQLAlchemy document, page, chunk, notebook, and derived-data models
- `app/pipeline/` — BSE intake, file storage, PDF/OCR extraction, structural parsing, chunking, and embeddings
- `app/services/` — manual intake, notebook lifecycle, and notebook search use cases
- `app/search_notebook.py` — stable Python retrieval entry point for external consumers
- `alembic/` — PostgreSQL and pgvector migrations
- `scripts/seed_companies.py` — canonical company seed command
- `tests/` — deterministic unit and contract tests

## Responsibility boundary

Enigma owns documents and evidence retrieval. Agent orchestration, investment analysis, generated answers, and user interfaces belong in the consuming system (currently planned as `glowing-garbanzo`).

All retrieval results must remain traceable to `document_id`, page range, and `chunk_id`. New parsers should persist their raw page source before adding derived structures.
