# ConGENIAl Enigma

Enigma is the document-intelligence and retrieval service for the research system. It owns document acquisition, immutable file storage, extraction, page-aware chunking, notebook membership, embeddings, and cited retrieval.

It deliberately does **not** generate research answers, run analyst agents, or ship a frontend. `glowing-garbanzo` can consume Enigma's `EvidencePack` and own those responsibilities.

## MVP architecture

```mermaid
flowchart TD
    A["BSE or manual upload"] --> B["Content-addressed file storage"]
    B --> C["PDF text or OCR extraction"]
    C --> D["Pages and deterministic structures"]
    D --> E["Page-aware chunks"]
    E --> F["PostgreSQL FTS + pgvector"]
    F --> G["Notebook-scoped EvidencePack"]
```

PostgreSQL is the only stateful service. Keyword retrieval uses PostgreSQL full-text search; semantic retrieval uses pgvector when embeddings are available. Hybrid search falls back to keyword search when no embedding provider is configured.

## What Enigma stores

- Source files with SHA-256 hashes and source, rights, uploader, and version metadata
- Extracted text per page with parser provenance and quality signals
- Page-citable chunks with optional OpenAI embeddings
- Structured transcript turns, presentation slides, press-release sections, financial rows, and management changes
- Notebooks, notebook-document membership, and tags

Manual intake accepts PDF, UTF-8 TXT, and Markdown files up to 50 MB, plus pasted text. Re-uploading the same content for the same company reuses the existing document and can attach it to additional notebooks.

## Run locally

Requirements: Python 3.11+ and Docker Compose.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
docker compose up -d postgres
alembic upgrade head
python scripts/seed_companies.py
uvicorn app.main:app --reload --port 8000
```

`OPENAI_API_KEY` is optional. Without it, ingestion and notebook keyword retrieval still work. Scanned PDFs require the `tesseract` executable on the host.

When upgrading an existing database, migration `0002` removes the legacy, non-page-citable embeddings table. Re-run `python -m app.pipeline.cli process-document <id>` for existing documents that should become searchable.

Interactive API documentation is available at `http://localhost:8000/docs`.

## Manual document intake

Create a notebook:

```bash
curl -X POST http://localhost:8000/api/v1/notebooks \
  -H 'Content-Type: application/json' \
  -d '{"name":"Laurus quarterly research","namespace_id":"default"}'
```

Upload a file and process it immediately:

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F company_id=1 \
  -F document_type=concall_transcript \
  -F title='Q1 FY27 earnings call' \
  -F quarter=Q1FY27 \
  -F notebook_ids=1 \
  -F process_now=true \
  -F embed=true \
  -F file=@transcript.pdf
```

Add pasted text:

```bash
curl -X POST http://localhost:8000/api/v1/documents/add-text \
  -H 'Content-Type: application/json' \
  -d '{
    "company_id": 1,
    "title": "Management meeting notes",
    "text": "Management expects the new plant to reach commercial production in Q4.",
    "document_type": "other",
    "notebook_ids": [1],
    "process_now": true
  }'
```

Files can be stored without synchronous extraction by setting `process_now=false`, then processed with `POST /api/v1/documents/{document_id}/process` and body `{"embed":true}`.

## Notebook retrieval contract

Use the HTTP endpoint:

```bash
curl -X POST http://localhost:8000/api/v1/notebooks/1/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"What did management say about capacity ramp-up?","mode":"hybrid","top_k":8}'
```

Or import the stable Python entry point:

```python
from app.db.session import SessionLocal
from app.search_notebook import NotebookSearchRequest, search_notebook

with SessionLocal() as db:
    evidence_pack = search_notebook(
        db,
        notebook_id=1,
        request=NotebookSearchRequest(query="capacity ramp-up", top_k=8),
    )
```

`EvidencePack` contains ranked source chunks, stable document/page/chunk citations, company and document metadata, and retrieval methods. It contains no generated answer.

## Main API surface

- `POST /api/v1/documents/upload`
- `POST /api/v1/documents/add-text`
- `POST /api/v1/documents/{id}/process`
- `GET /api/v1/documents/{id}`
- `GET /api/v1/documents/{id}/pages`
- `POST /api/v1/notebooks`
- `PUT /api/v1/notebooks/{id}/documents/{document_id}`
- `GET /api/v1/notebooks/{id}/documents`
- `POST /api/v1/notebooks/{id}/search`
- `GET /api/v1/companies`
- `GET /api/v1/health`

## Verification

```bash
python -m compileall app scripts tests
pytest
DATABASE_URL=postgresql://indiair:password@localhost:5432/indiair alembic upgrade head --sql
```

The canonical application is `app/`. The previous duplicate backend packages, Elasticsearch index, Streamlit frontends, and answer-generation RAG service were removed so Enigma has one clear responsibility and one runtime path.
