# Product Requirements Document
## IndiaIR — Indian Investor Relations Intelligence Platform
### Version 1.0 | MVP | April 2026

---

## 1. Executive Summary

IndiaIR is a research intelligence platform that ingests, extracts, indexes, and makes queryable all public investor relations content filed by listed Indian companies on BSE India. The MVP covers 30 companies across 5 years of historical filings, spanning concall transcripts, investor presentations, quarterly results press releases, and management change announcements. The primary user is a sell-side or buy-side equity analyst covering Indian markets.

The core value proposition: replace hours of manual transcript reading, filing triage, and cross-company comparison with a single semantic search and RAG-powered Q&A interface — covering not just what management said on concalls, but what the company formally announced and who is running it.

---

## 2. Problem Statement

### 2.1 Current State

Indian equity analysts seeking to research company commentary face the following workflow:

1. Navigate to BSE India's corporate filings portal
2. Manually search by company and date range
3. Download individual PDFs one at a time
4. Read through transcripts manually to find relevant passages
5. Repeat across multiple companies for cross-company comparisons
6. Maintain their own notes and Excel trackers for management commentary over time

There is no tool that aggregates, extracts, and makes searchable the full corpus of Indian IR content in a unified interface.

### 2.2 Pain Points

| Pain Point | Severity | Frequency |
|---|---|---|
| Cannot search across companies simultaneously | High | Daily |
| Cannot track how management language has evolved over quarters | High | Weekly |
| BSE portal is slow and requires manual navigation per company | Medium | Daily |
| No way to compare what two companies said about the same topic | High | Weekly |
| Scanned PDFs are unsearchable | Medium | Weekly |
| No structured speaker attribution in existing tools | Medium | Weekly |
| No unified view of management changes across covered companies | High | Monthly |
| Press release announcements are buried in BSE filing noise | Medium | Weekly |
| Cannot correlate a management change with subsequent earnings commentary | High | Occasional |

### 2.3 What Exists Today

- **BSE/NSE portals** — dumb file repositories, no search intelligence
- **Bloomberg/Refinitiv** — transcript coverage for large-caps only, poor search UX, $25k+/year
- **Quartr** — strong global product, thin Indian coverage, drops off below Nifty 100
- **Trendlyne/Tijori/Screener** — financial data with filing links, no transcript intelligence layer
- **No product** currently does semantic search across Indian concall transcripts for mid/small-cap companies

---

## 3. Goals and Non-Goals

### 3.1 MVP Goals

- Ingest and index all concall transcripts, investor presentations, quarterly results press releases, and management change announcements for 30 target companies, going back 5 years (FY21–FY26)
- Extract and store a standardised set of consolidated P&L metrics from quarterly and annual results for all 30 companies
- Achieve >85% clean text extraction quality across the corpus
- Enable full-text keyword search across the entire corpus with company/date filters
- Enable semantic (meaning-based) search using natural language queries
- Enable RAG-powered Q&A: ask a question, get an answer with citations to specific transcript passages, with financial context surfaced alongside commentary
- Provide a functional web UI usable by non-technical analysts

### 3.2 Non-Goals for MVP

- Live or real-time transcript capture
- Coverage beyond the 30 target companies
- Audio ingestion or ASR pipeline
- Balance sheet and cash flow statement extraction (deferred — P&L only for MVP)
- Segment-level financial data extraction (inconsistent across companies, deferred)
- Financial ratio calculations and derived metrics (Revenue growth, EBITDA CAGR, etc. — deferred)
- Restatement auto-correction (flag restatements; do not auto-adjust historical series)
- Mobile application
- User management, multi-tenancy, or billing
- Coverage of NSE-only filings (BSE is sufficient for target universe)
- Annual reports (high OCR complexity, lower query frequency)

---

## 4. Target Users

### Primary User — Sell-Side Analyst (MVP focus)

- Covers 10–20 companies in a sector
- Reads 3–5 concall transcripts per quarter per covered company
- Needs to cross-reference management commentary across quarters and companies
- Writes research notes that cite management commentary
- Technical comfort: moderate (uses Excel, Python occasionally, not a developer)

### Secondary User — Buy-Side Analyst

- Covers broader universe, less depth per company
- Values speed of surfacing relevant commentary over depth of reading
- Often works across multiple sectors

### Out of Scope for MVP

- Retail investors
- Corporate IR teams
- Quantitative / systematic funds (API access)

---

## 5. Target Company Universe (MVP — 30 Companies)

Selection criteria: consistent BSE transcript filing history, analyst coverage relevance, mix of sectors.

### Suggested Universe

