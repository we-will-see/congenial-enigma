# Quality Requirements
## IndiaIR — Test Strategy, CI/CD, Performance, Accessibility
### Version 1.0 | April 2026

---

> **For AI coding agents:** Implement every test described here. Tests are not optional. Each module must have a corresponding test file. CI must pass before any code is considered complete.

---

## 1. Test Strategy Overview

| Layer | Tool | Location | When Run |
|---|---|---|---|
| Unit | pytest | `tests/unit/` | Every commit |
| Integration | pytest + live DB/ES | `tests/integration/` | Every commit (Docker required) |
| End-to-end | pytest + httpx | `tests/e2e/` | Every commit |
| Performance | locust | `tests/perf/` | Pre-release |
| Extraction evaluation | Custom harness | `tests/eval/` | Pre-release |

Minimum coverage target: **80% line coverage** across all non-test code. Coverage measured with `pytest-cov`. CI fails if coverage drops below 80%.

---

## 2. Unit Tests

### 2.1 Financial Extractor

File: `tests/unit/test_financial_extractor.py`

```python
# AC-03: Must reproduce verified Laurus Labs 3QFY25 figures
def test_laurus_3qfy25_verified_fixture():
    """Financial extractor must reproduce verified figures within 2% tolerance."""
    result = financial_extractor.extract_from_fixture(LAURUS_3QFY25_FIXTURE_TEXT)
    assert abs(result['revenue'] - 1547.00) / 1547.00 < 0.02
    assert abs(result['ebitda'] - 278.00) / 278.00 < 0.02
    assert abs(result['pat'] - 152.00) / 152.00 < 0.02
    assert abs(result['eps_basic'] - 2.81) / 2.81 < 0.02

# AC-08: Consistency checks correctly reject bad data
def test_consistency_check_eps_pat_mismatch():
    bad_row = {"eps_basic": 10.0, "shares_cr": 53.6, "pat": 100.0}  # should be ~536 Cr
    flags = validate_financials(bad_row)
    assert "EPS_PAT_MISMATCH" in flags

def test_consistency_check_negative_revenue():
    bad_row = {"revenue": -100.0, "ebitda": 20.0, "pat": 10.0}
    flags = validate_financials(bad_row)
    assert "NEGATIVE_REVENUE" in flags

def test_ebitda_margin_always_recomputed():
    row = {"revenue": 1000.0, "ebitda": 200.0, "ebitda_margin": 0.99}  # wrong stated margin
    validate_financials(row)
    assert abs(row['ebitda_margin'] - 0.20) < 0.001  # must be recomputed

def test_label_dict_fuzzy_match():
    """All label variants must map to correct field."""
    test_cases = [
        ("Revenue from Operations", "revenue"),
        ("Net Revenue from Operations", "revenue"),
        ("Total Income from Operations", "revenue"),
        ("Profit After Tax", "pat"),
        ("PAT", "pat"),
        ("Finance Costs", "finance_costs"),
        ("Depreciation and Amortisation", "da"),
    ]
    for label, expected_field in test_cases:
        assert map_label_to_field(label) == expected_field, f"Failed for: {label}"
```

### 2.2 Transcript Parser

File: `tests/unit/test_transcript_parser.py`

```python
# AC-04: Speaker attribution on labelled test set
def test_management_attribution():
    text = "V.V. Ravi Kumar: Thank you. On margins, we expect improvement."
    turns = parse_transcript_turns(text)
    assert turns[0]['speaker_role'] == 'management'

def test_analyst_attribution_with_org():
    text = "Neha Manpuria (JPMorgan): My question is on the CDMO pipeline."
    turns = parse_transcript_turns(text)
    assert turns[0]['speaker_role'] == 'analyst'
    assert turns[0]['speaker_org'] == 'JPMorgan'
    assert turns[0]['speaker_name'] == 'Neha Manpuria'

def test_moderator_excluded_from_analysis():
    text = "Moderator: We will now take questions. Please go ahead."
    turns = parse_transcript_turns(text)
    assert turns[0]['speaker_role'] == 'moderator'

def test_multi_turn_sequence():
    """Multi-turn transcript parses correctly with correct sequence."""
    fixture = load_fixture('tests/fixtures/sample_transcript.txt')
    turns = parse_transcript_turns(fixture)
    assert len(turns) > 10
    roles = [t['speaker_role'] for t in turns]
    assert 'management' in roles
    assert 'analyst' in roles

def test_labeled_set_accuracy():
    """AC-04: Must achieve > 85% accuracy on 50-turn labeled set."""
    labeled = load_fixture('tests/fixtures/labeled_turns_50.json')
    correct = 0
    for item in labeled:
        result = classify_speaker_role(item['speaker_raw'], item['text'])
        if result == item['expected_role']:
            correct += 1
    accuracy = correct / len(labeled)
    assert accuracy >= 0.85, f"Speaker attribution accuracy {accuracy:.2%} below 85% threshold"
```

