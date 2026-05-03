# Architecture & Design Document
## IndiaIR — Indian Investor Relations Intelligence Platform
### Version 1.0 | April 2026

---

> **For AI coding agents:** This document defines system topology, data flow, component interfaces, and failure handling. Do not add components or change the data flow without flagging it. All inter-component communication must go through the defined interfaces.

---

## 1. System Overview

IndiaIR is a single-server, multi-process application. For MVP it runs entirely on one machine (local or cloud VM). There is no distributed infrastructure.

```
┌─────────────────────────────────────────────────────────────────┐
│                         Single Host                             │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │  Streamlit   │    │   FastAPI    │    │   APScheduler    │  │
│  │     UI       │───▶│   Backend   │    │   (Pipeline      │  │
│  │  :8501       │    │   :8000      │    │    Scheduler)    │  │
│  └──────────────┘    └──────┬───────┘    └────────┬─────────┘  │
│                             │                     │             │
│              ┌──────────────┼─────────────────────┤             │
│              │              │                     │             │
│         ┌────▼────┐   ┌─────▼─────┐   ┌──────────▼────────┐  │
│         │Postgres │   │  Elastic  │   │  Pipeline Workers  │  │
│         │+pgvector│   │  Search   │   │  (extraction,      │  │
│         │  :5432  │   │   :9200   │   │   indexing,        │  │
│         └─────────┘   └───────────┘   │   scheduling)      │  │
│                                        └───────────┬────────┘  │
│                                                    │            │
│                                        ┌───────────▼────────┐  │
│                                        │   Local Filesystem  │  │
│                                        │   ./data/raw_pdfs   │  │
│                                        └────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │   External APIs     │
                    │  - BSE India API    │
                    │  - Anthropic API    │
                    │  - OpenAI API       │
                    │  (embeddings only)  │
                    └────────────────────┘
```

---

## 2. Component Descriptions

### 2.1 Streamlit UI (`ui/app.py`)

- Single-page Streamlit app with sidebar navigation
- Communicates with FastAPI backend via `httpx` (not direct DB access)
- Pages: Search, Q&A, Company, Financials, Management Changes, Coverage Dashboard
- No authentication — single-user for MVP
- Runs on port 8501

### 2.2 FastAPI Backend (`api/main.py`)

- REST API serving the Streamlit frontend
- Handles: keyword search, semantic search, RAG Q&A, company data, financials, management changes, health check
- Connects to: Postgres (via SQLAlchemy async), Elasticsearch (via elasticsearch-py), OpenAI/Anthropic (via their SDKs)
- Runs on port 8000
- Async throughout — all DB and API calls use `await`

### 2.3 Pipeline Workers (`ingestion/`, `extraction/`, `indexing/`)

- Python processes, not a separate service
- Invoked by APScheduler for incremental polling
- Invoked by `scripts/backfill.py` for historical loading
- Write results to Postgres; indexing modules then read from Postgres and write to ES + pgvector
- All workers log to `pipeline_runs` table

### 2.4 APScheduler (`ingestion/scheduler.py`)

- Single background scheduler embedded in the FastAPI process
- Jobs:
  - `poll_bse_all_companies`: runs daily at 09:00 IST, iterates through all 30 companies
  - `index_pending_documents`: runs every 15 minutes, picks up any documents with `extraction_status = 'complete'` but not yet in ES
  - `health_check_external_apis`: runs every 5 minutes, updates health endpoint

### 2.5 Postgres + pgvector

- Version: PostgreSQL 16 + pgvector 0.7
- Two roles: `indiair` (app user, read/write), `indiair_ro` (read-only, for future use)
- Connection pool: min 2, max 10
- pgvector IVFFlat index with 100 lists (adequate for ~500k vectors at MVP scale)

### 2.6 Elasticsearch

- Version: 8.13 (single node, no cluster for MVP)
- One index: `india_ir_content`
- No authentication (bound to localhost only)
- JVM heap: 1GB (sufficient for MVP corpus)

---

## 3. Data Flow — Ingestion Pipeline