| # | Company | BSE Scrip | Sector |
|---|---|---|---|
| 1 | Laurus Labs | 540222 | CDMO / API |
| 2 | Divi's Laboratories | 532488 | CDMO / API |
| 3 | Syngene International | 539268 | CDMO |
| 4 | Piramal Pharma | 543635 | CDMO / Formulations |
| 5 | Cohance Lifesciences | 543350 | CDMO |
| 6 | Anthem Biosciences | 544210 | CDMO |
| 7 | Sai Life Sciences | 544282 | CDMO |
| 8 | Neuland Laboratories | 524558 | API |
| 9 | Sun Pharmaceutical | 524715 | Formulations |
| 10 | Dr. Reddy's Laboratories | 500124 | Formulations |
| 11 | Cipla | 500087 | Formulations |
| 12 | Lupin | 500257 | Formulations |
| 13 | Mankind Pharma | 543904 | Domestic Formulations |
| 14 | Torrent Pharmaceuticals | 500420 | Domestic Formulations |
| 15 | Alkem Laboratories | 539523 | Domestic Formulations |
| 16 | Ipca Laboratories | 524494 | Domestic Formulations |
| 17 | Max Healthcare | 543220 | Hospitals |
| 18 | Apollo Hospitals | 508869 | Hospitals |
| 19 | Narayana Hrudayalaya | 539551 | Hospitals |
| 20 | Fortis Healthcare | 532843 | Hospitals |
| 21 | Metropolis Healthcare | 542650 | Diagnostics |
| 22 | Dr. Lal PathLabs | 539524 | Diagnostics |
| 23 | Thyrocare Technologies | 539871 | Diagnostics |
| 24 | MedPlus Health Services | 543741 | Pharmacy Retail |
| 25 | Poly Medicure | 531768 | Med Devices |
| 26 | Infosys | 500209 | IT (benchmark) |
| 27 | TCS | 532540 | IT (benchmark) |
| 28 | HDFC Bank | 500180 | BFSI (benchmark) |
| 29 | Reliance Industries | 500325 | Conglomerate (benchmark) |
| 30 | Asian Paints | 500820 | Consumer (benchmark) |

*IT/BFSI/Consumer benchmarks included to validate search quality and as reference for OCR pipeline testing — these companies have the best transcript filing consistency.*

---

## 6. Functional Requirements

### 6.1 Data Ingestion

#### 6.1.1 BSE Polling

| Requirement | Detail |
|---|---|
| Source | BSE India corporate filings API (`api.bseindia.com`) |
| Trigger | Scheduled daily poll per company (run at 09:00 IST) |
| Historical backfill | On first run, backfill all filings from April 2020 to present |
| Deduplication | Hash-based on BSE filing ID; never re-download same filing |
| Storage | Raw PDFs stored in object storage (S3/GCS) with metadata in Postgres |
| Failure handling | Retry 3x with exponential backoff; alert on persistent failure |

#### 6.1.2 Document Classification

Each downloaded filing must be classified into one of:

- `concall_transcript` — Post-call PDF transcript
- `investor_presentation` — Slide deck (earnings or otherwise)
- `results_press_release` — Quarterly/annual results press release (financials + management commentary)
- `management_change` — Board/KMP appointments, resignations, retirements (Director Report, intimations)
- `board_meeting_outcome` — Outcome note with no substantive content beyond dates and resolutions
- `other` — Everything else

Classification method: BSE category code + filename keyword matching (regex). LLM fallback for ambiguous cases.

Documents proceeding to extraction pipeline:

| Document Type | Extraction Target |
|---|---|
| `concall_transcript` | Speaker turns (management + analyst) |
| `investor_presentation` | Slide-level text |
| `results_press_release` | Full text, structured into sections |
| `management_change` | Structured event record (person, role, change type, effective date) |
| `board_meeting_outcome` | Skip — low information density |
| `other` | Skip |

#### 6.1.3 Coverage Expectation

| Document Type | Expected Completeness |
|---|---|
| Concall transcripts (Nifty 100 companies) | >90% of calls, FY21–FY26 |
| Concall transcripts (mid-cap) | ~70–80% (some companies file inconsistently) |
| Investor presentations | ~85% (not all companies file these separately) |
| Results press releases | >95% (BSE mandated for listed companies) |
| Management change announcements | >95% (BSE mandated, SEBI Reg 30 filings) |

### 6.2 PDF Extraction

#### 6.2.1 Text Extraction Pipeline

Step 1 — PDF type detection:
- Attempt text extraction with pymupdf
- If extracted text length < 200 characters per page on average → classify as scanned PDF
- If extracted text quality score (proportion of valid unicode, word recognition rate) < 0.7 → classify as low-quality text PDF → route to OCR