### 2.3 Document Classifier

File: `tests/unit/test_document_classifier.py`

```python
# AC-06: Must classify all 5 document types correctly on 25-filing test set
def test_classifier_labeled_set():
    labeled = load_fixture('tests/fixtures/labeled_filings_25.json')
    correct = 0
    for item in labeled:
        result = classify_document(item['CATEGORYNAME'], item['SUBCATEGORYNAME'], item['HEADLINE'])
        if result == item['expected_type']:
            correct += 1
    assert correct / len(labeled) >= 1.0, "All 25 labeled filings must classify correctly"

@pytest.mark.parametrize("cat,subcat,headline,expected", [
    ("Concall", "Transcript", "Transcript of Earnings Call", "concall_transcript"),
    ("Investor Presentation", "", "Q3FY25 Investor Presentation", "investor_presentation"),
    ("Results", "Financial Results", "Unaudited Financial Results Q3", "results_press_release"),
    ("Change in Directors", "", "Appointment of CFO", "management_change"),
    ("Board Meeting", "Outcome of Board Meeting", "Board Meeting Outcome", "board_meeting_outcome"),
])
def test_classifier_parametrized(cat, subcat, headline, expected):
    assert classify_document(cat, subcat, headline) == expected
```

### 2.4 BSE Poller

File: `tests/unit/test_bse_poller.py`

```python
def test_parse_bse_response_date_format():
    """BSE date format DD-MON-YYYY HH:MM:SS must parse correctly."""
    raw = "23-OCT-2024 17:45:24"
    parsed = parse_bse_datetime(raw)
    assert parsed == datetime(2024, 10, 23, 17, 45, 24)

def test_parse_empty_table():
    """Empty Table array is not an error."""
    response = {"Table": []}
    filings = parse_bse_response(response)
    assert filings == []

def test_idempotency_skip_existing(db_session):
    """AC-10: Poller skips documents already in DB by filing_id."""
    # Insert a filing
    insert_filing(db_session, bse_filing_id="20241023-33", ...)
    # Run poller with same response
    result = process_filing(db_session, {"NEWSID": "20241023-33", ...})
    assert result == "skipped"
    assert db_session.query(Document).count() == 1  # no duplicate
```

### 2.5 Restatement Detection

File: `tests/unit/test_restatement.py`

```python
# AC-12: Restatement detection fires correctly
def test_restatement_detected_on_large_change(db_session):
    insert_financials(db_session, company_id=1, period="3QFY25", revenue=1547.0)
    # "Re-ingest" with restated figure (>5% change)
    upsert_financials(db_session, company_id=1, period="3QFY25", revenue=1620.0)
    fin = db_session.query(Financials).filter_by(company_id=1, period="3QFY25").one()
    assert fin.restated == True
    history = db_session.query(FinancialsHistory).filter_by(financials_id=fin.id).all()
    assert len(history) == 1

def test_no_restatement_on_small_change(db_session):
    insert_financials(db_session, company_id=1, period="3QFY25", revenue=1547.0)
    upsert_financials(db_session, company_id=1, period="3QFY25", revenue=1548.0)  # < 5% change
    fin = db_session.query(Financials).filter_by(company_id=1, period="3QFY25").one()
    assert fin.restated == False
```

---

## 3. Integration Tests

Require Docker Compose running (Postgres + ES). Run with:
```bash
docker-compose up -d
pytest tests/integration/ -v
```

File: `tests/integration/test_pipeline.py`

