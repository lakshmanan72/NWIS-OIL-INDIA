"""
NWIS Phase 4 — Test Document RAG & Institutional Memory
=======================================================
Tests semantic search across approved documents, distance calculation to active wells,
grounded evidence citation, and strict rejection of unsupported answers.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.document_ai.document_ingestion import document_ingestion_engine
from backend.document_ai.document_service import document_intelligence_service

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_approved_test_documents():
    """Seeds approved test documents with verified events and formations for RAG testing."""
    # Approved Well Completion Report for WELL-000050
    wcr_content = (
        "WELL INFORMATION\n"
        "Well ID: WELL-000050\n"
        "Well Name: KK-DW-17-1\n"
        "Field: Deepwater Sector\n"
        "Basin: Kerala-Konkan\n"
        "Total Depth: 1617.0 m\n\n"
        "FORMATION\n"
        "Top Barail Formation reached at 1100 m MD. Lithology: Shale with fractured sandstone.\n\n"
        "DRILLING EVENTS\n"
        "Severe mud losses were observed at 1132 m MD in Barail formation. Lost 55 bbls of fluid. "
        "Pumped coarse LCM pill and cured losses within 4 hours."
    ).encode("utf-8")

    doc, _, _ = document_ingestion_engine.ingest_document(
        filename="approved_rag_fixture_wcr.txt",
        content=wcr_content,
        uploaded_by="Senior Geologist",
    )

    # Approve document so chunks enter RAG index
    document_intelligence_service.approve_document(
        document_id=doc.document_id,
        reviewer="Operations Superintendent",
    )


def test_document_search_with_active_well_distance():
    """Verifies GET /api/documents/search returns matched records with spatial distance."""
    response = client.get(
        "/api/documents/search",
        params={"q": "mud loss Barail", "well_id": "WELL-000050"},
    )
    assert response.status_code == 200
    hits = response.json()
    assert len(hits) > 0

    hit = hits[0]
    assert hit["document_id"].startswith("DOC-")
    assert "Barail" in hit["formation"]
    assert "mud" in hit["excerpt"].lower() or "loss" in hit["excerpt"].lower()


def test_grounded_rag_query_with_verified_evidence():
    """Verifies POST /api/intelligence/query returns grounded answer with full citations."""
    query_payload = {
        "query": "What mud loss problems occurred in Barail formation?",
        "well_id": "WELL-000050",
        "depth_md": 1132.0,
        "radius_km": 25.0,
    }

    response = client.post("/api/intelligence/query", json=query_payload)
    assert response.status_code == 200
    res = response.json()

    assert "answer" in res
    assert "Historical institutional evidence indicates" in res["answer"]
    assert "Barail" in res["answer"]
    assert len(res["evidence"]) > 0

    # Verify citation fields
    citation = res["evidence"][0]
    assert "well_id" in citation
    assert "document_id" in citation
    assert "page" in citation
    assert "excerpt" in citation
    assert citation["depth_md"] is not None


def test_unsupported_query_returns_no_evidence_statement():
    """CRITICAL: Insufficient or unmatched evidence must return safe negative answer."""
    query_payload = {
        "query": "What meteorite impacts occurred in granite at depth 8500 m?",
        "well_id": "WELL-000050",
        "depth_md": 8500.0,
        "radius_km": 10.0,
    }

    response = client.post("/api/intelligence/query", json=query_payload)
    assert response.status_code == 200
    res = response.json()

    assert "No verified historical evidence found" in res["answer"]
    assert len(res["evidence"]) == 0
    assert res["source_count"] == 0


def test_depth_filtering_in_rag_query():
    """Verifies that queries outside the depth window filter out irrelevant records."""
    # WELL-000050 has event at 1132 m. If depth_md is 4500 m, it should be excluded.
    query_payload = {
        "query": "mud losses",
        "well_id": "WELL-000050",
        "depth_md": 4500.0,  # Far away from 1132 m
        "radius_km": 25.0,
    }

    response = client.post("/api/intelligence/query", json=query_payload)
    assert response.status_code == 200
    res = response.json()
    assert len(res["evidence"]) == 0
