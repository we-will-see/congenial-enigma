from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.documents import CoverageRow, DocumentOut, TranscriptTurnOut
from app.services.document_service import coverage_dashboard, list_event_documents, list_transcript_turns

router = APIRouter(tags=["documents"])


@router.get("/events/{event_id}/documents", response_model=list[DocumentOut])
def event_documents(event_id: int, db: Session = Depends(get_db)) -> list[DocumentOut]:
    return [DocumentOut.model_validate(document) for document in list_event_documents(db, event_id)]


@router.get("/documents/{document_id}/transcript", response_model=list[TranscriptTurnOut])
def transcript(document_id: int, db: Session = Depends(get_db)) -> list[TranscriptTurnOut]:
    turns = list_transcript_turns(db, document_id)
    if not turns:
        raise HTTPException(status_code=404, detail={"error": "Transcript not found", "code": "TRANSCRIPT_NOT_FOUND"})
    return [TranscriptTurnOut.model_validate(turn) for turn in turns]


@router.get("/coverage", response_model=list[CoverageRow])
def coverage(db: Session = Depends(get_db)) -> list[CoverageRow]:
    return coverage_dashboard(db)