```
BSE India API
      │
      ▼ (1) Poll filings list
┌─────────────────┐
│  bse_poller.py  │──── writes ────▶ events table (metadata only)
└────────┬────────┘                  documents table (status=pending)
         │
         ▼ (2) Download PDF
┌──────────────────┐
│ PDF downloader   │──── stores ───▶ ./data/raw_pdfs/{scrip}/{filing_id}.pdf
└────────┬─────────┘                 updates documents.storage_path
         │
         ▼ (3) Classify
┌──────────────────────┐
│ document_classifier  │──── updates ▶ documents.document_type
└────────┬─────────────┘
         │
         ├──── if concall_transcript ──▶ transcript_parser.py ──▶ turns table
         │
         ├──── if investor_presentation ─▶ slide_parser.py ──▶ slides table
         │
         ├──── if results_press_release ─▶ press_release_parser.py ──▶ press_release_sections table
         │                                  financial_extractor.py ──▶ financials table
         │
         ├──── if management_change ──────▶ mgmt_change_parser.py ──▶ management_changes table
         │
         └──── if other/outcome ──────────▶ skip (status=skipped)
                    │
                    ▼ (4) Quality check
         ┌──────────────────────┐
         │  quality_checker.py  │──── updates ▶ documents.quality_score, quality_flags, extraction_status
         └────────┬─────────────┘
                  │
                  ▼ (5) Index
         ┌──────────────────────┐
         │   es_indexer.py      │──── writes ──▶ Elasticsearch (full-text)
         │   embedding_indexer  │──── writes ──▶ pgvector (semantic)
         └──────────────────────┘
```

**Status transitions for `documents.extraction_status`:**
```
pending → processing → complete → (indexed)
pending → processing → failed
pending → processing → low_quality → (manual review or OCR retry)
pending → skipped  (board_meeting_outcome, other)
```

---

## 4. Data Flow — Query Pipeline

### 4.1 Keyword Search

```
User query + filters
      │
      ▼
FastAPI: POST /api/v1/search/keyword
      │
      ▼
Build ES query:
  - match query on text field
  - filter by company_id, quarter range, document_type, speaker_role
  - highlight on text field (300 char fragments)
      │
      ▼
ES returns hits with scores + highlighted snippets
      │
      ▼
Enrich from Postgres: fetch company_name, speaker details for each hit
      │
      ▼
Return paginated results
```

### 4.2 RAG Q&A

```
User question + scope filters
      │
      ▼
1. Embed question → OpenAI text-embedding-3-small (1536-dim vector)
      │
      ▼
2. Vector search in pgvector:
   SELECT * FROM embeddings
   WHERE company_id = ANY(:company_ids)  -- if scoped
   ORDER BY embedding <=> :query_vector
   LIMIT 15
      │
      ▼
3. Keyword search in ES (same query, top 10)
      │
      ▼
4. RRF fusion: merge vector + keyword results, deduplicate, take top 10
      │
      ▼
5. If question contains financial signals (revenue, margin, profit, growth, etc.):
   Fetch relevant financials from Postgres for scoped companies
      │
      ▼
6. Build prompt:
   - RAG_SYSTEM_PROMPT (from TECH_SPEC)
   - Context: top 10 chunks formatted with company/quarter/speaker metadata
   - Financials: formatted table if fetched in step 5
      │
      ▼
7. Stream response from Claude Sonnet via Anthropic API
      │
      ▼
8. Extract citations from response, resolve to document links
      │
      ▼
9. Stream tokens + citations + financial data as SSE to client
```

---

## 5. API Design Principles

- **Versioned:** All endpoints prefixed with `/api/v1/`
- **No side effects on GET:** GET endpoints never modify state
- **Consistent error format:** `{"error": "Human message", "code": "SNAKE_CASE_CODE"}`
- **Pagination:** All list endpoints paginated. Default page_size=20, max=100. Response includes `total` count.
- **Timeouts:** All external API calls have explicit timeouts:
  - BSE API: 30s
  - Anthropic API: 120s (streaming)
  - OpenAI embeddings: 30s
- **No N+1 queries:** All list endpoints fetch related data in bulk, not per-item

**Error codes:**

| Code | HTTP Status | Meaning |
|---|---|---|
| INVALID_INPUT | 422 | Request validation failed |
| NOT_FOUND | 404 | Resource not found |
| SEARCH_UNAVAILABLE | 503 | Elasticsearch down |
| LLM_UNAVAILABLE | 503 | Anthropic API unreachable |
| RATE_LIMITED | 429 | Too many requests |
| INTERNAL_ERROR | 500 | Unexpected error |

---

## 6. Scaling Approach

MVP is explicitly single-server. The architecture does not need to scale horizontally for MVP. However, the design must not prevent future scaling.

**What would scale first if needed:**

