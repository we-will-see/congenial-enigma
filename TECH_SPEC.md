# Technical & Functional Specification
## IndiaIR — Indian Investor Relations Intelligence Platform
### Version 1.0 | April 2026

---

> **For AI coding agents:** This document defines exact implementation contracts. Field names, types, package versions, and validation rules are normative — do not substitute alternatives without flagging the deviation. Where a sample input/output is provided, your implementation must reproduce it exactly.

---

## 1. Technology Stack — Pinned Versions

```
Python              3.11.x
FastAPI             0.111.x
SQLAlchemy          2.0.x
Alembic             1.13.x
psycopg2-binary     2.9.x
pgvector            0.2.x
elasticsearch       8.13.x
pymupdf             1.24.x   (import as fitz)
pdfplumber          0.11.x
camelot-py[cv]      0.11.x
pytesseract         0.3.x
Pillow              10.x
openai              1.x      (for embeddings only)
anthropic           0.28.x   (for RAG + LLM extraction)
apscheduler         3.10.x
streamlit           1.35.x
plotly              5.x
pandas              2.x
pydantic            2.x
httpx               0.27.x
python-dotenv       1.0.x
structlog           24.x
pytest              8.x
pytest-asyncio      0.23.x
```

All packages installed via `pip install -r requirements.txt`. No conda.

---

## 2. Environment Variables

All configuration via environment variables. No hardcoded values anywhere.