Step 2 — Extraction by type:
- **Text PDF**: pymupdf extraction → unicode normalization → ligature correction
- **Scanned PDF**: Tesseract OCR (eng) at 300 DPI → text cleaning
- **Low-quality text PDF**: AWS Textract (or Google Document AI) for higher accuracy

Step 3 — Quality validation:
- Word count per page must exceed 50
- Proportion of non-ASCII characters must be < 15%
- Flag and log all extractions below quality threshold for manual review

#### 6.2.2 Concall Transcript Parser

Concall transcripts must be parsed into structured speaker turns:

```
{
  "event_id": "...",
  "company": "Laurus Labs",
  "date": "2025-01-23",
  "quarter": "3QFY25",
  "turns": [
    {
      "turn_id": 1,
      "speaker_raw": "V.V. Ravi Kumar",
      "speaker_role": "management",
      "speaker_title": "CFO",
      "text": "Thank you. On the margin side..."
    },
    {
      "turn_id": 2,
      "speaker_raw": "Alankar Garude",
      "speaker_role": "analyst",
      "speaker_org": "Kotak Securities",
      "text": "My question is on the CDMO pipeline..."
    }
  ]
}
```

Speaker attribution logic:
- Parse speaker header lines using regex patterns for common transcript formats (boldface name + colon, all-caps name + colon, parenthetical affiliation)
- Classify as `management` or `analyst` based on context (opening lines, affiliation parsing)
- Moderator turns are classified separately and excluded from search index
- Unattributable turns are classified as `unknown` and included with lower search priority

#### 6.2.3 Investor Presentation Parser

Slide decks are parsed at the slide level:
- Extract text per slide (title + body)
- Preserve table contents where detectable
- Store slide number as metadata for citation

#### 6.2.4 Results Press Release Parser

Quarterly and annual results press releases are parsed as follows:
- Full text extraction (these are almost always text PDFs)
- Section detection: financial highlights, operational highlights, management commentary/outlook
- The management commentary / outlook section is the high-value portion — extract and index separately with tag `press_release_commentary`
- Financial tables extracted as structured text (not parsed into numbers — that is out of scope)

The management commentary section in a results press release is often more carefully worded than a concall — it represents the company's official forward-looking statement. It should be indexed and searchable with the same priority as concall management turns.

#### 6.2.5 Management Change Parser

Management change filings (SEBI Regulation 30 intimations, Director Reports) are parsed into structured event records rather than free text:

```
{
  "event_id": "...",
  "company": "Laurus Labs",
  "filing_date": "2024-09-15",
  "change_type": "appointment" | "resignation" | "retirement" | "cessation" | "re-appointment",
  "person_name": "Dr. Satyanarayana Chava",
  "role": "Managing Director & CEO",
  "role_category": "KMP" | "Board-Executive" | "Board-NonExecutive" | "Board-Independent",
  "effective_date": "2024-10-01",
  "reason": "Superannuation" | "Personal reasons" | "Better opportunity" | null,
  "additional_charge": false,
  "raw_text": "..."
}
```

Extraction method: LLM-based structured extraction from the filing text. These filings follow a semi-standard format under SEBI Reg 30 but vary enough that regex alone is insufficient.

Key design decisions:
- `role_category` is inferred from the role title (MD/CEO/CFO/COO → KMP; Chairman/Director → Board)
- `reason` is extracted only when explicitly stated; otherwise null (do not infer)
- Multiple changes in a single filing are extracted as separate records
- Re-appointments and additional charge designations are included — they are material for tracking leadership continuity

These records populate a dedicated `management_changes` table and also feed the company timeline view.

#### 6.2.6 Financial Data Extraction

**Source documents:** Quarterly results press releases (Reg 33 filings) and annual results press releases. These are the same documents already being downloaded and classified — no new source required. The financial tables in these PDFs are the primary extraction target.

**Scope — MVP line items (consolidated P&L only):**

| Line Item | Label | Notes |
|---|---|---|
| Net Revenue / Net Sales | `revenue` | Use net of GST/excise; note if company reports gross |
| EBITDA | `ebitda` | Extract directly if stated; compute as EBIT + D&A if not |
| EBITDA Margin | `ebitda_margin` | Compute from revenue + EBITDA; do not extract stated figure (often inconsistently defined) |
| Depreciation & Amortisation | `da` | Required for EBITDA computation fallback |
| EBIT | `ebit` | Extract if stated |
| Finance Costs / Interest | `finance_costs` | |
| PBT | `pbt` | Profit Before Tax |
| Tax | `tax` | |
| PAT | `pat` | Profit After Tax (attributable to owners, not minority) |
| EPS (Basic, Diluted) | `eps_basic`, `eps_diluted` | |
| Shares Outstanding | `shares` | Required for EPS cross-check |

