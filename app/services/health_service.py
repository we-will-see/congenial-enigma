from datetime import UTC, datetime

from elasticsearch import Elasticsearch
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.common import HealthResponse


def check_health(db: Session) -> tuple[int, HealthResponse]:
    db_status = "ok"
    es_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"
    try:
        Elasticsearch(settings.es_host).ping()
    except Exception:
        es_status = "error"
    status = "ok" if db_status == "ok" and es_status == "ok" else "degraded"
    return (200 if status == "ok" else 503), HealthResponse(status=status, db=db_status, es=es_status, timestamp=datetime.now(UTC))
