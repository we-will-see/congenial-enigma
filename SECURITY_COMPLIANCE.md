# Security & Compliance
## IndiaIR — Threat Model, Secrets, Audit, Privacy
### Version 1.0 | April 2026

---

> **For AI coding agents:** Implement every control listed here. Security controls are not optional. If a control conflicts with other requirements, flag it — do not silently omit it.

---

## 1. Threat Model (STRIDE)

MVP is a single-user internal tool running locally. The threat surface is limited but real.

| Threat | Vector | Likelihood | Control |
|---|---|---|---|
| **Spoofing** | Someone impersonates the API | Low (localhost only) | Bind FastAPI to 127.0.0.1 only |
| **Tampering** | Malicious PDF on BSE triggers code execution | Medium | PDF parsing in isolated context; no exec/eval on extracted text |
| **Repudiation** | No audit log of who queried what | Low (single user) | Pipeline run log; query log for RAG |
| **Information Disclosure** | API keys leaked in logs | Medium | Scrub keys from all log output |
| **DoS** | LLM API cost explosion from runaway queries | Low | Rate limit RAG endpoint |
| **Elevation** | BSE scraper follows malicious redirect | Low | Whitelist BSE domain; validate PDF Content-Type |

---

## 2. Secrets Management

**Rule: zero secrets in code or config files committed to version control.**

```bash
# .env (never committed — in .gitignore)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
POSTGRES_PASSWORD=...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

```python
# config.py — only reads from env, never defines values
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str
    openai_api_key: str
    database_url: str
    es_host: str = "http://localhost:9200"
    # ... all other settings

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

**`.gitignore` must include:**
```
.env
*.env
data/raw_pdfs/
logs/
*.pem
*.key
```

**Log scrubbing — keys must never appear in logs:**
```python
import structlog

def scrub_secrets(event_dict):
    for key in ['api_key', 'password', 'secret', 'token']:
        if key in event_dict:
            event_dict[key] = '***REDACTED***'
    return event_dict

structlog.configure(processors=[scrub_secrets, ...])
```

---

## 3. Network Security

**FastAPI binding:** In production/local deployment, bind to `127.0.0.1` only:
```python
# In startup script or Dockerfile CMD
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

**Elasticsearch:** Bound to localhost only (no auth in single-node local setup). If exposed on a network: enable `xpack.security.enabled=true` and configure basic auth.

**External API calls:** Only the following domains are permitted outbound:
- `api.bseindia.com` — BSE filings
- `www.bseindia.com` — PDF downloads
- `api.anthropic.com` — LLM (RAG + extraction)
- `api.openai.com` — embeddings only

**PDF download validation:**
```python
def download_pdf(url: str) -> bytes:
    # Whitelist check
    allowed_domains = ["bseindia.com", "www.bseindia.com"]
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc not in allowed_domains:
        raise ValueError(f"URL domain not whitelisted: {parsed.netloc}")

    response = httpx.get(url, timeout=30, follow_redirects=False)  # no redirects

    # Content-type check
    content_type = response.headers.get('content-type', '')
    if 'pdf' not in content_type.lower() and 'octet-stream' not in content_type.lower():
        raise ValueError(f"Unexpected content type: {content_type}")

    # Size limit: 50MB
    if len(response.content) > 50 * 1024 * 1024:
        raise ValueError("PDF exceeds 50MB size limit")

    return response.content
```

---

## 4. Input Validation

All user inputs validated via Pydantic before processing.

```python
class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    companies: list[int] | None = Field(default=None, max_length=30)
    quarter_from: str | None = Field(default=None, pattern=r'^\dQFY\d{2}$')
    quarter_to: str | None = Field(default=None, pattern=r'^\dQFY\d{2}$')
    document_types: list[str] | None = None
    speaker_roles: list[str] | None = None
    page: int = Field(default=1, ge=1, le=1000)
    page_size: int = Field(default=20, ge=1, le=100)

class QARequest(BaseModel):
    question: str = Field(min_length=5, max_length=1000)
    company_ids: list[int] | None = Field(default=None, max_length=30)
    quarter_from: str | None = None
    quarter_to: str | None = None
    session_id: str | None = Field(default=None, max_length=100)