**Quarterly vs. annual cadence:**

- Extract both quarterly (Q1–Q4) and full-year figures from results filings
- For annual figures, prefer the standalone annual results filing over summing quarterly (avoids rounding and restatement issues)
- Store both `period_type: quarterly` and `period_type: annual` with the same schema

**Extraction method:**

Financial table extraction from Indian press release PDFs is non-trivial. Use a two-pass approach:

*Pass 1 — Structured table extraction:* Use `camelot` (for text PDFs) or `pdfplumber` to extract table cells. Map rows to line items using a fuzzy match against a canonical label dictionary (handles variations like "Revenue from Operations", "Net Revenue", "Total Income from Operations").

*Pass 2 — LLM validation:* For any quarter where extracted figures fail internal consistency checks (e.g., Revenue − EBITDA ≠ EBIT within 1% tolerance, or EPS × shares ≠ PAT within 2%), run the raw table text through Claude Haiku with a structured extraction prompt. LLM pass is the fallback, not the primary method — it is slower and more expensive.

**Consistency checks (mandatory before storing):**

- PAT / Shares ≈ EPS (within 2%)
- EBITDA − D&A ≈ EBIT (within 1%)
- QoQ and YoY changes flagged if > 50% in either direction (likely extraction error or restatement)
- Negative revenue or EBITDA flagged for manual review

**Restatement handling:**

When a company restates a prior quarter (detected by re-filing or by a significant change in a previously stored value), store the new figure with a `restated: true` flag and preserve the original. Do not silently overwrite. Surface restatement flags in the UI.

**What is explicitly excluded from MVP:**

- Balance sheet (assets, liabilities, working capital)
- Cash flow statement (OCF, capex, FCF)
- Segment revenue breakdown
- Standalone (non-consolidated) figures — store only consolidated
- Forex impact disclosures
- Guidance figures (these appear in transcripts and press release commentary, not in financial tables — covered by RAG)

### 6.3 Storage and Indexing

#### 6.3.1 Postgres Schema (Metadata)

Key tables:

- `companies` — scrip code, name, sector, BSE ID
- `events` — company, event date, event type, quarter label, filing ID
- `documents` — event FK, document type, BSE URL, S3 path, extraction status, quality score
- `turns` — document FK, turn index, speaker raw, speaker role, speaker org, text
- `slides` — document FK, slide number, title, body text
- `press_release_sections` — document FK, section type (financial_highlights / operational / management_commentary), text
- `management_changes` — company FK, filing date, change type, person name, role, role category, effective date, reason, raw text
- `financials` — company FK, period (e.g., `3QFY25`), period_type (quarterly / annual), revenue, ebitda, ebitda_margin, da, ebit, finance_costs, pbt, tax, pat, eps_basic, eps_diluted, shares, restated (bool), extraction_method (table / llm), quality_flag

#### 6.3.2 Elasticsearch Index

Index name: `india_ir_content`

Fields:
- `text` — full text (analyzed, English analyzer)
- `company` — keyword
- `quarter` — keyword (format: `3QFY25`)
- `fy_year` — integer
- `event_date` — date
- `speaker_role` — keyword (`management` / `analyst` / `unknown` / `press_release` / `n_a`)
- `document_type` — keyword (`concall_transcript` / `investor_presentation` / `results_press_release` / `management_change`)
- `section_type` — keyword (for press releases: `management_commentary` / `financial_highlights` / `operational`)
- `turn_id`, `document_id` — for citation linking

Management change records are **not** indexed in Elasticsearch for full-text search — they are structured data stored in Postgres and surfaced via the dedicated management changes view. They are included in the RAG context when a query explicitly references leadership or personnel.

#### 6.3.3 Vector Index (pgvector)