```bash
# Database
DATABASE_URL=postgresql://indiair:password@localhost:5432/indiair

# Elasticsearch
ES_HOST=http://localhost:9200
ES_INDEX_NAME=india_ir_content

# Storage
S3_BUCKET=indiair-raw-pdfs          # or LOCAL_STORAGE_PATH for dev
LOCAL_STORAGE_PATH=./data/raw_pdfs

# LLM APIs
ANTHROPIC_API_KEY=sk-ant-...         # For RAG Q&A, mgmt change extraction, financial fallback
OPENAI_API_KEY=sk-...                # For embeddings only (text-embedding-3-small)

# OCR
USE_AWS_TEXTRACT=false               # Set true to enable Textract fallback
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=ap-south-1

# Pipeline
BSE_POLL_INTERVAL_SECONDS=86400      # 24 hours
BSE_REQUEST_DELAY_SECONDS=1.0        # Throttle between requests
MAX_RETRIES=3
RETRY_BACKOFF_SECONDS=5

# Quality thresholds
MIN_CHARS_PER_PAGE=200               # Below this = likely scanned PDF
MIN_TEXT_QUALITY_SCORE=0.7           # Below this = route to OCR
RESTATEMENT_THRESHOLD=0.05           # Flag if stored value changes by > 5%
FINANCIAL_CONSISTENCY_TOLERANCE=0.02 # 2% tolerance on cross-checks

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

---

## 3. Database Schema — Complete DDL

```sql
-- Enable extensions
CREATE EXTENSION IF NOT EXISTS pgvector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Companies master
CREATE TABLE companies (
    id              SERIAL PRIMARY KEY,
    scrip_code      VARCHAR(10) NOT NULL UNIQUE,
    isin            VARCHAR(12),
    name            VARCHAR(200) NOT NULL,
    name_aliases    TEXT[],          -- alternate names seen in filings
    sector          VARCHAR(100),
    sub_sector      VARCHAR(100),
    bse_id          VARCHAR(20),
    active          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Filing events
CREATE TABLE events (
    id              SERIAL PRIMARY KEY,
    company_id      INTEGER NOT NULL REFERENCES companies(id),
    bse_filing_id   VARCHAR(50) UNIQUE,       -- BSE's internal filing ID
    event_date      DATE NOT NULL,
    event_type      VARCHAR(50) NOT NULL,      -- concall, results, mgmt_change, presentation
    quarter         VARCHAR(10),               -- e.g. 3QFY25; NULL for non-periodic events
    fy_year         INTEGER,                   -- e.g. 2025
    filing_url      TEXT,                      -- original BSE URL
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_events_company_date ON events(company_id, event_date DESC);
CREATE INDEX idx_events_quarter ON events(quarter);

-- Documents (one event can have multiple documents)
CREATE TABLE documents (
    id                  SERIAL PRIMARY KEY,
    event_id            INTEGER NOT NULL REFERENCES events(id),
    document_type       VARCHAR(50) NOT NULL,
        -- concall_transcript | investor_presentation | results_press_release
        -- management_change | board_meeting_outcome | other
    bse_url             TEXT,
    storage_path        TEXT NOT NULL,         -- S3 key or local path
    file_hash           VARCHAR(64),           -- SHA-256 of raw PDF
    page_count          INTEGER,
    pdf_type            VARCHAR(20),           -- text | scanned | mixed
    extraction_status   VARCHAR(20) DEFAULT 'pending',
        -- pending | processing | complete | failed | low_quality
    extraction_method   VARCHAR(20),           -- pymupdf | tesseract | textract
    quality_score       FLOAT,                 -- 0.0–1.0
    quality_flags       TEXT[],                -- array of flag strings
    error_message       TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    processed_at        TIMESTAMPTZ
);

CREATE INDEX idx_documents_event ON documents(event_id);
CREATE INDEX idx_documents_type ON documents(document_type);
CREATE INDEX idx_documents_status ON documents(extraction_status);

-- Concall speaker turns
CREATE TABLE turns (
    id              BIGSERIAL PRIMARY KEY,
    document_id     INTEGER NOT NULL REFERENCES documents(id),
    turn_index      INTEGER NOT NULL,
    speaker_raw     TEXT,                      -- as it appears in the PDF
    speaker_name    VARCHAR(200),              -- normalised
    speaker_role    VARCHAR(20) NOT NULL,
        -- management | analyst | moderator | unknown
    speaker_org     VARCHAR(200),              -- analyst's firm if known
    speaker_title   VARCHAR(200),              -- CFO, MD, etc.
    text            TEXT NOT NULL,
    word_count      INTEGER,
    UNIQUE(document_id, turn_index)
);

CREATE INDEX idx_turns_document ON turns(document_id);
CREATE INDEX idx_turns_role ON turns(speaker_role);

-- Presentation slides
CREATE TABLE slides (
    id              BIGSERIAL PRIMARY KEY,
    document_id     INTEGER NOT NULL REFERENCES documents(id),
    slide_number    INTEGER NOT NULL,
    title           TEXT,
    body_text       TEXT,
    UNIQUE(document_id, slide_number)
);

-- Press release sections
CREATE TABLE press_release_sections (
    id              BIGSERIAL PRIMARY KEY,
    document_id     INTEGER NOT NULL REFERENCES documents(id),
    section_type    VARCHAR(50) NOT NULL,
        -- financial_highlights | operational_highlights | management_commentary | other
    section_order   INTEGER,
    text            TEXT NOT NULL
);

-- Management changes (structured)
CREATE TABLE management_changes (
    id              BIGSERIAL PRIMARY KEY,
    company_id      INTEGER NOT NULL REFERENCES companies(id),
    document_id     INTEGER REFERENCES documents(id),
    filing_date     DATE NOT NULL,
    effective_date  DATE,
    change_type     VARCHAR(30) NOT NULL,
        -- appointment | resignation | retirement | cessation | re_appointment | additional_charge
    person_name     VARCHAR(200) NOT NULL,
    role            VARCHAR(200) NOT NULL,
    role_category   VARCHAR(30) NOT NULL,
        -- kmp | board_executive | board_non_executive | board_independent
    reason          TEXT,                      -- NULL if not stated
    din             VARCHAR(20),               -- Director Identification Number if present
    raw_text        TEXT NOT NULL,
    extraction_confidence FLOAT,               -- 0.0–1.0 from LLM
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_mgmt_changes_company ON management_changes(company_id);
CREATE INDEX idx_mgmt_changes_date ON management_changes(filing_date DESC);

-- Financials (consolidated P&L only)
CREATE TABLE financials (
    id              BIGSERIAL PRIMARY KEY,
    company_id      INTEGER NOT NULL REFERENCES companies(id),
    document_id     INTEGER REFERENCES documents(id),
    period          VARCHAR(10) NOT NULL,      -- e.g. 3QFY25 or FY25
    period_type     VARCHAR(10) NOT NULL,      -- quarterly | annual
    period_end_date DATE,
    -- P&L line items (all in INR Crores, 2 decimal places)
    revenue         NUMERIC(12,2),
    ebitda          NUMERIC(12,2),
    ebitda_margin   NUMERIC(6,4),              -- e.g. 0.1802 = 18.02%
    da              NUMERIC(12,2),             -- Depreciation & Amortisation
    ebit            NUMERIC(12,2),
    finance_costs   NUMERIC(12,2),
    pbt             NUMERIC(12,2),
    tax             NUMERIC(12,2),
    pat             NUMERIC(12,2),
    eps_basic       NUMERIC(10,2),
    eps_diluted     NUMERIC(10,2),
    shares_cr       NUMERIC(10,4),             -- shares outstanding in Crores
    -- Metadata
    currency        VARCHAR(5) DEFAULT 'INR',
    unit            VARCHAR(20) DEFAULT 'Crores',
    restated        BOOLEAN DEFAULT FALSE,
    restatement_note TEXT,
    extraction_method VARCHAR(20),             -- table | llm_fallback
    quality_flags   TEXT[],
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(company_id, period, period_type)
);

CREATE INDEX idx_financials_company_period ON financials(company_id, period);

-- Embeddings (pgvector)
CREATE TABLE embeddings (
    id              BIGSERIAL PRIMARY KEY,
    -- Source reference (one of these will be non-null)
    turn_id         BIGINT REFERENCES turns(id),
    slide_id        BIGINT REFERENCES slides(id),
    section_id      BIGINT REFERENCES press_release_sections(id),
    -- Chunk metadata (denormalised for fast retrieval)
    company_id      INTEGER NOT NULL REFERENCES companies(id),
    document_id     INTEGER NOT NULL REFERENCES documents(id),
    document_type   VARCHAR(50) NOT NULL,
    quarter         VARCHAR(10),
    event_date      DATE,
    speaker_role    VARCHAR(20),
    chunk_text      TEXT NOT NULL,
    chunk_index     INTEGER,
    -- Vector
    embedding       vector(1536),              -- text-embedding-3-small dimension
    model_version   VARCHAR(50) DEFAULT 'text-embedding-3-small',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_embeddings_company ON embeddings(company_id);
CREATE INDEX embeddings_vector_idx ON embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Pipeline run log
CREATE TABLE pipeline_runs (
    id              SERIAL PRIMARY KEY,
    run_type        VARCHAR(50) NOT NULL,      -- backfill | incremental | single_document
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    status          VARCHAR(20) DEFAULT 'running',
    documents_processed INTEGER DEFAULT 0,
    documents_failed INTEGER DEFAULT 0,
    errors          JSONB DEFAULT '[]',
    metrics         JSONB DEFAULT '{}'
);

-- Financials history (for restatement tracking)
CREATE TABLE financials_history (
    id              BIGSERIAL PRIMARY KEY,
    financials_id   BIGINT NOT NULL REFERENCES financials(id),
    snapshot        JSONB NOT NULL,            -- full row at time of change
    changed_at      TIMESTAMPTZ DEFAULT NOW(),
    change_reason   TEXT
);
```

---

## 4. BSE API Contract

### 4.1 Filings Endpoint

```
GET https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w
```

**Query parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| strCat | string | Yes | Category filter. Use `-1` for all categories |
| strPrevDate | string | Yes | Start date, format `YYYYMMDD` |
| strToDate | string | Yes | End date, format `YYYYMMDD` |
| strScrip | string | Yes | BSE scrip code (e.g. `540222`) |
| strSearch | string | Yes | Use `P` |
| strType | string | Yes | Use `C` |

**Response structure:**

```json
{
  "Table": [
    {
      "NEWSID": "20241023-33",
      "SLNO": "1",
      "DT_TM": "23-OCT-2024 17:45:24",
      "NEWS_DT": "23-OCT-2024",
      "CATEGORYNAME": "Concall",
      "SUBCATEGORYNAME": "Transcript",
      "HEADLINE": "Transcript of Earnings Call",
      "ATTACHMENT": "https://www.bseindia.com/xml-data/corpfiling/AttachHis/abc123.pdf",
      "SCRIP_CD": "540222",
      "COMPANY_NAME": "LAURUS LABS LIMITED",
      "SLNO2": "0"
    }
  ]
}
```

**Key fields used:**
- `NEWSID` → `bse_filing_id`
- `DT_TM` → filing datetime (parse format `DD-MON-YYYY HH:MM:SS`)
- `CATEGORYNAME` + `SUBCATEGORYNAME` → document classification
- `ATTACHMENT` → PDF download URL
- `SCRIP_CD` → company lookup

**Rate limiting:** 1 request per second per scrip code. Use `asyncio.sleep(BSE_REQUEST_DELAY_SECONDS)` between requests.

**Error handling:**
- HTTP 429 → back off 60 seconds, retry
- HTTP 5xx → retry with exponential backoff up to MAX_RETRIES
- Empty `Table` array → no filings in date range, not an error
- Connection timeout after 30 seconds → retry

### 4.2 Document Classifier — Category Mapping

```python
CATEGORY_MAP = {
    # (CATEGORYNAME, SUBCATEGORYNAME) → document_type
    ("Concall", "Transcript"): "concall_transcript",
    ("Concall", "Audio"): "other",
    ("Investor Presentation", ""): "investor_presentation",
    ("Investor Presentation", "Investor Presentation"): "investor_presentation",
    ("Results", "Financial Results"): "results_press_release",
    ("Results", "Quarterly Financial Results"): "results_press_release",
    ("Results", "Unaudited Financial Results"): "results_press_release",
    ("Results", "Audited Financial Results"): "results_press_release",
    ("Board Meeting", "Outcome of Board Meeting"): "board_meeting_outcome",
    ("Reg36(1)(2)", "Outcome of Board Meeting"): "board_meeting_outcome",
    ("Change in Directors/Key Managerial Personnel", ""): "management_change",
    ("Change in Directors/Key Managerial Personnel/Auditor/Compliance Officer", ""): "management_change",
    ("Appointment", ""): "management_change",
    ("Resignation", ""): "management_change",
}

# Fallback: keyword match on HEADLINE
HEADLINE_PATTERNS = {
    "concall_transcript": ["transcript", "concall", "earnings call transcript"],
    "investor_presentation": ["investor presentation", "analyst day", "investor day"],
    "results_press_release": ["financial results", "quarterly results", "annual results"],
    "management_change": ["appointment", "resignation", "cessation", "director", "kmp", "cfo", "ceo", "md "],
}
```

---

## 5. PDF Extraction Specification

### 5.1 PDF Type Detection

```python
def detect_pdf_type(pdf_path: str) -> str:
    """Returns: 'text' | 'scanned' | 'mixed'"""
    # Open with pymupdf
    # For each page, extract text
    # Compute average chars per page
    # Compute proportion of valid unicode (printable ASCII + common Indian chars)
    # If avg_chars_per_page < MIN_CHARS_PER_PAGE → 'scanned'
    # If quality_score < MIN_TEXT_QUALITY_SCORE → route to OCR regardless
    # If > 30% pages are scanned but < 70% → 'mixed'
```

### 5.2 Transcript Parser — Speaker Turn Format

Indian concall transcripts use these header patterns (regex, case-insensitive):

```python
SPEAKER_PATTERNS = [
    # Pattern 1: Bold name followed by colon (most common — KFin/Link Intime)
    r'^([A-Z][A-Za-z\s\.\-]+?):\s',
    # Pattern 2: Name in all-caps
    r'^([A-Z][A-Z\s\.]+):\s',
    # Pattern 3: Name with affiliation in parentheses
    r'^([A-Za-z\s\.\-]+?)\s*\(([A-Za-z\s]+?)\):\s',
    # Pattern 4: "Management" or "Analyst" as speaker
    r'^(Management|Analyst|Moderator|Operator):\s',
    # Pattern 5: Line starting with name followed by newline then text
    r'^([A-Z][A-Za-z\s\.\-]+?)\n',
]

MANAGEMENT_SIGNALS = [
    "managing director", "md &", "chief executive", "ceo", "chief financial",
    "cfo", "chief operating", "coo", "president", "vice president", "vp ",
    "head of", "director", "chairman", "whole-time director"
]

ANALYST_SIGNALS = [
    "analyst", "research", "securities", "capital", "asset management",
    "investments", "fund", "partners", "advisors", "bank", "broking"
]

MODERATOR_SIGNALS = ["moderator", "operator", "good morning", "good evening",
                     "welcome", "next question", "next participant"]
```

**Expected output — sample:**

Input PDF text:
```
V.V. Ravi Kumar: Thank you. On margins, we expect to see improvement in Q4.

Neha Manpuria (JPMorgan): My question is on the CDMO pipeline.

V.V. Ravi Kumar: Yes, we have added three new molecules this quarter.
```

Expected `turns` output:
```python
[
    {
        "turn_index": 0,
        "speaker_raw": "V.V. Ravi Kumar",
        "speaker_name": "V.V. Ravi Kumar",
        "speaker_role": "management",
        "speaker_org": None,
        "speaker_title": "CFO",  # resolved from company master if known
        "text": "Thank you. On margins, we expect to see improvement in Q4.",
        "word_count": 13
    },
    {
        "turn_index": 1,
        "speaker_raw": "Neha Manpuria (JPMorgan)",
        "speaker_name": "Neha Manpuria",
        "speaker_role": "analyst",
        "speaker_org": "JPMorgan",
        "speaker_title": None,
        "text": "My question is on the CDMO pipeline.",
        "word_count": 7
    }
]
```

### 5.3 Financial Extractor — Label Dictionary

The canonical label dictionary maps raw table row labels (as they appear in Indian press release PDFs) to normalised field names. Matching is fuzzy (lowercase, strip punctuation, Levenshtein distance ≤ 2).

```python
LABEL_DICT = {
    "revenue": [
        "revenue from operations", "net revenue from operations",
        "total revenue from operations", "net sales", "revenue",
        "total income from operations", "net revenue", "sales",
        "gross revenue from operations", "income from operations",
        "revenue from contracts with customers"
    ],
    "ebitda": [
        "ebitda", "earnings before interest tax depreciation amortisation",
        "operating ebitda", "ebitda before exceptional"
    ],
    "da": [
        "depreciation and amortisation", "depreciation & amortisation",
        "depreciation", "depreciation amortisation", "d&a",
        "depreciation depletion and amortisation"
    ],
    "ebit": [
        "ebit", "operating profit", "profit from operations",
        "earnings before interest and tax"
    ],
    "finance_costs": [
        "finance costs", "interest expense", "finance charges",
        "interest and finance charges", "borrowing costs"
    ],
    "pbt": [
        "profit before tax", "pbt", "profit before exceptional items and tax",
        "profit before exceptional and tax"
    ],
    "tax": [
        "tax expense", "income tax expense", "provision for tax",
        "total tax expense", "current tax", "tax"
    ],
    "pat": [
        "profit after tax", "pat", "profit for the period",
        "profit for the year", "net profit", "profit attributable to owners",
        "profit attributable to equity shareholders"
    ],
    "eps_basic": [
        "basic eps", "earnings per share basic", "basic earnings per share",
        "eps (basic)", "basic eps (not annualised)"
    ],
    "eps_diluted": [
        "diluted eps", "earnings per share diluted", "diluted earnings per share",
        "eps (diluted)", "diluted eps (not annualised)"
    ],
    "shares_cr": [
        "weighted average shares", "weighted average number of equity shares",
        "shares outstanding", "number of equity shares"
    ]
}
```

**Verified test fixture — Laurus Labs 3QFY25:**

```python
LAURUS_3QFY25_VERIFIED = {
    "company": "Laurus Labs",
    "period": "3QFY25",
    "period_type": "quarterly",
    "revenue": 1547.00,
    "ebitda": 278.00,
    "ebitda_margin": 0.1797,     # 17.97%
    "pat": 152.00,
    "eps_basic": 2.81,
}
# financial_extractor output must match these values within 2% tolerance
# This is AC-03 in the PRD acceptance criteria
```

### 5.4 Financial Consistency Checks

All checks must pass before a row is written to the `financials` table. Failures are written to `quality_flags`, not discarded.

```python
def validate_financials(row: dict) -> list[str]:
    flags = []
    tol = FINANCIAL_CONSISTENCY_TOLERANCE  # 0.02

    # Check 1: EPS × shares ≈ PAT
    if all(row.get(f) for f in ['eps_basic', 'shares_cr', 'pat']):
        computed_pat = row['eps_basic'] * row['shares_cr']
        if abs(computed_pat - row['pat']) / row['pat'] > tol:
            flags.append(f"EPS_PAT_MISMATCH: computed={computed_pat:.2f} stored={row['pat']:.2f}")

    # Check 2: EBITDA - D&A ≈ EBIT (if all three present)
    if all(row.get(f) for f in ['ebitda', 'da', 'ebit']):
        computed_ebit = row['ebitda'] - row['da']
        if abs(computed_ebit - row['ebit']) / abs(row['ebit']) > tol:
            flags.append(f"EBITDA_DA_EBIT_MISMATCH: computed={computed_ebit:.2f} stored={row['ebit']:.2f}")

    # Check 3: EBIT - finance_costs ≈ PBT (if all present)
    if all(row.get(f) for f in ['ebit', 'finance_costs', 'pbt']):
        computed_pbt = row['ebit'] - row['finance_costs']
        if abs(computed_pbt - row['pbt']) / abs(row['pbt']) > tol:
            flags.append(f"PBT_MISMATCH")

    # Check 4: Revenue must be positive
    if row.get('revenue') and row['revenue'] <= 0:
        flags.append("NEGATIVE_REVENUE")

    # Check 5: QoQ/YoY sanity (> 50% change flagged)
    # Requires prior period data from DB — checked in validator, not extractor

    # Check 6: EBITDA margin consistency
    if all(row.get(f) for f in ['revenue', 'ebitda']):
        computed_margin = row['ebitda'] / row['revenue']
        row['ebitda_margin'] = round(computed_margin, 4)  # always recompute, never trust stated

    return flags
```

### 5.5 Management Change Extractor — LLM Prompt

```python
MGMT_CHANGE_SYSTEM_PROMPT = """
You extract structured management change records from Indian listed company regulatory filings.
Respond ONLY with a JSON array. No preamble, no markdown, no explanation.

For each change mentioned, return one object with these exact fields:
{
    "person_name": string,           // Full name as stated
    "role": string,                  // Exact role title as stated
    "role_category": string,         // One of: kmp | board_executive | board_non_executive | board_independent
    "change_type": string,           // One of: appointment | resignation | retirement | cessation | re_appointment | additional_charge
    "effective_date": string | null, // ISO format YYYY-MM-DD or null if not stated
    "reason": string | null,         // Only if explicitly stated, else null
    "din": string | null,            // Director Identification Number if present
    "confidence": float              // 0.0-1.0, your confidence in this extraction
}

Role category rules:
- MD, CEO, CFO, COO, CS (Company Secretary), CTO → kmp
- Whole-time Director, Executive Director → board_executive
- Non-Executive Non-Independent Director → board_non_executive
- Independent Director → board_independent

Do NOT infer reason if not explicitly stated. Do NOT assume effective date from filing date.
"""
```

---

## 6. Elasticsearch Index Mapping

```json
{
  "mappings": {
    "properties": {
      "text": {
        "type": "text",
        "analyzer": "english",
        "fields": {
          "keyword": { "type": "keyword" }
        }
      },
      "company_id":     { "type": "integer" },
      "company_name":   { "type": "keyword" },
      "quarter":        { "type": "keyword" },
      "fy_year":        { "type": "integer" },
      "event_date":     { "type": "date" },
      "document_type":  { "type": "keyword" },
      "speaker_role":   { "type": "keyword" },
      "speaker_name":   { "type": "keyword" },
      "section_type":   { "type": "keyword" },
      "turn_id":        { "type": "long" },
      "slide_id":       { "type": "long" },
      "section_id":     { "type": "long" },
      "document_id":    { "type": "integer" }
    }
  },
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "analysis": {
      "analyzer": {
        "english": {
          "tokenizer": "standard",
          "filter": ["lowercase", "english_stop", "english_stemmer"]
        }
      }
    }
  }
}
```

---

## 7. FastAPI Endpoint Contracts

All endpoints return JSON. All errors return `{"error": "message", "code": "ERROR_CODE"}`.

### 7.1 Search

```
POST /api/v1/search/keyword
Content-Type: application/json

Request:
{
    "query": string,               // required, min 2 chars
    "companies": [int],            // optional, list of company_ids
    "quarter_from": string | null, // e.g. "1QFY21"
    "quarter_to": string | null,   // e.g. "4QFY26"
    "document_types": [string],    // optional filter
    "speaker_roles": [string],     // optional filter
    "page": int,                   // default 1
    "page_size": int               // default 20, max 100
}

Response 200:
{
    "total": int,
    "page": int,
    "results": [
        {
            "id": int,             // turn_id or slide_id or section_id
            "content_type": string, // turn | slide | section
            "company_id": int,
            "company_name": string,
            "quarter": string,
            "event_date": string,
            "document_type": string,
            "speaker_name": string | null,
            "speaker_role": string | null,
            "snippet": string,     // 300 chars with <mark> tags around matches
            "score": float,
            "document_id": int
        }
    ],
    "took_ms": int
}
```

```
POST /api/v1/search/semantic
Content-Type: application/json

Request: same as keyword search

Response: same shape, score = cosine similarity (0–1)
```

### 7.2 Q&A

```
POST /api/v1/qa/ask
Content-Type: application/json

Request:
{
    "question": string,            // required
    "company_ids": [int] | null,   // scope to companies; null = all
    "quarter_from": string | null,
    "quarter_to": string | null,
    "session_id": string | null    // for 2-turn context; null = new session
}

Response 200 (streaming, text/event-stream):
data: {"type": "token", "content": "Based"}
data: {"type": "token", "content": " on"}
...
data: {"type": "citations", "citations": [
    {
        "id": int,
        "company_name": string,
        "quarter": string,
        "speaker_name": string,
        "document_type": string,
        "snippet": string,
        "document_id": int
    }
]}
data: {"type": "financials", "data": [...]}  // only if relevant
data: {"type": "done"}
```

### 7.3 Companies

```
GET /api/v1/companies
Response: list of {id, scrip_code, name, sector}

GET /api/v1/companies/{id}
Response: company detail + coverage summary

GET /api/v1/companies/{id}/events?quarter=3QFY25
Response: list of events with document links

GET /api/v1/companies/{id}/financials?from=1QFY21&to=4QFY26
Response: list of financial rows ordered by period
```

### 7.4 Management Changes

```
GET /api/v1/management-changes
Query params: company_id, role_category, change_type, from_date, to_date, page, page_size
Response: paginated list of management_change records with company name
```

### 7.5 Health

```
GET /api/v1/health
Response 200: {"status": "ok", "db": "ok", "es": "ok", "timestamp": "..."}
Response 503: {"status": "degraded", "db": "ok", "es": "error", ...}
```

---

## 8. RAG System Prompt

```python
RAG_SYSTEM_PROMPT = """
You are IndiaIR, a research assistant for Indian equity analysts.
You answer questions about Indian listed companies using their public IR filings.

RULES:
1. Answer only from the provided context. Do not use general knowledge about these companies.
2. If context is insufficient, say: "I could not find relevant information for this question in the available filings."
3. Every factual claim must be attributable to a specific passage. Use inline citations: [Company, Quarter, Speaker].
4. For financial figures, always state the unit (Crores INR unless otherwise noted).
5. When comparing companies, structure your answer with one paragraph per company.
6. Do not speculate about future performance beyond what management has explicitly stated.
7. If financial data is provided in the FINANCIALS section, use it to ground commentary in actual numbers.
8. Keep answers concise — 200–400 words unless the question requires more.

FORMAT:
- Write in plain prose, no bullet points.
- Citations inline: [Laurus Labs, 3QFY25, Management]
- Financial figures: "₹1,547 Cr" format

CONTEXT:
{context}

FINANCIALS (if relevant):
{financials}
"""
```

---

## 9. Chunking Strategy

For the vector index, chunks are generated as follows:

- **Concall turns:** Each turn is one chunk. Do not split turns. If a turn exceeds 400 tokens, split at sentence boundaries.
- **Slides:** Each slide = one chunk (title + body).
- **Press release sections:** Each section = one chunk. If management_commentary section exceeds 400 tokens, split at paragraph boundaries.
- **Overlap:** 0 tokens between turn-based chunks (turns are natural boundaries). 50-token overlap for intra-section splits.
- **Minimum chunk size:** 20 tokens. Discard shorter chunks (moderator intros, page headers).

---

## 10. Idempotency Rules

All pipeline operations must be idempotent:

| Operation | Idempotency mechanism |
|---|---|
| Download PDF | Skip if `file_hash` already in `documents` table |
| Extract turns | Delete existing turns for document_id before re-inserting |
| Extract financials | UPDATE if `(company_id, period, period_type)` exists; detect restatement |
| Index to Elasticsearch | Use document `id` as ES `_id`; upsert not insert |
| Generate embeddings | Delete existing embeddings for document_id before re-inserting |
| Management changes | Deduplicate on `(company_id, person_name, change_type, effective_date)` |

---

*Last Updated: April 2026 | Version 1.0*
