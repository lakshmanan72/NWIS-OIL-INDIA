import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_a_existing_wcr_well_015160_resolves_wcr_document():
    """
    Test Case A: Existing dynamic WCR well (WELL-015160, NHK-542)
    Resolves linked WCR document -> returns 200 with actual document ID and metadata.
    """
    resp = client.get("/api/wells/WELL-015160/document")
    assert resp.status_code == 200
    data = resp.json()
    assert data["well_id"] == "WELL-015160"
    assert data["document_id"].startswith("DOC-")
    assert data["document_type"] == "WCR"
    assert "nhk" in data["file_name"].lower() or "542" in data["file_name"].lower() or data["file_name"].endswith(".pdf")
    assert data["has_document"] is True
    assert data["review_url"] == f"/documents/{data['document_id']}/review"

    # Direct document review endpoint works
    doc_resp = client.get(f"/api/documents/{data['document_id']}")
    assert doc_resp.status_code == 200
    doc_data = doc_resp.json()
    assert doc_data["document"]["document_id"] == data["document_id"]
    assert doc_data["document"]["well_id"] == "WELL-015160"

    # Direct well ID route on /api/documents/ safely resolves to document
    well_route_resp = client.get("/api/documents/WELL-015160")
    assert well_route_resp.status_code == 200
    w_data = well_route_resp.json()
    assert w_data["document"]["document_id"] == data["document_id"]
    assert w_data["resolved_from_well_id"] == "WELL-015160"


def test_b_another_wcr_well_000001_and_000050():
    """
    Test Case B: Historical and existing WCR wells (WELL-000001 and WELL-000050)
    Resolves linked WCR document -> review payload loads successfully.
    """
    # 1. Historical well WELL-000001
    resp1 = client.get("/api/wells/WELL-000001/document")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["well_id"] == "WELL-000001"
    assert data1["document_id"] == "DOC-00000001"
    assert data1["document_type"] == "WCR"
    assert data1["file_name"] == "WELL-000001_WCR_2021.pdf"
    assert data1["has_document"] is True

    # Check review endpoint for historical document
    doc1_resp = client.get("/api/documents/DOC-00000001")
    assert doc1_resp.status_code == 200
    doc1_data = doc1_resp.json()
    assert doc1_data["document"]["document_id"] == "DOC-00000001"
    assert doc1_data["document"]["well_id"] == "WELL-000001"
    assert len(doc1_data["extractions"]) > 0

    # 2. Well WELL-000050
    resp50 = client.get("/api/wells/WELL-000050/document")
    assert resp50.status_code == 200
    data50 = resp50.json()
    assert data50["well_id"] == "WELL-000050"
    assert data50["document_id"].startswith("DOC-")
    assert data50["document_type"] == "WCR"

    doc50_resp = client.get(f"/api/documents/{data50['document_id']}")
    assert doc50_resp.status_code == 200


def test_c_well_without_wcr_document_015149():
    """
    Test Case C: Well without WCR document (WELL-015149)
    Returns semantic 404: "No WCR document available for well 'WELL-015149'".
    Frontend avoids generic 404 page and shows "WCR Document Not Available" state.
    """
    resp = client.get("/api/wells/WELL-015149/document")
    assert resp.status_code == 404
    detail = resp.json()["detail"]
    assert "No WCR document available for well 'WELL-015149'" in detail

    # Also test via documents well-ID route
    doc_resp = client.get("/api/documents/WELL-015149")
    assert doc_resp.status_code == 404
    assert "No WCR document available for well 'WELL-015149'" in doc_resp.json()["detail"]


def test_d_direct_review_url_with_valid_document_id():
    """
    Test Case D: Direct review URL using a valid document_id opens successfully.
    """
    resp = client.get("/api/documents/DOC-00000001")
    assert resp.status_code == 200
    data = resp.json()
    assert "document" in data
    assert "extractions" in data
    assert "events" in data
    assert data["document"]["document_id"] == "DOC-00000001"


def test_e_invalid_document_id_returns_proper_document_not_found():
    """
    Test Case E: Invalid document_id produces standard "Document Not Found" 404.
    """
    resp = client.get("/api/documents/DOC-NON-EXISTENT-XYZ-999")
    assert resp.status_code == 404
    detail = resp.json()["detail"]
    assert "Document 'DOC-NON-EXISTENT-XYZ-999' not found." in detail


def test_f_map_markers_reflect_accurate_wcr_availability():
    """
    Test Case F: Map markers dataset correctly supplies source_document
    for wells with WCR, and None for wells without WCR.
    """
    resp = client.get("/api/wells/map-markers?include_new=true")
    assert resp.status_code == 200
    markers = resp.json()["markers"]

    # WELL-015160 has WCR document
    m_15160 = next((m for m in markers if m["well_id"] == "WELL-015160"), None)
    assert m_15160 is not None
    assert m_15160["source_document"] is not None
    assert m_15160["source_document"].startswith("DOC-")

    # WELL-000001 has historical WCR document
    m_000001 = next((m for m in markers if m["well_id"] == "WELL-000001"), None)
    assert m_000001 is not None
    assert m_000001["source_document"] == "DOC-00000001"

    # WELL-015149 does not have WCR document
    m_015149 = next((m for m in markers if m["well_id"] == "WELL-015149"), None)
    assert m_015149 is not None
    assert m_015149["source_document"] is None


def test_g_nonexistent_well_returns_well_not_found():
    """
    Test Case G: Querying document for nonexistent well returns 'Well not found'.
    """
    resp = client.get("/api/wells/WELL-999999/document")
    assert resp.status_code == 404
    assert "Well 'WELL-999999' not found." in resp.json()["detail"]
