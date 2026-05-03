from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.search import SearchRequest, SearchResponse
from app.services.search_service import keyword_search, semantic_search

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/keyword", response_model=SearchResponse)
def search_keyword(request: SearchRequest) -> SearchResponse:
    try:
        return keyword_search(request)
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"error": str(exc), "code": "SEARCH_UNAVAILABLE"}) from exc


@router.post("/semantic", response_model=SearchResponse)
def search_semantic(request: SearchRequest, db: Session = Depends(get_db)) -> SearchResponse:
    try:
        return semantic_search(db, request)
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"error": str(exc), "code": "SEMANTIC_SEARCH_UNAVAILABLE"}) from exc