| Bottleneck | Signal | Solution |
|---|---|---|
| Embedding generation | > 1M chunks to index | Batch with async parallelism; move to dedicated embedding service |
| ES query latency | > 2s at scale | Add ES replicas; tune IVFFlat nprobes |
| Postgres connection pool | Pool exhausted under load | Increase pool size; add PgBouncer |
| PDF storage | > 50GB | Move from local filesystem to S3 |
| RAG response latency | Users complaining | Cache frequent queries in Redis |

**What to avoid building prematurely:** Kubernetes, message queues (Celery/RabbitMQ), microservices. The pipeline is a batch process, not a real-time stream. APScheduler + sync workers is sufficient for MVP scale (30 companies, daily polling).

---

## 7. Failure Handling

### 7.1 BSE API Failures

```python
# In bse_poller.py
for attempt in range(MAX_RETRIES):
    try:
        response = httpx.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        log.warning("BSE API timeout", attempt=attempt, scrip=scrip_code)
        await asyncio.sleep(RETRY_BACKOFF_SECONDS * (2 ** attempt))
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            await asyncio.sleep(60)  # hard back-off on rate limit
        elif e.response.status_code >= 500:
            await asyncio.sleep(RETRY_BACKOFF_SECONDS * (2 ** attempt))
        else:
            raise  # 4xx other than 429 = don't retry

# After MAX_RETRIES: log to pipeline_runs.errors, continue to next company
# Do NOT raise — one company failing should not stop the full poll
```

### 7.2 PDF Extraction Failures

- If `pymupdf` raises exception: catch, log, set `extraction_status = 'failed'`, continue
- If extracted text quality below threshold: set `extraction_status = 'low_quality'`, attempt OCR
- If OCR also fails: set `extraction_status = 'failed'`, log to `pipeline_runs`
- Never lose a document reference — even failed extractions keep their `documents` row

### 7.3 LLM API Failures (Anthropic)

- For management change extraction (batch, not user-facing): retry 3x, then skip with `extraction_confidence = 0`
- For financial LLM fallback: retry 3x, then write the row with `extraction_method = 'failed'` and `quality_flags = ['LLM_EXTRACTION_FAILED']`
- For RAG Q&A (user-facing): return error message to client immediately, do not hang

### 7.4 Elasticsearch Down

- Search endpoints return 503 with `SEARCH_UNAVAILABLE`
- Ingestion pipeline logs the failure but does not block — documents are marked as `extraction_status = 'complete'` and will be picked up by the `index_pending_documents` job when ES recovers
- Health endpoint reflects ES status

### 7.5 Postgres Down

- All endpoints return 503
- Pipeline scheduler logs error and retries on next scheduled run
- No in-memory state — nothing is lost

### 7.6 Partial Pipeline Runs

If the pipeline process is killed mid-run (e.g. OOM, manual kill):
- Documents in `processing` status need cleanup on restart
- On startup: reset any documents stuck in `processing` for > 30 minutes to `pending`

```python
# In pipeline startup
db.execute("""
    UPDATE documents SET extraction_status = 'pending'
    WHERE extraction_status = 'processing'
    AND updated_at < NOW() - INTERVAL '30 minutes'
""")
```

---

## 8. Logging

All components use `structlog` with JSON output.

**Standard fields on every log line:**
```json
{
    "timestamp": "2026-04-23T09:15:32Z",
    "level": "info",
    "logger": "ingestion.bse_poller",
    "event": "filing_downloaded",
    "scrip_code": "540222",
    "filing_id": "20241023-33",
    "document_type": "concall_transcript",
    "duration_ms": 342
}
```

**Log levels:**
- `DEBUG`: Per-turn parsing details, extraction intermediates (disabled in production)
- `INFO`: Every document processed, every API call, pipeline start/end
- `WARNING`: Quality flags, retries, BSE API slow responses
- `ERROR`: Extraction failures, API failures after retries
- `CRITICAL`: DB down, unrecoverable pipeline state

**Log file:** `./logs/indiair.log` — JSON, one line per event, rotation at 100MB.

---

## 9. docker-compose.yml

```yaml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: indiair
      POSTGRES_USER: indiair
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U indiair"]
      interval: 10s
      timeout: 5s
      retries: 5

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
    volumes:
      - es_data:/usr/share/elasticsearch/data
    ports:
      - "9200:9200"
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:9200/_cluster/health || exit 1"]
      interval: 15s
      timeout: 10s
      retries: 5

volumes:
  postgres_data:
  es_data:
```

---

*Last Updated: April 2026 | Version 1.0*
