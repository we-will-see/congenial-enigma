from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from api.core.config import get_settings
from api.db.models import Document
from api.db.session import SessionLocal
from ingestion.bse_poller import BSEPoller
from services.pipeline_service import PipelineService


def poll_bse_all_companies() -> None:
    with SessionLocal() as db:
        poller = BSEPoller(db)
        import asyncio

        asyncio.run(poller.poll_all_companies(date(2020, 4, 1), date.today()))


def index_pending_documents() -> None:
    with SessionLocal() as db:
        pipeline = PipelineService()
        docs = db.scalars(select(Document).where(Document.extraction_status == "pending").limit(25)).all()
        for document in docs:
            pipeline.process_document(db, document)


def build_scheduler() -> BackgroundScheduler:
    settings = get_settings()
    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(poll_bse_all_companies, "cron", hour=9, minute=0, id="poll_bse_all_companies", replace_existing=True)
    scheduler.add_job(index_pending_documents, "interval", minutes=15, id="index_pending_documents", replace_existing=True)
    scheduler.add_job(poll_bse_all_companies, "interval", seconds=settings.bse_poll_interval_seconds, id="poll_bse_interval", replace_existing=True, next_run_time=None)
    return scheduler
