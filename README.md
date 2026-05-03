# IndiaIR MVP

IndiaIR is a FastAPI + Streamlit MVP for ingesting BSE investor-relations filings, extracting document content, indexing keyword and semantic search, and answering RAG questions with citations.

## Stack

- Python 3.11
- FastAPI 0.111, SQLAlchemy 2.0, Alembic 1.13
- PostgreSQL 16 + pgvector, Elasticsearch 8.13
- PyMuPDF, pdfplumber, pytesseract, camelot
- OpenAI `text-embedding-3-small` for embeddings
- Anthropic Claude for RAG and structured fallback extraction
- Streamlit 1.35, Plotly, Pandas

## Setup

```bash
cp .env.example .env
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d postgres elasticsearch
alembic upgrade head
python scripts/seed_companies.py
python scripts/mock_ingest.py
```

Set `OPENAI_API_KEY` for live embeddings and `ANTHROPIC_API_KEY` for Claude-backed RAG. Without keys, the app uses deterministic local embeddings and an extractive fallback answer so the MVP remains runnable.

## Run

```bash
uvicorn api.main:app --reload --port 8000
streamlit run ui/app.py
```

Backend health check:

```bash
curl http://localhost:8000/api/v1/health
```

## Main Endpoints

- `GET /api/v1/health`
- `GET /api/v1/companies`
- `GET /api/v1/companies/{id}`
- `GET /api/v1/companies/{id}/events`
- `GET /api/v1/companies/{id}/financials`
- `GET /api/v1/management-changes`
- `POST /api/v1/search/keyword`
- `POST /api/v1/search/semantic`
- `POST /api/v1/qa/ask`
- `POST /api/v1/pipeline/mock-ingest`
- `POST /api/v1/pipeline/process/{document_id}`

## Pipeline

The pipeline modules are under `ingestion/`, `extraction/`, `indexing/`, and `services/`.

- `BSEPoller` calls the BSE corporate filings API with the TECH_SPEC parameters and stores events/documents idempotently.
- `DocumentClassifier` maps BSE category/subcategory and headline keywords to the required document types.
- `TextExtractor` uses PyMuPDF first and Tesseract OCR if text quality is low.
- Parsers write turns, slides, press-release sections, management changes, and P&L financials.
- `EmbeddingIndexer` stores pgvector embeddings using OpenAI when configured, with a local fallback for development.
- `ESIndexer` writes the specified Elasticsearch mapping and content documents.

## Development Notes

Run a minimal verification pass:

```bash
python -m compileall api ingestion extraction indexing services scripts ui
pytest
```

The sample files included in the repo are placeholders, so `scripts/mock_ingest.py` creates a small Laurus Labs 3QFY25 corpus that exercises transcript parsing, financial extraction, search, semantic retrieval, and Q&A citations.
