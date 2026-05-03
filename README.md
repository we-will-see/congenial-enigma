# IndiaIR Repository Guide

IndiaIR is an investor-relations intelligence system for ingesting BSE filings, extracting structured information, indexing both keyword + semantic retrieval, and powering grounded Q&A with citations.

This README is a practical guide for **what this repo contains**, **how to run it**, and **how to work on it safely**.

## 1) What this repo includes

There are two main backend code trees:

- `app/`: the primary FastAPI app + pipeline modules that align with the current API routes.
- `api/`, `services/`, `ingestion/`, `extraction/`, `indexing/`: earlier/parallel module layout still present in the repository.

There are also two UI entrypoints:

- `ui/app.py`: Streamlit UI for the FastAPI backend.
- `frontend/streamlit_app.py`: additional Streamlit app variant.

Because both old and newer layouts exist, start from `app/main.py` + `app/api/v1/*` for current backend behavior.

## 2) High-level architecture

1. **Ingestion**
   - Poll/capture filing metadata and documents.
2. **Extraction & classification**
   - Classify documents (transcript, press release, financials, management changes, etc.).
   - Parse document text into structured entities.
3. **Storage + indexing**
   - Persist data in PostgreSQL.
   - Store vectors (pgvector) for semantic retrieval.
   - Index searchable fields in Elasticsearch.
4. **Serving layer**
   - FastAPI exposes health, company, document, search, and Q&A endpoints.
5. **UI**
   - Streamlit apps provide exploratory workflows over API results.

For deeper product/engineering context, see:

- `TECH_SPEC.md`
- `ARCH_DESIGN.md`
- `QUALITY_SPEC.md`
- `RELIABILITY_DEVOPS.md`
- `SECURITY_COMPLIANCE.md`

## 3) Repository map

See full map in `docs/REPO_GUIDE.md`.

Quick summary:

- `app/api/v1/`: API routes (`health`, `companies`, `documents`, `search`, `qa`, `management_changes`).
- `app/models/`: SQLAlchemy ORM models for core entities.
- `app/pipeline/`: extraction, chunking, embeddings, indexing, orchestration, CLI.
- `app/services/`: application service layer used by endpoints.
- `app/db/`, `alembic/`: DB session, base metadata, migrations.
- `tests/`: pipeline and classifier/extractor tests.
- `scripts/`: seeding + mock ingestion utilities.
- `ui/`, `frontend/`: Streamlit UIs.

## 4) Local setup

### Prereqs

- Python 3.11
- Docker + Docker Compose
- PostgreSQL 16 and Elasticsearch 8.13 (via compose)

### Install

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d postgres elasticsearch
alembic upgrade head
python scripts/seed_companies.py
python scripts/mock_ingest.py
```

### Environment variables

Set API keys as needed:

- `OPENAI_API_KEY` (embeddings)
- `ANTHROPIC_API_KEY` (LLM-backed Q&A / extraction fallback)

Without keys, portions of the app may run in deterministic/local fallback mode depending on configured code paths.

## 5) Run the system

### Backend

```bash
uvicorn app.main:app --reload --port 8000
```

### UI

```bash
streamlit run ui/app.py
```

### Health check

```bash
curl http://localhost:8000/api/v1/health
```

## 6) Core API endpoints

- `GET /api/v1/health`
- `GET /api/v1/companies`
- `GET /api/v1/companies/{company_id}`
- `GET /api/v1/documents`
- `POST /api/v1/search/keyword`
- `POST /api/v1/search/semantic`
- `POST /api/v1/qa/ask`
- `GET /api/v1/management-changes`

> Tip: check route modules under `app/api/v1/` for exact request/response schemas.

## 7) Testing and verification

Run these before committing:

```bash
python -m compileall app api ingestion extraction indexing services scripts ui frontend tests
pytest
```

## 8) Known repo realities (important)

- The repo currently contains **duplicate/parallel module trees** (`app/*` and older `api|services|ingestion|...` paths).
- Some docs refer to earlier entrypoints (`api.main:app`) while current route layout in `app/api/v1` suggests using `app.main:app`.
- Keep new feature work centered in the `app/` tree unless explicitly refactoring legacy modules.

## 9) Suggested cleanup plan

If you want to “fully organize” this repo next, execute in phases:

1. Pick canonical backend tree (`app/`) and deprecate old duplicates.
2. Move product/architecture specs into `docs/specs/`.
3. Add `.env.example` with all required runtime settings.
4. Add `Makefile` (`make setup`, `make test`, `make run-api`, `make run-ui`).
5. Add CI for lint + tests + migration checks.

---

If you want, I can do the next step and apply a **safe structural refactor** (non-breaking file moves + import compatibility layer) in a follow-up change.
