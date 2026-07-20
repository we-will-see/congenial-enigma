from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.notebooks import (
    EvidencePack,
    NotebookCreate,
    NotebookDocumentAdd,
    NotebookDocumentOut,
    NotebookOut,
    NotebookSearchRequest,
)
from app.services.notebook_search import search_notebook
from app.services.notebook_service import (
    add_document_to_notebook,
    create_notebook,
    get_notebook,
    list_notebook_documents,
    list_notebooks,
    remove_document_from_notebook,
)

router = APIRouter(prefix="/notebooks", tags=["notebooks"])


@router.post("", response_model=NotebookOut, status_code=201)
def create(request: NotebookCreate, db: Session = Depends(get_db)) -> NotebookOut:
    try:
        notebook = create_notebook(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc), "code": "NOTEBOOK_EXISTS"}) from exc
    return NotebookOut.model_validate(notebook)


@router.get("", response_model=list[NotebookOut])
def notebooks(namespace_id: str | None = None, db: Session = Depends(get_db)) -> list[NotebookOut]:
    return list_notebooks(db, namespace_id)


@router.get("/{notebook_id}", response_model=NotebookOut)
def notebook_detail(notebook_id: int, db: Session = Depends(get_db)) -> NotebookOut:
    notebook = get_notebook(db, notebook_id)
    if not notebook:
        raise HTTPException(status_code=404, detail={"error": "Notebook not found", "code": "NOTEBOOK_NOT_FOUND"})
    result = NotebookOut.model_validate(notebook)
    result.document_count = len(notebook.document_memberships)
    return result


@router.get("/{notebook_id}/documents", response_model=list[NotebookDocumentOut])
def notebook_documents(notebook_id: int, db: Session = Depends(get_db)) -> list[NotebookDocumentOut]:
    if not get_notebook(db, notebook_id):
        raise HTTPException(status_code=404, detail={"error": "Notebook not found", "code": "NOTEBOOK_NOT_FOUND"})
    return list_notebook_documents(db, notebook_id)


@router.put("/{notebook_id}/documents/{document_id}", response_model=NotebookDocumentOut)
def add_document(
    notebook_id: int,
    document_id: int,
    request: NotebookDocumentAdd,
    db: Session = Depends(get_db),
) -> NotebookDocumentOut:
    try:
        add_document_to_notebook(db, notebook_id, document_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": str(exc), "code": "RESOURCE_NOT_FOUND"}) from exc
    rows = list_notebook_documents(db, notebook_id)
    return next(row for row in rows if row.document_id == document_id)


@router.delete("/{notebook_id}/documents/{document_id}", status_code=204)
def remove_document(notebook_id: int, document_id: int, db: Session = Depends(get_db)) -> Response:
    if not remove_document_from_notebook(db, notebook_id, document_id):
        raise HTTPException(status_code=404, detail={"error": "Notebook document not found", "code": "MEMBERSHIP_NOT_FOUND"})
    return Response(status_code=204)


@router.post("/{notebook_id}/search", response_model=EvidencePack)
def search(notebook_id: int, request: NotebookSearchRequest, db: Session = Depends(get_db)) -> EvidencePack:
    try:
        return search_notebook(db, notebook_id, request)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "not found" in message else 422
        raise HTTPException(status_code=status_code, detail={"error": message, "code": "NOTEBOOK_SEARCH_INVALID"}) from exc