```python
# AC-05: BSE API live integration
def test_bse_api_live_laurus_labs():
    """Hit live BSE API and verify response structure."""
    filings = fetch_bse_filings(scrip_code="540222", from_date="20240101", to_date="20240430")
    assert len(filings) > 0
    assert all('NEWSID' in f for f in filings)
    assert all('ATTACHMENT' in f for f in filings)

# AC-10: Full pipeline idempotency
def test_full_pipeline_idempotent(db_session, es_client, sample_pdf_path):
    """Running the pipeline twice on the same document produces no duplicates."""
    run_pipeline_on_document(sample_pdf_path, "concall_transcript", company_id=1)
    count_after_first = db_session.query(Turn).count()
    es_count_after_first = es_client.count(index="india_ir_content")['count']

    run_pipeline_on_document(sample_pdf_path, "concall_transcript", company_id=1)
    assert db_session.query(Turn).count() == count_after_first
    assert es_client.count(index="india_ir_content")['count'] == es_count_after_first

def test_financial_pipeline_end_to_end(db_session, sample_press_release_path):
    """Financial extraction from real PDF populates financials table correctly."""
    run_pipeline_on_document(sample_press_release_path, "results_press_release", company_id=1)
    fin = db_session.query(Financials).filter_by(company_id=1).first()
    assert fin is not None
    assert fin.revenue > 0
    assert fin.extraction_status not in ['failed']

def test_es_search_returns_results(es_client, db_session, indexed_corpus):
    """After indexing, keyword search returns results."""
    results = keyword_search("capacity utilization", company_ids=None)
    assert len(results['results']) > 0
```

---

## 4. End-to-End Tests

File: `tests/e2e/test_api.py`

Uses `httpx.AsyncClient` against the running FastAPI server.

```python
# AC-01: Keyword search latency
async def test_keyword_search_latency():
    start = time.time()
    response = await client.post("/api/v1/search/keyword", json={"query": "capacity utilization"})
    elapsed = time.time() - start
    assert response.status_code == 200
    assert elapsed < 2.0, f"Keyword search took {elapsed:.2f}s, expected < 2s"
    assert response.json()['total'] >= 0

# AC-02: RAG Q&A first token latency
async def test_qa_first_token_latency():
    start = time.time()
    first_token_time = None
    async with client.stream("POST", "/api/v1/qa/ask", json={
        "question": "What has Laurus Labs said about margins?",
        "company_ids": [1]
    }) as response:
        async for chunk in response.aiter_text():
            if first_token_time is None and '"token"' in chunk:
                first_token_time = time.time()
                break
    assert first_token_time - start < 5.0

async def test_health_check():
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data['db'] == 'ok'
    assert data['es'] == 'ok'

async def test_search_empty_result_not_error():
    response = await client.post("/api/v1/search/keyword", json={
        "query": "xyzzy_nonexistent_term_12345"
    })
    assert response.status_code == 200
    assert response.json()['total'] == 0

async def test_company_financials_endpoint():
    response = await client.get("/api/v1/companies/1/financials")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
```

---

## 5. Extraction Evaluation Harness

File: `tests/eval/run_eval.py`

This is a separate evaluation script, not run in CI (requires real PDFs and human-labeled data).

```bash
# Run extraction quality evaluation
python tests/eval/run_eval.py --type speaker_attribution --fixture tests/fixtures/labeled_turns_50.json
python tests/eval/run_eval.py --type management_change --fixture tests/fixtures/labeled_mgmt_25.json
python tests/eval/run_eval.py --type financial --fixture tests/fixtures/verified_financials.json
```

Outputs a quality report to `tests/eval/results/` with pass/fail per acceptance criterion.

**Required fixture files (must be created during Phase 0 validation):**
- `tests/fixtures/labeled_turns_50.json` — 50 speaker turns with hand-labeled roles
- `tests/fixtures/labeled_filings_25.json` — 25 filing metadata rows with hand-labeled document types
- `tests/fixtures/labeled_mgmt_25.json` — 25 management change filing texts with hand-labeled structured output
- `tests/fixtures/verified_financials.json` — manually verified P&L figures for 3+ companies × 4+ quarters
- `tests/fixtures/sample_transcript.txt` — full text of one real concall transcript
- `tests/fixtures/sample_press_release.txt` — full text of one real results press release

---

## 6. CI/CD Pipeline

