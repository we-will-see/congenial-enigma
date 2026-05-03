# Product Requirements Document
## IndiaIR — Indian Investor Relations Intelligence Platform
### Version 1.0 | MVP | April 2026

---

## 1. Executive Summary

IndiaIR is a research intelligence platform that ingests, extracts, indexes, and makes queryable all public investor relations content filed by listed Indian companies on BSE India. The MVP covers 30 companies across 5 years of historical filings, with a focus on concall transcripts and investor presentations. The primary user is a sell-side or buy-side equity analyst covering Indian markets.

The core value proposition: replace hours of manual transcript reading and cross-company comparison with a single semantic search and RAG-powered Q&A interface.

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

### 2.3 What Exists Today

- **BSE/NSE portals** — dumb file repositories, no search intelligence
- **Bloomberg/Refinitiv** — transcript coverage for large-caps only, poor search UX, $25k+/year
- **Quartr** — strong global product, thin Indian coverage, drops off below Nifty 100
- **Trendlyne/Tijori/Screener** — financial data with filing links, no transcript intelligence layer
- **No product** currently does semantic search across Indian concall transcripts for mid/small-cap companies

---

## 3. Goals and Non-Goals

### 3.1 MVP Goals

- Ingest and index all concall transcripts and investor presentations for 30 target companies, going back 5 years (FY21–FY26)
- Achieve >85% clean text extraction quality across the corpus
- Enable full-text keyword search across the entire corpus with company/date filters
- Enable semantic (meaning-based) search using natural language queries
- Enable RAG-powered Q&A: ask a question, get an answer with citations to specific transcript passages
- Provide a functional web UI usable by non-technical analysts

### 3.2 Non-Goals for MVP

- Live or real-time transcript capture
- Coverage beyond the 30 target companies
- Audio ingestion or ASR pipeline
- Financial data (earnings, balance sheet, ratios)
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
- `results_press_release` — Quarterly/annual results press release
- `board_meeting_outcome` — Outcome note (no transcript content, low value)
- `other` — Everything else

Classification method: BSE category code + filename keyword matching (regex). LLM fallback for ambiguous cases. Only `concall_transcript` and `investor_presentation` proceed to extraction pipeline.

#### 6.1.3 Coverage Expectation

| Document Type | Expected Completeness |
|---|---|
| Concall transcripts (Nifty 100 companies) | >90% of calls, FY21–FY26 |
| Concall transcripts (mid-cap) | ~70–80% (some companies file inconsistently) |
| Investor presentations | ~85% (not all companies file these separately) |

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

### 6.3 Storage and Indexing

#### 6.3.1 Postgres Schema (Metadata)

Key tables:

- `companies` — scrip code, name, sector, BSE ID
- `events` — company, event date, event type, quarter label, filing ID
- `documents` — event FK, document type, BSE URL, S3 path, extraction status, quality score
- `turns` — document FK, turn index, speaker raw, speaker role, speaker org, text
- `slides` — document FK, slide number, title, body text

#### 6.3.2 Elasticsearch Index

Index name: `india_ir_turns`

Fields:
- `text` — full text (analyzed, English analyzer)
- `company` — keyword
- `quarter` — keyword (format: `3QFY25`)
- `fy_year` — integer
- `event_date` — date
- `speaker_role` — keyword (`management` / `analyst` / `unknown`)
- `document_type` — keyword
- `turn_id`, `document_id` — for citation linking

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
3. Constructs prompt with retrieved chunks as context
4. Returns a structured answer with inline citations

Citation format: `[Company Name, Quarter, Speaker Name]` linking back to the source passage.

LLM: Claude Sonnet (via Anthropic API).

Example queries the system must handle:

- *"What has Laurus Labs management said about CDMO capacity utilization over the last 6 quarters?"*
- *"Which companies mentioned inventory destocking in 2QFY25?"*
- *"What is Syngene's guidance on FY26 revenue?"*
- *"Compare what Divi's and Laurus have said about US generics pricing pressure"*

#### 6.4.4 Company Timeline View

Per-company view showing:
- All indexed events in chronological order (quarter, event type)
- Click to read full transcript in-app (rendered from parsed turns)
- Quick summary of each event (LLM-generated, 3–5 bullet points)

