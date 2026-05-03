from __future__ import annotations

from datetime import datetime

from elasticsearch import Elasticsearch
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.core.config import get_settings
from api.core.logging import configure_logging
from api.db.models import Company, Document, Event, Financial, ManagementChange
from api.db.session import get_db
from api.schemas.contracts import CompanyOut, HealthResponse, PaginatedManagementChanges, QARequest, SearchRequest
from ingestion.scheduler import build_scheduler
from services.pipeline_service import PipelineService, create_mock_corpus
from services.rag_service import RAGService
from services.search_service import SearchService

configure_logging()
app = FastAPI(title="IndiaIR API", version="0.1.0")
search_service = SearchService()
rag_service = RAGService()
scheduler = None


@app.on_event("startup")
def startup() -> None:
    global scheduler
    try:
        scheduler = build_scheduler()
        scheduler.start()
    except Exception:
        scheduler = None


@app.on_event("shutdown")
def shutdown() -> None:
    if scheduler:
        scheduler.shutdown(wait=False)


@app.get("/api/v1/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    db_status = "ok"
    es_status = "ok"
    details = {}
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        db_status = "error"
        details["db_error"] = str(exc)
    try:
        es_status = "ok" if Elasticsearch(get_settings().es_host, request_timeout=2).ping() else "error"
    except Exception as exc:
        es_status = "error"
        details["es_error"] = str(exc)
    return HealthResponse(status="ok" if db_status == "ok" else "degraded", db=db_status, es=es_status, timestamp=datetime.utcnow(), details=details)


@app.post("/api/v1/search/keyword")
def keyword_search(request: SearchRequest, db: Session = Depends(get_db)):
    return search_service.keyword(db, request)


@app.post("/api/v1/search/semantic")
def semantic_search(request: SearchRequest, db: Session = Depends(get_db)):
    return search_service.semantic(db, request)


@app.post("/api/v1/qa/ask")
def ask(request: QARequest, db: Session = Depends(get_db)):
    return StreamingResponse(rag_service.stream_answer(db, request), media_type="text/event-stream")


@app.get("/api/v1/companies", response_model=list[CompanyOut])
def companies(db: Session = Depends(get_db)):
    return db.scalars(select(Company).where(Company.active.is_(True)).order_by(Company.name)).all()


@app.get("/api/v1/companies/{company_id}")
def company_detail(company_id: int, db: Session = Depends(get_db)):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail={"error": "Company not found", "code": "NOT_FOUND"})
    document_count = db.scalar(select(func.count(Document.id)).join(Event).where(Event.company_id == company_id))
    return {"id": company.id, "scrip_code": company.scrip_code, "name": company.name, "sector": company.sector, "document_count": document_count}


@app.get("/api/v1/companies/{company_id}/events")
def company_events(company_id: int, quarter: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Event).where(Event.company_id == company_id).order_by(Event.event_date.desc())
    if quarter:
        stmt = stmt.where(Event.quarter == quarter)
    return [
        {
            "id": event.id,
            "event_date": event.event_date,
            "event_type": event.event_type,
            "quarter": event.quarter,
            "fy_year": event.fy_year,
            "filing_url": event.filing_url,
            "documents": [{"id": doc.id, "document_type": doc.document_type, "extraction_status": doc.extraction_status} for doc in event.documents],
        }
        for event in db.scalars(stmt).all()
    ]


@app.get("/api/v1/companies/{company_id}/financials")
def company_financials(company_id: int, db: Session = Depends(get_db)):
    return db.scalars(select(Financial).where(Financial.company_id == company_id).order_by(Financial.period)).all()


@app.get("/api/v1/management-changes", response_model=PaginatedManagementChanges)
def management_changes(
    company_id: int | None = None,
    role_category: str | None = None,
    change_type: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    stmt = select(ManagementChange, Company.name).join(Company, Company.id == ManagementChange.company_id)
    if company_id:
        stmt = stmt.where(ManagementChange.company_id == company_id)
    if role_category:
        stmt = stmt.where(ManagementChange.role_category == role_category)
    if change_type:
        stmt = stmt.where(ManagementChange.change_type == change_type)
    if from_date:
        stmt = stmt.where(ManagementChange.filing_date >= from_date)
    if to_date:
        stmt = stmt.where(ManagementChange.filing_date <= to_date)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(stmt.order_by(ManagementChange.filing_date.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"total": total, "page": page, "results": [{**change.__dict__, "company_name": company_name} for change, company_name in rows]}


@app.post("/api/v1/pipeline/process/{document_id}")
def process_document(document_id: int, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail={"error": "Document not found", "code": "NOT_FOUND"})
    PipelineService().process_document(db, document)
    return {"status": document.extraction_status, "document_id": document.id}


@app.post("/api/v1/pipeline/mock-ingest")
def mock_ingest(db: Session = Depends(get_db)):
    create_mock_corpus(db)
    return {"status": "ok"}