File: `.github/workflows/ci.yml` (or equivalent for local CI)

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_DB: indiair_test
          POSTGRES_USER: indiair
          POSTGRES_PASSWORD: testpassword
        ports: ["5432:5432"]
      elasticsearch:
        image: docker.elastic.co/elasticsearch/elasticsearch:8.13.0
        env:
          discovery.type: single-node
          xpack.security.enabled: "false"
          ES_JAVA_OPTS: "-Xms512m -Xmx512m"
        ports: ["9200:9200"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov httpx

      - name: Install Tesseract
        run: sudo apt-get install -y tesseract-ocr

      - name: Run migrations
        env:
          DATABASE_URL: postgresql://indiair:testpassword@localhost:5432/indiair_test
        run: alembic upgrade head

      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=. --cov-report=xml --cov-fail-under=80

      - name: Run integration tests
        env:
          DATABASE_URL: postgresql://indiair:testpassword@localhost:5432/indiair_test
          ES_HOST: http://localhost:9200
        run: pytest tests/integration/ -v

      - name: Run e2e tests
        env:
          DATABASE_URL: postgresql://indiair:testpassword@localhost:5432/indiair_test
          ES_HOST: http://localhost:9200
        run: |
          uvicorn api.main:app --port 8000 &
          sleep 3
          pytest tests/e2e/ -v

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Ruff lint
        run: |
          pip install ruff
          ruff check .
      - name: Type check
        run: |
          pip install mypy
          mypy . --ignore-missing-imports
```

**CI gates — all must pass before merge:**
- All unit tests pass
- All integration tests pass
- All e2e tests pass
- Coverage ≥ 80%
- Ruff lint: zero errors
- No new `# type: ignore` comments without explanation

---

## 7. Performance Goals

### 7.1 Latency Targets (P95, measured on MVP hardware)

| Operation | P50 Target | P95 Target | P99 Max |
|---|---|---|---|
| Keyword search (full corpus) | 500ms | 1.5s | 2.0s |
| Semantic search (pgvector) | 800ms | 2.0s | 3.0s |
| RAG Q&A first token | 2s | 4s | 5s |
| Company page load | 300ms | 800ms | 1.5s |
| Financials comparison (5 companies) | 400ms | 1.0s | 2.0s |
| PDF extraction (text PDF, 20 pages) | 2s | 5s | 10s |
| PDF extraction (scanned PDF, 20 pages) | 30s | 60s | 120s |

### 7.2 Throughput Targets

| Operation | Target |
|---|---|
| Historical backfill (30 companies × 5 years) | Complete in < 8 hours |
| Daily incremental poll (30 companies) | Complete in < 30 minutes |
| Embedding indexing (full corpus, ~500k chunks) | Complete in < 4 hours |

### 7.3 Performance Test (Locust)

File: `tests/perf/locustfile.py`

```python
from locust import HttpUser, task, between

class AnalystUser(HttpUser):
    wait_time = between(2, 5)

    @task(3)
    def keyword_search(self):
        self.client.post("/api/v1/search/keyword", json={
            "query": "capacity utilization",
            "page_size": 20
        })

    @task(1)
    def company_page(self):
        self.client.get("/api/v1/companies/1/financials")

    @task(1)
    def management_changes(self):
        self.client.get("/api/v1/management-changes?page_size=20")
```

Run with: `locust -f tests/perf/locustfile.py --users 10 --spawn-rate 2 --run-time 60s`

Target: P95 keyword search < 2s at 10 concurrent users.

---

## 8. Accessibility Standards

The Streamlit UI must meet **WCAG 2.1 Level AA** for the following criteria:

| Criterion | Implementation |
|---|---|
| 1.4.3 Contrast Ratio | Minimum 4.5:1 for all text. Use Streamlit's default theme — do not override with low-contrast custom CSS |
| 1.4.4 Resize Text | Do not use fixed pixel font sizes in custom CSS |
| 2.1.1 Keyboard | All interactive elements reachable by Tab key (Streamlit default behaviour) |
| 2.4.2 Page Titled | Each page has a unique `st.title()` |
| 3.1.1 Language | `lang="en"` in page config |
| 3.3.1 Error Identification | All error states show a specific error message, not just a generic "error occurred" |
| 3.3.2 Labels | All form inputs have visible labels (`st.text_input("Label", ...)`) |
| 4.1.2 Name Role Value | Do not override Streamlit's default ARIA roles with custom HTML |

**Streamlit-specific:**
```python
st.set_page_config(
    page_title="IndiaIR — [Page Name]",
    page_icon="📊",
    layout="wide"
)
```

**Empty states** — every list/search result area must have an explicit empty state message. Never show a blank area when there is no data.

**Error states** — all API error responses must be surfaced to the user with `st.error("message")`. Never silently swallow errors.

---

## 9. Regression Coverage

The following scenarios must remain passing after any code change. Run as part of integration test suite.

| Scenario | What it protects |
|---|---|
| Laurus Labs 3QFY25 financials verified fixture | Financial extractor accuracy |
| Speaker attribution labeled set (50 turns) | Transcript parser accuracy |
| Document classifier labeled set (25 filings) | Classifier accuracy |
| BSE API response parsing | Poller date/field parsing |
| Idempotent pipeline run | No duplicate data |
| Restatement detection | Data integrity |
| Keyword search returns results for "margin" | ES index health |
| Health endpoint returns 200 | System health |

---

*Last Updated: April 2026 | Version 1.0*
