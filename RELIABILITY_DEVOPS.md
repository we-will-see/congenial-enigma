# Reliability & DevOps
## IndiaIR — SLIs/SLOs, Alerting, Environments, Deployment
### Version 1.0 | April 2026

---

> **For AI coding agents:** Implement health checks, the startup sequence, and the Makefile. SLOs are targets; alerting fires when they are breached.

---

## 1. SLIs and SLOs

MVP is a single-user internal tool. SLOs are defined for self-monitoring, not external commitments.

| SLI | SLO Target | Measurement |
|---|---|---|
| Keyword search availability | 99% of requests succeed (non-5xx) | Health check + error rate log |
| Keyword search P95 latency | < 2s | Request timing in access log |
| RAG Q&A availability | 95% (dependent on Anthropic API) | Error rate log |
| RAG Q&A P95 first-token latency | < 5s | Streaming timing log |
| Pipeline daily run completion | 100% of scheduled runs complete within 2 hours | pipeline_runs table |
| Data freshness | New BSE filings indexed within 24 hours of filing | event_date vs processed_at delta |

---

## 2. Health Checks

### 2.1 Application Health Endpoint

```python
@router.get("/health")
async def health_check():
    status = {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

    # Check Postgres
    try:
        await db.execute(text("SELECT 1"))
        status["db"] = "ok"
    except Exception as e:
        status["db"] = "error"
        status["status"] = "degraded"

    # Check Elasticsearch
    try:
        es_health = await es.cluster.health(timeout="2s")
        status["es"] = "ok" if es_health['status'] != 'red' else "degraded"
        if status["es"] == "degraded":
            status["status"] = "degraded"
    except Exception:
        status["es"] = "error"
        status["status"] = "degraded"

    # Check external API reachability (non-blocking, cached)
    status["anthropic_api"] = get_cached_api_status("anthropic")
    status["openai_api"] = get_cached_api_status("openai")

    http_status = 200 if status["status"] == "ok" else 503
    return JSONResponse(content=status, status_code=http_status)
```

### 2.2 Pipeline Health

The APScheduler job `health_check_external_apis` runs every 5 minutes and writes to an in-memory cache:

```python
async def check_api_health():
    """Ping Anthropic and OpenAI. Cache result for 5 minutes."""
    try:
        await anthropic_client.messages.create(
            model="claude-haiku-20250507",
            max_tokens=1,
            messages=[{"role": "user", "content": "hi"}]
        )
        set_cached_status("anthropic", "ok")
    except Exception:
        set_cached_status("anthropic", "error")
```

---

## 3. Alerting

MVP alerting is lightweight — log-based, no external service required.

**Alert conditions** written to `logs/alerts.log` (separate from main log):

```python
ALERT_CONDITIONS = [
    # Pipeline failures
    {
        "name": "pipeline_run_failed",
        "condition": "pipeline_runs.status = 'failed'",
        "message": "Pipeline run failed. Check pipeline_runs table for errors.",
        "severity": "high"
    },
    {
        "name": "high_extraction_failure_rate",
        "condition": "documents with extraction_status='failed' in last 24h > 20%",
        "message": "More than 20% of documents failed extraction in last 24 hours.",
        "severity": "medium"
    },
    # Data freshness
    {
        "name": "stale_data",
        "condition": "max(events.created_at) < NOW() - INTERVAL '26 hours'",
        "message": "No new filings ingested in last 26 hours. BSE API may be down.",
        "severity": "medium"
    },
    # API costs
    {
        "name": "high_llm_cost",
        "condition": "sum(query_log.cost_usd) in last 24h > 5.00",
        "message": "LLM API costs exceeded $5 in last 24 hours.",
        "severity": "low"
    }
]
```

Alerts checked by APScheduler job `check_alert_conditions`, runs every 30 minutes.

---

## 4. Startup Sequence

```python
# api/main.py — lifespan context
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    logger.info("IndiaIR starting up")

    # 1. Verify database connection
    await verify_db_connection()

    # 2. Run pending migrations
    run_alembic_upgrade()

    # 3. Verify Elasticsearch connection + index exists
    await verify_es_connection()
    await ensure_es_index_exists()

    # 4. Reset stuck pipeline documents
    await reset_stuck_documents()

    # 5. Start APScheduler
    scheduler.start()
    logger.info("APScheduler started")

    # 6. Log startup summary
    company_count = await db.scalar(select(func.count(Company.id)))
    doc_count = await db.scalar(select(func.count(Document.id)))
    logger.info("Startup complete", companies=company_count, documents=doc_count)

    yield

    # SHUTDOWN
    scheduler.shutdown(wait=False)
    logger.info("IndiaIR shutdown complete")
```

---

## 5. Rollback Plan

MVP is a single-server deployment with no orchestration. Rollback procedure:

**Code rollback:**
```bash
git log --oneline -10          # identify last good commit
git checkout <commit-hash>     # roll back code
pip install -r requirements.txt
# restart services
```

**Database rollback:**
```bash
# If migration introduced a bug
alembic downgrade -1           # roll back one migration
# Or to specific revision
alembic downgrade <revision_id>
```

**Data rollback (extraction re-run):**
```bash
# If extraction logic produced bad data, re-run on affected documents
python scripts/reprocess.py --company-id 1 --document-type concall_transcript --from-date 2024-01-01
```

The `financials_history` table preserves all previous values — financial data can always be restored from history.

---

## 6. Environments

### 6.1 Local Development

```
Environment: developer's laptop
Config: .env.local
Database: Docker Compose (localhost:5432)
Elasticsearch: Docker Compose (localhost:9200)
Storage: ./data/raw_pdfs/
API: uvicorn --reload (hot reload)
UI: streamlit run ui/app.py
```

