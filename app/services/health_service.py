from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.common import HealthResponse


def check_health(db: Session) -> tuple[int, HealthResponse]:
    db_status = "ok"
    storage_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"
    try:
        settings.local_storage_path.mkdir(parents=True, exist_ok=True)
        probe = settings.local_storage_path / ".healthcheck"
        probe.touch(exist_ok=True)
        probe.unlink(missing_ok=True)
    except Exception:
        storage_status = "error"
    status = "ok" if db_status == "ok" and storage_status == "ok" else "degraded"
    return (200 if status == "ok" else 503), HealthResponse(
        status=status,
        db=db_status,
        storage=storage_status,
        timestamp=datetime.now(UTC),
    )
