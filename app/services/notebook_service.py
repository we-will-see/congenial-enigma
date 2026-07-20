from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.notebook import Notebook, NotebookDocument
from app.schemas.notebooks import NotebookCreate, NotebookDocumentAdd, NotebookDocumentOut, NotebookOut


def create_notebook(db: Session, request: NotebookCreate) -> Notebook:
    notebook = Notebook(**request.model_dump())
    db.add(notebook)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError(f"notebook {request.name!r} already exists in namespace {request.namespace_id!r}") from exc
    db.refresh(notebook)
    return notebook


def list_notebooks(db: Session, namespace_id: str | None = None) -> list[NotebookOut]:
    count = func.count(NotebookDocument.document_id).label("document_count")
    stmt = (
        select(Notebook, count)
        .outerjoin(NotebookDocument, NotebookDocument.notebook_id == Notebook.id)
        .group_by(Notebook.id)
        .order_by(Notebook.updated_at.desc(), Notebook.id.desc())
    )
    if namespace_id:
        stmt = stmt.where(Notebook.namespace_id == namespace_id)
    return [
        NotebookOut.model_validate(notebook).model_copy(update={"document_count": document_count})
        for notebook, document_count in db.execute(stmt)
    ]


def get_notebook(db: Session, notebook_id: int) -> Notebook | None:
    return db.get(Notebook, notebook_id)


def add_document_to_notebook(
    db: Session,
    notebook_id: int,
    document_id: int,
    request: NotebookDocumentAdd,
) -> NotebookDocument:
    if not db.get(Notebook, notebook_id):
        raise ValueError(f"notebook {notebook_id} not found")
    if not db.get(Document, document_id):
        raise ValueError(f"document {document_id} not found")
    membership = db.get(NotebookDocument, (notebook_id, document_id))
    if membership:
        membership.tags = _clean_tags(request.tags)
        membership.added_by = request.added_by or membership.added_by
    else:
        membership = NotebookDocument(
            notebook_id=notebook_id,
            document_id=document_id,
            tags=_clean_tags(request.tags),
            added_by=request.added_by,
        )
        db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


def remove_document_from_notebook(db: Session, notebook_id: int, document_id: int) -> bool:
    membership = db.get(NotebookDocument, (notebook_id, document_id))
    if not membership:
        return False
    db.delete(membership)
    db.commit()
    return True


def list_notebook_documents(db: Session, notebook_id: int) -> list[NotebookDocumentOut]:
    rows = db.execute(
        select(NotebookDocument, Document)
        .join(Document, Document.id == NotebookDocument.document_id)
        .where(NotebookDocument.notebook_id == notebook_id)
        .order_by(NotebookDocument.added_at.desc(), Document.id.desc())
    )
    return [
        NotebookDocumentOut(
            notebook_id=membership.notebook_id,
            document_id=document.id,
            title=document.title,
            document_type=document.document_type,
            source_type=document.source_type,
            extraction_status=document.extraction_status,
            tags=membership.tags or [],
            added_by=membership.added_by,
            added_at=membership.added_at,
        )
        for membership, document in rows
    ]


def _clean_tags(tags: list[str]) -> list[str]:
    cleaned = [tag.strip().lower()[:100] for tag in tags if tag.strip()]
    return list(dict.fromkeys(cleaned))