```

**SQL injection:** All database queries use SQLAlchemy ORM or parameterised queries. Never build SQL strings by concatenation.

**LLM prompt injection:** User question text is inserted into the RAG prompt. Apply basic sanitisation:
```python
def sanitise_question(text: str) -> str:
    # Remove any attempts to escape the prompt context
    dangerous_patterns = [
        r'ignore previous instructions',
        r'system prompt',
        r'<\|.*?\|>',           # token injection
        r'\[INST\]',            # Llama instruction tokens
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            raise ValueError("Question contains disallowed content")
    return text.strip()
```

---

## 5. Rate Limiting

**RAG Q&A endpoint:** Maximum 20 requests per minute (to control Anthropic API costs).

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/qa/ask")
@limiter.limit("20/minute")
async def ask_question(request: Request, body: QARequest):
    ...
```

**BSE polling:** Already rate-limited by `BSE_REQUEST_DELAY_SECONDS = 1.0` in ingestion.

---

## 6. Audit Log

All RAG Q&A queries are logged for cost monitoring and debugging:

```sql
CREATE TABLE query_log (
    id          BIGSERIAL PRIMARY KEY,
    timestamp   TIMESTAMPTZ DEFAULT NOW(),
    query_type  VARCHAR(20),           -- keyword | semantic | qa
    question    TEXT,
    company_ids INTEGER[],
    result_count INTEGER,
    duration_ms INTEGER,
    tokens_used INTEGER,               -- for RAG queries
    cost_usd    NUMERIC(8,6)           -- estimated cost
);
```

---

## 7. OWASP ASVS — Applicable Controls (Level 1)

For an internal single-user tool, full ASVS Level 2 is out of scope. The following Level 1 controls apply:

| ASVS ID | Control | Implementation |
|---|---|---|
| V1.1 | Secrets not hardcoded | pydantic-settings + .env |
| V2.1 | No default passwords | POSTGRES_PASSWORD required in .env |
| V5.1 | All inputs validated | Pydantic models on all endpoints |
| V5.2 | No SQL injection | SQLAlchemy ORM throughout |
| V7.1 | Logs don't contain secrets | structlog scrubber |
| V9.1 | TLS for external APIs | httpx defaults to TLS verification on |
| V12.1 | File upload validation | PDF size + content-type checks |
| V14.1 | Dependencies pinned | requirements.txt with exact versions |

---

## 8. Compliance

### 8.1 Data Source

All data ingested by IndiaIR is sourced from BSE India's public corporate filings portal. These filings are:
- Mandated by SEBI regulations (Listing Obligations and Disclosure Requirements)
- Publicly accessible without authentication
- Required to be published by listed companies for investor transparency

IndiaIR does not scrape behind authentication, does not access non-public data, and does not redistribute data to third parties.

### 8.2 Data Retention

| Data type | Retention | Rationale |
|---|---|---|
| Raw PDFs | Indefinite (local storage) | Source of truth for extraction |
| Extracted text (turns, slides, sections) | Indefinite | Core product data |
| Financial records | Indefinite | Historical research value |
| Pipeline run logs | 90 days | Operational debugging |
| Query logs | 90 days | Cost monitoring |
| Management change records | Indefinite | Historical governance data |

### 8.3 Personal Data

IndiaIR stores names of company executives (from public regulatory filings) and names of sell-side analysts (from public concall transcripts). This is:
- Public information disclosed in regulatory filings
- Processed for legitimate research purposes
- Not combined with any non-public personal data

No user personal data is collected. There is no user registration, no cookies, no analytics tracking.

### 8.4 BSE Terms of Service

BSE India does not publish explicit API terms of service for the undocumented filings API. IndiaIR operates as an internal research tool with the following constraints to minimise risk:
- Rate limiting (1 req/sec) to avoid server burden
- No redistribution of downloaded content to third parties
- Data used solely for internal research analysis

If BSE introduces authenticated API access or explicit terms, this must be reviewed and the tool updated to comply.

---

*Last Updated: April 2026 | Version 1.0*
