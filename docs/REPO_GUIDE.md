# Repo Map and Contributor Notes

## Top-level directories/files

- `app/` — current primary backend application.
- `api/` — legacy/parallel backend package.
- `services/` — legacy/parallel service modules.
- `ingestion/`, `extraction/`, `indexing/` — modular pipeline components (legacy/parallel and still useful).
- `ui/`, `frontend/` — Streamlit frontends.
- `tests/` — automated tests.
- `scripts/` — local scripts for seed/mock ingest.
- `alembic/` + `alembic.ini` — DB migration setup.
- `docker-compose.yml` — local infra services.
- `requirements.txt` — Python dependencies.
- `*.md` specs — product, architecture, reliability, security, UX docs.

## Core backend (`app/`) detail

- `app/main.py` — FastAPI app bootstrap.
- `app/api/v1/` — HTTP routes.
- `app/models/` — SQLAlchemy models.
- `app/schemas/` — API/Pydantic schema objects.
- `app/services/` — use-case/business services.
- `app/db/` — DB engine/session/base.
- `app/core/` — config/logging.
- `app/pipeline/` — extraction/indexing orchestration.
- `app/rag/` — prompts + QA service logic.

## Where to start as a new maintainer

1. Read `README.md`.
2. Read `ARCH_DESIGN.md` and `TECH_SPEC.md`.
3. Run setup + tests locally.
4. Trace one request path (e.g., `/api/v1/search/semantic`) from route → service → DB/index.

## Practical conventions for future cleanup

- Prefer adding new backend code under `app/`.
- Keep legacy tree untouched unless doing deliberate consolidation.
- Add migration for any model changes.
- Ensure tests cover both extraction and API-facing logic.