### 6.5 Web UI

#### 6.5.1 Pages

| Page | Description |
|---|---|
| Home / Search | Global search bar (keyword or natural language), filter panel, results |
| Q&A | Question input, answer with citations, source passage viewer |
| Company Page | Timeline of events, event summaries, link to full transcript viewer |
| Transcript Viewer | Full rendered transcript with speaker turns, keyword highlight, scroll-to-turn |
| Coverage Dashboard | Admin view — coverage status per company, extraction quality, missing filings |

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
| Text extraction quality (text PDFs) | > 95% of turns parseable |
| Text extraction quality (scanned PDFs) | > 80% of turns parseable |
| Speaker attribution accuracy | > 85% of turns correctly attributed to management vs analyst |
| Quarter label accuracy | 100% (verified against BSE filing date) |
| Filing coverage (Nifty 100 companies in universe) | > 90% of calls over 5-year period |

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
│   └── slide_parser.py         # Presentation slide parsing
├── indexing/
│   ├── es_indexer.py           # Elasticsearch indexing
│   ├── embedding_indexer.py    # Chunking + pgvector indexing
│   └── quality_checker.py      # Extraction quality validation
├── search/
│   ├── keyword_search.py       # ES full-text search
│   ├── semantic_search.py      # pgvector similarity search
│   └── rag.py                  # Retrieval + Claude API Q&A
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
- Build `document_classifier.py`
- Run historical backfill for all 30 companies
- Build `text_extractor.py` and `transcript_parser.py`
- Populate Postgres `companies`, `events`, `documents`, `turns` tables
- Build `coverage_report.py` to monitor gaps

Success metric: > 85% of expected filings downloaded and turns extracted for Nifty 100 companies in universe.

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
- Build `rag.py` — retrieval + Claude API prompt construction + streaming response
- Add Q&A page to Streamlit UI
- Build company timeline page and transcript viewer

Success metric: RAG correctly answers the 5 benchmark questions listed in section 6.4.3 with accurate citations.

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
| Elasticsearch operational complexity | Low | Medium | Use managed ES (Elastic Cloud) if local Docker is problematic |
| LLM API costs (RAG at scale) | Low at MVP | Medium | Rate limit Q&A queries; cache frequent queries |
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
| Keyword search latency | < 2 seconds |
| RAG Q&A accuracy (benchmark questions) | 5 / 5 correct with accurate citations |
| Time to answer a cross-company query vs. manual | 30 seconds vs. 2+ hours |

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
- **Financial data layer** — earnings, margins, ratios alongside transcript commentary
- **Alerts** — keyword-triggered notifications on new filings
- **API access** — for quant/systematic users
- **Multi-tenancy and billing** — for external productization
- **Keyword trend charts** — frequency of a term across quarters over time
- **Speaker profiling** — track individual analyst questions across companies over time
- **Export** — CSV/Excel export of search results

---

## 13. Open Questions

1. **OCR service decision** — Tesseract (free, lower quality) vs. AWS Textract (~$1.50/1000 pages) vs. Google Document AI. To be resolved in Phase 0 based on quality test results.

2. **Embedding model** — OpenAI `text-embedding-3-small` ($0.02/1M tokens, managed) vs. `intfloat/e5-base-v2` (free, self-hosted). At MVP corpus size (~5M tokens for 30 companies × 5 years), OpenAI cost is < $1 total. OpenAI preferred for MVP simplicity.

3. **UI framework** — Streamlit is fastest to build but has UX limitations. Accept this for MVP; reassess if showing to external users.

4. **BSE API reliability** — The undocumented BSE API has worked reliably for years but is not guaranteed. Need a direct HTML scraper fallback. Assess in Phase 1.

5. **Quarter label normalization** — BSE filing dates don't always map cleanly to quarters (e.g., a call held in April for Q4 results). Define normalization rules: use BSE filing date to infer FY quarter; flag for manual review if ambiguous.

---

*Document Owner: Research Team*
*Last Updated: April 2026*
*Status: Draft — pending Phase 0 validation*