### 6.2 Production (Single Server)

```
Environment: VPS or dedicated machine (min 8GB RAM, 4 cores, 100GB SSD)
Config: .env (managed manually)
Database: Docker Compose or system PostgreSQL
Elasticsearch: Docker Compose
Storage: ./data/raw_pdfs/ (local) or S3 bucket
API: uvicorn (no reload), behind nginx
UI: streamlit run ui/app.py, behind nginx
Process manager: systemd or supervisord
```

No staging environment for MVP. Test against dev before deploying to production.

---

## 7. Infrastructure as Code

### 7.1 Directory Structure

```
deploy/
├── docker-compose.yml          # Postgres + ES (from ARCH_DESIGN)
├── docker-compose.override.yml # Dev overrides (hot reload, debug ports)
├── nginx.conf                  # Reverse proxy config
├── systemd/
│   ├── indiair-api.service
│   └── indiair-ui.service
└── scripts/
    ├── install.sh              # Fresh server setup
    ├── backup.sh               # Database backup
    └── restore.sh              # Database restore
```

### 7.2 systemd Service Files

```ini
# deploy/systemd/indiair-api.service
[Unit]
Description=IndiaIR FastAPI Backend
After=network.target postgresql.service

[Service]
Type=simple
User=indiair
WorkingDirectory=/opt/indiair
EnvironmentFile=/opt/indiair/.env
ExecStart=/opt/indiair/venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 7.3 Nginx Configuration

```nginx
# /etc/nginx/sites-available/indiair
server {
    listen 80;
    server_name localhost;

    # FastAPI
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120s;    # for streaming RAG responses
        proxy_buffering off;         # required for SSE streaming
    }

    # Streamlit
    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";  # for Streamlit WebSocket
    }
}
```

---

## 8. Deployment Pipeline

```bash
# Makefile — all deployment operations
.PHONY: install dev test lint migrate backfill start stop restart backup

install:
	python -m venv venv
	./venv/bin/pip install -r requirements.txt
	cp .env.example .env
	docker-compose up -d
	sleep 5
	./venv/bin/alembic upgrade head
	@echo "Installation complete. Edit .env with your API keys, then run: make backfill"

dev:
	docker-compose up -d
	./venv/bin/uvicorn api.main:app --reload --port 8000 &
	./venv/bin/streamlit run ui/app.py --server.port 8501

test:
	docker-compose up -d
	./venv/bin/pytest tests/unit tests/integration tests/e2e -v --cov=. --cov-fail-under=80

lint:
	./venv/bin/ruff check .
	./venv/bin/mypy . --ignore-missing-imports

migrate:
	./venv/bin/alembic upgrade head

backfill:
	./venv/bin/python scripts/backfill.py --from-date 2020-04-01 --to-date 2026-04-30

start:
	systemctl start indiair-api indiair-ui

stop:
	systemctl stop indiair-api indiair-ui

restart:
	systemctl restart indiair-api indiair-ui

backup:
	./deploy/scripts/backup.sh

logs:
	journalctl -u indiair-api -f
```

---

## 9. Release Checklist

Before any production deployment:

```
PRE-DEPLOYMENT
[ ] All CI tests passing
[ ] Coverage >= 80%
[ ] No new secrets in code (git grep for common key patterns)
[ ] requirements.txt updated if new packages added
[ ] Alembic migration created for any schema changes
[ ] Migration tested on a copy of prod DB (alembic upgrade head on backup)
[ ] .env.example updated if new env vars added

DEPLOYMENT
[ ] git pull on production server
[ ] pip install -r requirements.txt
[ ] alembic upgrade head
[ ] systemctl restart indiair-api indiair-ui

POST-DEPLOYMENT
[ ] Health endpoint returns 200 (GET /api/v1/health)
[ ] Keyword search returns results
[ ] Company page loads for Laurus Labs
[ ] Check logs/indiair.log for errors in first 5 minutes
[ ] Verify pipeline_runs table shows no new failures
```

---

## 10. Backup and Recovery

### 10.1 Database Backup

```bash
# deploy/scripts/backup.sh
#!/bin/bash
BACKUP_DIR="/opt/indiair/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/indiair_$DATE.sql.gz"

mkdir -p $BACKUP_DIR
pg_dump -U indiair indiair | gzip > $BACKUP_FILE
echo "Backup written to $BACKUP_FILE"

# Keep last 7 daily backups
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
```

Run daily via cron: `0 2 * * * /opt/indiair/deploy/scripts/backup.sh`

### 10.2 Recovery Time Objectives

| Scenario | RTO |
|---|---|
| Code rollback | < 10 minutes |
| Database restore from backup | < 30 minutes |
| Full re-extraction from raw PDFs | < 8 hours (same as backfill) |
| ES index rebuild from Postgres | < 4 hours |

Raw PDFs are the ultimate source of truth. If the database is lost but PDFs are intact, everything can be reconstructed by re-running the pipeline.

---

## 11. Capacity Planning

MVP corpus estimate:

| Data type | Estimated volume |
|---|---|
| Raw PDFs (30 companies × 5 years × ~20 filings/year) | ~3,000 PDFs × avg 1MB = ~3GB |
| Postgres data | ~500MB |
| ES index | ~1GB |
| pgvector embeddings (500k chunks × 1536 dims × 4 bytes) | ~3GB |
| **Total storage** | **~8GB** |

Minimum server spec for MVP: 8GB RAM, 4 vCPU, 50GB SSD. Cost on a typical cloud provider: ~$30–50/month.

---

*Last Updated: April 2026 | Version 1.0*
