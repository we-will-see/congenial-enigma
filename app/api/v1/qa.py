from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.rag.qa_service import stream_answer
from app.schemas.qa import QARequest

router = APIRouter(prefix="/qa", tags=["qa"])


@router.post("/ask")
async def ask(request: QARequest, db: Session = Depends(get_db)) -> StreamingResponse:
    return StreamingResponse(stream_answer(db, request), media_type="text/event-stream")
