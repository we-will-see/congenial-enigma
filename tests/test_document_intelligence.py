from app.main import app
from app.core.config import settings
from app.models.document import Document
from app.models.notebook import Notebook
from app.pipeline.document_indexer import build_page_chunk_specs
from app.pipeline.orchestrator import _extract_document
from app.pipeline.storage import sanitize_filename, store_uploaded_document, validate_upload
from app.schemas.notebooks import EvidencePack, NotebookSearchRequest
from app.services import notebook_search
from app.services.notebook_search import _citation, _keyword_stmt, _semantic_stmt, reciprocal_rank_fusion
from sqlalchemy.dialects import postgresql


def test_manual_upload_routes_are_exposed() -> None:
    paths = app.openapi()["paths"]
    assert "/api/v1/documents/upload" in paths
    assert "/api/v1/documents/add-text" in paths
    assert "/api/v1/notebooks/{notebook_id}/search" in paths
    assert "/api/v1/qa/ask" not in paths


def test_upload_validation_removes_path_components_and_checks_pdf_header() -> None:
    assert sanitize_filename("../../Board Pack 1.pdf") == "Board Pack 1.pdf"
    assert validate_upload("report.pdf", "application/pdf", b"%PDF-1.7\nbody") == (
        "report.pdf",
        "application/pdf",
    )


def test_upload_validation_rejects_disguised_pdf() -> None:
    try:
        validate_upload("report.pdf", "application/pdf", b"not a pdf")
    except ValueError as exc:
        assert "valid PDF header" in str(exc)
    else:
        raise AssertionError("disguised PDF was accepted")


def test_manual_storage_is_content_addressed_and_idempotent(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "local_storage_path", tmp_path)
    content = b"source document text"
    first = store_uploaded_document(content, "notes.txt", "text/plain", "500123")
    second = store_uploaded_document(content, "notes.txt", "text/plain", "500123")
    assert first == second
    assert first[0].read_bytes() == content
    assert first[1] in str(first[0])


def test_utf8_extraction_preserves_manual_page_boundaries(tmp_path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("First page evidence.\fSecond page evidence.", encoding="utf-8")
    document = Document(event_id=1, document_type="other", mime_type="text/plain", storage_path=str(path))
    result = _extract_document(document)
    assert result.method == "utf8"
    assert result.page_count == 2
    assert result.page_texts == ["First page evidence.", "Second page evidence."]


def test_page_chunking_keeps_exact_page_provenance_and_overlap() -> None:
    specs = build_page_chunk_specs(
        [(1, "one two three four five"), (2, "alpha beta")],
        max_words=3,
        overlap_words=1,
    )
    assert [(spec.ordinal, spec.page_start, spec.page_end, spec.text) for spec in specs] == [
        (0, 1, 1, "one two three"),
        (1, 1, 1, "three four five"),
        (2, 2, 2, "alpha beta"),
    ]
    assert all(len(spec.text_hash) == 64 for spec in specs)


def test_reciprocal_rank_fusion_rewards_cross_method_matches() -> None:
    scores = reciprocal_rank_fusion([[10, 20, 30], [30, 10, 40]])
    assert scores[10] > scores[20]
    assert scores[30] > scores[20]
    assert scores[40] < scores[10]


def test_evidence_contract_has_citations_but_no_generated_answer() -> None:
    assert _citation(12, 2, 4, 4, 9) == "doc:12:v2:p4:chunk:9"
    assert _citation(12, 2, 4, 6, 9) == "doc:12:v2:p4-6:chunk:9"
    assert "evidence" in EvidencePack.model_fields
    assert "answer" not in EvidencePack.model_fields


def test_hybrid_search_degrades_to_keyword_when_embeddings_fail(monkeypatch) -> None:
    class StubSession:
        def get(self, _model, _identifier):
            return Notebook(id=1, namespace_id="default", name="research")

    class BrokenProvider:
        def embed_query(self, _query):
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr(notebook_search, "_keyword_rows", lambda *_args: [])
    result = notebook_search.search_notebook(
        StubSession(),
        1,
        NotebookSearchRequest(query="capacity ramp", mode="hybrid"),
        embedding_provider=BrokenProvider(),
    )
    assert result.retrieval_mode == "keyword_fallback"
    assert result.evidence == []


def test_notebook_search_statements_compile_for_postgresql() -> None:
    request = NotebookSearchRequest(
        query="capacity ramp",
        company_ids=[1],
        document_types=["concall_transcript"],
        top_k=5,
    )
    keyword_sql = str(_keyword_stmt(7, request, 20).compile(dialect=postgresql.dialect()))
    semantic_sql = str(_semantic_stmt(7, request, [0.0] * 1536, 20).compile(dialect=postgresql.dialect()))
    assert "to_tsvector" in keyword_sql
    assert "notebook_documents" in keyword_sql
    assert "<=>" in semantic_sql
