from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1.companies import router as companies_router
from app.api.v1.documents import router as documents_router
from app.api.v1.health import router as health_router
from app.api.v1.management_changes import router as management_router
from app.api.v1.qa import router as qa_router
from app.api.v1.search import router as search_router
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(title="IndiaIR API", version="0.1.0")


@app.exception_handler(Exception)
async def unhandled_exception(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"error": str(exc), "code": "INTERNAL_ERROR"})


@app.exception_handler(HTTPException)
async def http_exception(_: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail and "code" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail), "code": "HTTP_ERROR"})


@app.exception_handler(RequestValidationError)
async def validation_exception(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"error": str(exc), "code": "VALIDATION_ERROR"})


app.include_router(health_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(qa_router, prefix="/api/v1")
app.include_router(companies_router, prefix="/api/v1")
app.include_router(management_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