- Chunking: 300-token sliding window with 50-token overlap, at the turn level (don't split turns)
- Embedding model: `text-embedding-3-small` (OpenAI) or `intfloat/e5-base-v2` (open source)
- Stored in Postgres `embeddings` table via pgvector extension
- Each chunk carries full metadata (company, date, quarter, speaker role, document type)

### 6.4 Search and Query Interface

#### 6.4.1 Keyword Search

- Full-text search across all indexed turns and slides
- Filters: company (multi-select), quarter range, document type, speaker role
- Results show: company, date, quarter, speaker name/role, passage snippet with keyword highlighted
- Pagination: 20 results per page
- Sort: relevance (default), date descending, date ascending

#### 6.4.2 Semantic Search

- Natural language query input
- Returns top-20 semantically similar passages
- Same filter options as keyword search
- Results show cosine similarity score (internal, not surfaced in UI)
- Hybrid mode: combine keyword + semantic scores (RRF or weighted sum)

#### 6.4.3 RAG Q&A

User inputs a natural language question. System:

1. Embeds the question
2. Retrieves top-10 relevant chunks (filtered by company/date if specified)
3. If the question references financial performance, pulls relevant quarterly financials from Postgres and appends as structured context
4. Constructs prompt with retrieved chunks + financial context
5. Returns a structured answer with inline citations

Citation format: `[Company Name, Quarter, Speaker Name]` for transcript passages; `[Company Name, Quarter, Financials]` for financial data points.

The combination of financial data and transcript commentary in a single RAG context is the core differentiator — it enables answers like *"Laurus Labs guided for margin expansion in 3QFY25 — their actual EBITDA margin that quarter was 18.2%, up from 16.8% in 3QFY24"* without the analyst having to cross-reference two separate tools.

Example queries the system must handle:

- *"What has Laurus Labs management said about CDMO capacity utilization over the last 6 quarters?"*
- *"Which companies mentioned inventory destocking in 2QFY25?"*
- *"What is Syngene's guidance on FY26 revenue?"*
- *"Compare what Divi's and Laurus have said about US generics pricing pressure"*
- *"What did Piramal Pharma say in its 3QFY25 results press release about the CDMO outlook?"*
- *"Which companies in the coverage universe changed their CFO in the last 2 years?"*
- *"Who is the current CEO of Cohance Lifesciences and when did they take over?"*
- *"Show me all management changes at Syngene since FY22"*
- *"Laurus Labs said margins would recover — did they? Show me the last 6 quarters of EBITDA margin"*
- *"Which covered CDMOs grew revenue more than 20% in FY25?"*
- *"Compare EBITDA margins across Divi's, Laurus, and Syngene for FY24 and FY25"*

#### 6.4.5 Management Changes View

A dedicated cross-company view showing all KMP and Board-level personnel changes across the covered universe:

- Filterable by: company, role category (KMP / Board-Executive / Board-Independent), change type (appointment / resignation / retirement), date range
- Default sort: most recent first
- Each row shows: company, person name, role, change type, effective date, reason (if stated)
- Clicking a row shows the full filing text and links to subsequent concall transcripts — so an analyst can immediately read what management said post-change
- Company page includes a dedicated management changes panel in the timeline, showing the evolution of key roles over the 5-year period

This view solves a specific analyst workflow: when a CFO or CEO change is announced, the analyst needs to (a) confirm the facts, (b) understand the reason, and (c) assess whether subsequent earnings commentary reflects a change in tone or strategy. Today this requires multiple manual steps across BSE filings, news, and transcript reading. IndiaIR surfaces all three in one place.

Per-company view showing:
- All indexed events in chronological order (quarter, event type)
- Click to read full transcript in-app (rendered from parsed turns)
- Quick summary of each event (LLM-generated, 3–5 bullet points)

### 6.5 Web UI

#### 6.5.1 Pages

| Page | Description |
|---|---|
| Home / Search | Global search bar (keyword or natural language), filter panel, results |
| Q&A | Question input, answer with citations, source passage viewer, financial context panel |
| Company Page | Timeline of events, financials chart, event summaries, management changes log, link to full transcript viewer |
| Financials View | Multi-company financial comparison — revenue, EBITDA, PAT, margins across quarters, with restatement flags |
| Transcript Viewer | Full rendered transcript with speaker turns, keyword highlight, scroll-to-turn |
| Management Changes | Cross-company view — all KMP/Board changes across covered universe, filterable by company, role, change type, date range |
| Coverage Dashboard | Admin view — coverage status per company, extraction quality, missing filings, financial extraction quality |

#### 6.5.2 UI Requirements

- Functional over beautiful at MVP stage — Streamlit or a minimal React app is acceptable
- Search results must load in < 3 seconds for keyword search
- RAG Q&A response must begin streaming within 5 seconds
- Must be usable on a standard 13-inch laptop screen
- No mobile optimization required for MVP

---

## 7. Non-Functional Requirements

### 7.1 Performance

| Operation | Target Latency |
|---|---|
| Keyword search (no filters) | < 2 seconds |
| Keyword search (with filters) | < 2 seconds |
| Semantic search | < 3 seconds |
| RAG Q&A (first token) | < 5 seconds |
| Full transcript page load | < 2 seconds |

### 7.2 Data Quality

| Metric | Target |
|---|---|
| Text extraction quality (text PDFs) | > 95% of turns/sections parseable |
| Text extraction quality (scanned PDFs) | > 80% of turns parseable |
| Speaker attribution accuracy | > 85% of turns correctly attributed to management vs analyst |
| Press release section detection accuracy | > 90% (management commentary section correctly identified) |
| Management change structured extraction accuracy | > 92% (person name, role, change type, effective date all correctly extracted) |
| Quarter label accuracy | 100% (verified against BSE filing date) |
| Filing coverage (Nifty 100 companies in universe) | > 90% of calls over 5-year period |
| Management change filing coverage | > 95% (SEBI Reg 30 mandated, consistently filed) |

### 7.3 Reliability

- System must handle incremental daily ingestion without manual intervention
- Failed extractions must be logged and surfaced in coverage dashboard
- No data loss on pipeline restarts

### 7.4 Security

- No user authentication required for MVP (single-user or trusted internal access)
- API keys (OpenAI/Anthropic) stored in environment variables, never in code
- BSE polling respects rate limits (max 1 request/second per company)

---

## 8. Technical Architecture

### 8.1 Stack

| Layer | Technology | Rationale |
|---|---|---|
| Ingestion scheduler | APScheduler (Python) | Lightweight, no separate broker needed at MVP scale |
| PDF extraction | pymupdf + Tesseract | Open source, sufficient quality for text PDFs |
| OCR fallback | AWS Textract | Higher accuracy for scanned PDFs, pay-per-use |
| Metadata store | PostgreSQL | Relational structure for companies/events/turns |
| Full-text search | Elasticsearch (Docker) | Best-in-class text search, filterable metadata |
| Vector search | pgvector | Co-located with Postgres, avoids separate vector DB at MVP scale |
| Embeddings | text-embedding-3-small | Cost-effective, strong quality |
| LLM (RAG) | Claude Sonnet via Anthropic API | Quality, citation handling |
| Object storage | AWS S3 (or local filesystem for MVP) | PDF archive |
| Backend API | FastAPI | Fast, async-native |
| Frontend | Streamlit (MVP) → React (post-MVP) | Rapid iteration at MVP stage |
| Deployment | Single EC2 instance or local server (MVP) | No Kubernetes overhead at this scale |

### 8.2 Data Flow

```
BSE India API
    ↓ (daily poll)
Filing Metadata + PDF Download
    ↓
Document Classifier
    ↓               ↓
Concall Transcript  Investor Presentation
    ↓                       ↓
PDF Type Detection      PDF Type Detection
    ↓                       ↓
Text/OCR Extraction     Text/OCR Extraction
    ↓                       ↓
Speaker Turn Parser     Slide Parser
    ↓                       ↓
Postgres (metadata + turns + slides)
    ↓               ↓
Elasticsearch       pgvector
(full-text)         (embeddings)
    ↓               ↓
        FastAPI
            ↓
        Streamlit UI
```

### 8.3 Repository Structure

```
india-ir/
├── ingestion/
│   ├── bse_poller.py           # BSE API polling, PDF download
│   ├── document_classifier.py  # Filing type classification
│   └── company_master.py       # Scrip code master, company metadata
├── extraction/
│   ├── pdf_detector.py         # Text vs scanned PDF detection
│   ├── text_extractor.py       # pymupdf extraction + cleaning
│   ├── ocr_extractor.py        # Tesseract / Textract fallback
│   ├── transcript_parser.py    # Speaker turn parsing
│   ├── slide_parser.py         # Presentation slide parsing
│   ├── press_release_parser.py # Section detection + management commentary extraction
│   ├── mgmt_change_parser.py   # LLM-based structured extraction of Reg 30 filings
│   ├── financial_extractor.py  # Table extraction (camelot/pdfplumber) + LLM fallback
│   ├── financial_validator.py  # Consistency checks, restatement detection, quality flags
│   └── label_dictionary.py     # Canonical P&L line item label → field mapping
├── indexing/
│   ├── es_indexer.py           # Elasticsearch indexing
│   ├── embedding_indexer.py    # Chunking + pgvector indexing
│   └── quality_checker.py      # Extraction quality validation
├── search/
│   ├── keyword_search.py       # ES full-text search
│   ├── semantic_search.py      # pgvector similarity search
│   └── rag.py                  # Retrieval + financial context + Claude API Q&A
├── api/
│   └── main.py                 # FastAPI routes
├── ui/
│   └── app.py                  # Streamlit UI
├── db/
│   ├── models.py               # SQLAlchemy models
│   └── migrations/             # Alembic migrations
├── scripts/
│   ├── backfill.py             # Historical backfill runner
│   └── coverage_report.py      # Coverage dashboard data
├── config.py
├── requirements.txt
└── docker-compose.yml          # Postgres + Elasticsearch
```

---

## 9. Implementation Phases

### Phase 0 — OCR Validation (1 week)

**Goal:** Validate text extraction quality before building anything else.

Tasks:
- Download 30 concall transcripts manually — 10 from large-caps (likely text PDFs), 10 from mid-caps, 10 from 2020–2021 (more likely scanned)
- Run through pymupdf + Tesseract pipeline
- Manually review output quality for speaker attribution parsability
- Define quality thresholds
- Decision gate: if scanned PDF quality < 70%, budget for AWS Textract before proceeding

Deliverable: quality report with pass/fail by document type and company size.

### Phase 1 — Data Warehouse (2–3 weeks)

**Goal:** Get the full 5-year corpus on disk and in Postgres.

Tasks:
- Build `bse_poller.py` and `company_master.py`
- Build `document_classifier.py` — including classification of Reg 30 management change filings
- Run historical backfill for all 30 companies
- Build `text_extractor.py`, `transcript_parser.py`, `press_release_parser.py`, `mgmt_change_parser.py`, `financial_extractor.py`, and `financial_validator.py`
- Populate Postgres `companies`, `events`, `documents`, `turns`, `press_release_sections`, `management_changes`, and `financials` tables
- Build `coverage_report.py` to monitor gaps

Success metric: > 85% of expected filings downloaded and turns extracted for Nifty 100 companies in universe. Financial extraction passes consistency checks for > 80% of quarterly periods across all 30 companies. Management changes table populated with > 90% of known KMP changes for at least 5 test companies.

### Phase 2 — Search Index (1–2 weeks)

**Goal:** Full-text keyword search working end-to-end.

Tasks:
- Spin up Elasticsearch via Docker
- Build `es_indexer.py`
- Build `keyword_search.py` with filter support
- Build minimal Streamlit UI: search bar + filter panel + results list

Success metric: query "capacity utilization" across all companies in < 2 seconds, results are accurate and well-attributed.

### Phase 3 — Semantic Search and RAG (2–3 weeks)

**Goal:** Natural language Q&A with citations.

Tasks:
- Set up pgvector
- Build `embedding_indexer.py` — chunking + embedding + storage
- Build `semantic_search.py`
- Build `rag.py` — retrieval + financial context injection + Claude API prompt construction + streaming response
- Add Q&A page to Streamlit UI
- Build company page with financials chart (revenue, EBITDA margin over quarters) and transcript timeline
- Build financials comparison view (multi-company, multi-metric, multi-quarter)
- Build management changes view (cross-company + per-company panel)
- Wire press release management commentary sections into RAG context

Success metric: RAG correctly answers all 11 benchmark questions listed in section 6.4.3 with accurate citations. Financial data matches manually verified figures for 3 spot-checked companies across 8 quarters each. Management changes view correctly shows full KMP/Board history for at least 5 spot-checked companies.

### Phase 4 — Incremental Ingestion and Hardening (1 week)

**Goal:** System runs reliably without manual intervention.

Tasks:
- Wire up APScheduler for daily BSE polling
- Build failure alerting (email or Slack webhook on extraction failures)
- Build coverage dashboard in UI
- Performance testing and query optimization

---

## 10. Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Scanned PDF OCR quality insufficient | Medium | High | Phase 0 validation gate; AWS Textract fallback budget |
| BSE API structure changes or rate limiting | Low | High | Build scraper fallback (direct HTML); cache aggressively |
| Inconsistent transcript filing by mid-caps | High | Medium | Accept coverage gaps; surface clearly in UI |
| Speaker attribution fails on non-standard formats | Medium | Medium | Manual correction pipeline; `unknown` fallback doesn't break search |
| Press release management commentary section detection fails | Medium | Low | Section detection failure degrades to indexing full press release text — still searchable, just less structured |
| Financial table extraction fails (bad PDF layout) | High | Medium | Two-pass approach (camelot → LLM fallback); consistency check gates storage; quality flag surfaced in UI |
| Company uses non-standard P&L line item labels | High | Medium | Fuzzy label matching against canonical dictionary; LLM fallback for unmatched labels |
| Silent restatements not detected | Medium | High | Flag any stored value that changes by >5% on re-ingestion; surface in UI |
| EBITDA not explicitly stated (must be computed) | Medium | Low | Compute from EBIT + D&A; flag computed vs. extracted in schema |
| Management change LLM extraction hallucination | Low | High | Validate extracted fields against filing date and known role taxonomy; surface raw text alongside structured record for analyst verification |
| Multiple changes in one Reg 30 filing parsed as single record | Medium | Medium | Design parser to handle multi-person filings explicitly; test against known multi-change filings |
| Elasticsearch operational complexity | Low | Medium | Use managed ES (Elastic Cloud) if local Docker is problematic |
| LLM API costs (RAG + mgmt change + financial fallback extraction) | Low at MVP | Medium | Cache management change and financial extractions; rate limit Q&A queries |
| BSE terms of service on bulk scraping | Medium | Medium | Operate as internal research tool; not a public product at MVP |

---

## 11. Success Metrics

### MVP Success Criteria

| Metric | Target |
|---|---|
| Companies covered | 30 |
| Historical depth | FY21–FY26 (5 years) |
| Extraction quality (text PDFs) | > 95% |
| Extraction quality (scanned PDFs) | > 80% |
| Financial extraction pass rate (consistency checks) | > 80% of quarterly periods without manual intervention |
| Financial data accuracy (spot-check vs. manual) | < 1% error on revenue, EBITDA, PAT for verified quarters |
| Management change extraction accuracy | > 92% |
| Keyword search latency | < 2 seconds |
| RAG Q&A accuracy (benchmark questions) | 11 / 11 correct with accurate citations |
| Time to answer a cross-company query vs. manual | 30 seconds vs. 2+ hours |
| Management change timeline completeness | > 95% of KMP/Board changes visible per company |

### Qualitative Validation

After MVP, the system is shown to 3–5 buy-side analysts. Success if:
- They immediately understand the value without explanation
- They spontaneously identify a query they would use it for
- At least 3 of 5 say they would pay for access

---

## 12. Out of Scope — Future Versions

The following are explicitly deferred to post-MVP:

- **Live transcripts** — YouTube capture + VoIP dial-in pipeline
- **Expanded coverage** — Nifty 500 and beyond
- **NSE filings** integration
- **Annual reports** — high OCR complexity, lower query frequency
- **Balance sheet and cash flow extraction** — deferred to post-MVP
- **Segment-level financial data** — inconsistent across companies, high extraction complexity
- **Derived financial ratios** — revenue growth, EBITDA CAGR, return ratios (computable post-MVP from stored P&L data)
- **Consensus estimates and vs-estimates tracking** — requires external estimates data source
- **Alerts** — keyword-triggered notifications on new filings
- **API access** — for quant/systematic users
- **Multi-tenancy and billing** — for external productization
- **Keyword trend charts** — frequency of a term across quarters over time
- **Speaker profiling** — track individual analyst questions across companies over time
- **Export** — CSV/Excel export of search results and financial data

---

## 13. Open Questions

1. **OCR service decision** — Tesseract (free, lower quality) vs. AWS Textract (~$1.50/1000 pages) vs. Google Document AI. To be resolved in Phase 0 based on quality test results.

2. **Embedding model** — OpenAI `text-embedding-3-small` ($0.02/1M tokens, managed) vs. `intfloat/e5-base-v2` (free, self-hosted). At MVP corpus size (~5M tokens for 30 companies × 5 years), OpenAI cost is < $1 total. OpenAI preferred for MVP simplicity.

3. **UI framework** — Streamlit is fastest to build but has UX limitations. Accept this for MVP; reassess if showing to external users.

4. **BSE API reliability** — The undocumented BSE API has worked reliably for years but is not guaranteed. Need a direct HTML scraper fallback. Assess in Phase 1.

5. **Quarter label normalization** — BSE filing dates don't always map cleanly to quarters (e.g., a call held in April for Q4 results). Define normalization rules: use BSE filing date to infer FY quarter; flag for manual review if ambiguous.

6. **Management change LLM extraction model** — Use Claude Haiku (fast, cheap) for structured extraction of Reg 30 filings, with a validation pass that checks extracted fields against a known role taxonomy. Budget ~$0.01–0.02 per filing at MVP scale.

7. **Management changes: include independent directors?** — Reg 30 filings include Independent Director appointments and resignations, which are a governance signal but lower analytical priority than KMP changes. Decision: include all, but surface KMP changes more prominently via role_category filter in the UI.

8. **Financial extraction: camelot vs. pdfplumber** — Both libraries extract tables from text PDFs but perform differently on multi-column and merged-cell layouts common in Indian press releases. Test both on 10 sample filings in Phase 0 to determine default; retain both as selectable strategies per document.

9. **EBITDA definition consistency** — Indian companies define EBITDA differently (some include other income, some exclude exceptional items). For MVP, always compute EBITDA as Revenue − Operating Expenses (i.e., exclude other income and exceptional items) for cross-company comparability. Flag any quarter where the company's stated EBITDA deviates from the computed figure by > 3%.

---

*Document Owner: Research Team*
*Last Updated: April 2026*
*Status: Draft — pending Phase 0 validation*
