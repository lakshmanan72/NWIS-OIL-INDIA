"""
NWIS Test Suite: Dynamic WCR Document Link & Persistence Pipeline
================================================================
Verifies that:
1. Dynamic WCR wells (e.g., WELL-015138, WELL-015160) have valid, persisted DOC-WCR-... IDs.
2. GET /api/wells/{well_id}/document resolves to the correct document_id and returns 200.
3. GET /api/documents/{document_id} loads the document review details without 404.
4. Historical seed wells (WELL-000001, WELL-000050) resolve to their linked WCR documents.
5. Wells without WCR documents (e.g., WELL-015149) return semantic 404 / unavailable state.
6. The full WCR upload -> well creation pipeline persists source_document across wells and documents.
7. Map markers receive source_document = DOC-WCR-... enabling "View WCR Document".
"""
import io
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


# =============================================================================
# 1. Verification for WELL-015138 (Repaired Dynamic WCR Well)
# =============================================================================

def test_well_015138_document_resolution():
    """
    Verifies WELL-015138:
    - GET /api/wells/WELL-015138/document returns 200 OK
    - document_id starts with DOC-WCR-
    - document_type == 'WCR'
    - has_document == True
    - GET /api/documents/{document_id} returns 200 OK
    """
    resp = client.get("/api/wells/WELL-015138/document")
    assert resp.status_code == 200, f"Expected 200 for WELL-015138 document, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["well_id"] == "WELL-015138"
    assert data["has_document"] is True
    assert data["document_type"] == "WCR"
    assert data["document_id"].startswith("DOC-WCR-")
    assert data["document_id"] == "DOC-WCR-BF3D5491"

    # Verify review endpoint
    doc_resp = client.get(f"/api/documents/{data['document_id']}")
    assert doc_resp.status_code == 200
    doc_data = doc_resp.json()
    assert doc_data["document"]["document_id"] == "DOC-WCR-BF3D5491"
    assert doc_data["document"]["document_type"] == "WCR"


def test_well_015138_map_marker():
    """Verifies that the interactive map marker for WELL-015138 carries source_document."""
    resp = client.get("/api/wells/map-markers?include_new=true")
    assert resp.status_code == 200
    markers = resp.json().get("markers", [])
    marker = next((m for m in markers if m.get("well_id") == "WELL-015138"), None)
    assert marker is not None, "WELL-015138 marker must be present on the map"
    assert marker["source_document"] == "DOC-WCR-BF3D5491"
    assert marker["coordinate_source"] == "WCR_DOCUMENT"
    assert marker["source_id"] == "DYNAMIC_WCR"


# =============================================================================
# 2. Verification for WELL-015160 (Uploaded Real WCR Well)
# =============================================================================

def test_well_015160_document_resolution():
    """
    Verifies WELL-015160:
    - GET /api/wells/WELL-015160/document returns 200 OK
    - document_id starts with DOC-WCR-
    - document_type == 'WCR'
    - has_document == True
    """
    resp = client.get("/api/wells/WELL-015160/document")
    assert resp.status_code == 200
    data = resp.json()
    assert data["well_id"] == "WELL-015160"
    assert data["has_document"] is True
    assert data["document_type"] == "WCR"
    assert data["document_id"].startswith("DOC-WCR-")

    doc_resp = client.get(f"/api/documents/{data['document_id']}")
    assert doc_resp.status_code == 200


# =============================================================================
# 3. Verification for Canonical Seed Wells (WELL-000001 and WELL-000050)
# =============================================================================

def test_canonical_well_000001_document_resolution():
    """Verifies historical seed well WELL-000001 resolves to its linked WCR catalog document."""
    resp = client.get("/api/wells/WELL-000001/document")
    assert resp.status_code == 200
    data = resp.json()
    assert data["well_id"] == "WELL-000001"
    assert data["document_id"] == "DOC-00000001"
    assert data["document_type"] == "WCR"
    assert data["has_document"] is True

    # Review cockpit loads historical document successfully
    doc_resp = client.get("/api/documents/DOC-00000001")
    assert doc_resp.status_code == 200


def test_canonical_well_000050_document_resolution():
    """Verifies canonical well WELL-000050 resolves to its linked WCR document."""
    resp = client.get("/api/wells/WELL-000050/document")
    assert resp.status_code == 200
    data = resp.json()
    assert data["well_id"] == "WELL-000050"
    assert data["document_type"] == "WCR"
    assert data["has_document"] is True

    doc_resp = client.get(f"/api/documents/{data['document_id']}")
    assert doc_resp.status_code == 200


# =============================================================================
# 4. Verification for Wells Without WCR Document (WELL-015149)
# =============================================================================

def test_well_015149_unavailable_state():
    """
    Verifies that a well without a WCR document:
    - GET /api/wells/WELL-015149/document returns 404 with semantic detail
    - GET /api/documents/WELL-015149 returns 404 with semantic detail
    - Does NOT crash or return generic server error
    """
    resp = client.get("/api/wells/WELL-015149/document")
    assert resp.status_code == 404
    assert "No WCR document available for well 'WELL-015149'" in resp.json()["detail"]

    # Direct document endpoint fallback returns clear 404
    doc_resp = client.get("/api/documents/WELL-015149")
    assert doc_resp.status_code == 404
    assert "No WCR document available for well 'WELL-015149'" in doc_resp.json()["detail"]


# =============================================================================
# 5. End-to-End Pipeline: Upload WCR -> Well Created -> source_document Linked
# =============================================================================

def test_wcr_upload_creates_and_persists_source_document():
    """
    Guarantees end-to-end WCR upload flow:
    1. Upload WCR PDF -> document_id generated as DOC-WCR-...
    2. Create well from WCR -> well.source_document set to doc_id
    3. GET /api/wells/{new_well_id}/document returns 200 with doc_id
    4. GET /api/documents/{doc_id} returns 200
    5. Map marker receives source_document = doc_id
    """
    import uuid
    from backend.tests.test_wcr_workflow_integration import build_wcr_pdf
    run_id = uuid.uuid4().hex[:6]
    pdf_bytes = build_wcr_pdf([
        f"WELL COMPLETION REPORT\nWell Name: DIB-REGRESS-{run_id}\nOperator: Oil India Limited\nField: Dibrugarh Exploration\nBasin: Assam-Arakan\nTotal Depth: 3820 m\nFormation: Tipam Sandstone\nLatitude: 27 deg 12 min 34.5 sec N\nLongitude: 95 deg 07 min 24.2 sec E"
    ])
    files = {"file": (f"WCR_REGRESS_{run_id}.pdf", pdf_bytes, "application/pdf")}
    upload_resp = client.post(
        "/api/wcr/upload",
        files=files,
        data={"uploaded_by": "Test Operations Engineer"},
    )
    assert upload_resp.status_code == 200
    u_data = upload_resp.json()
    doc_id = u_data["document_id"]
    assert doc_id.startswith("DOC-WCR-")

    # Create well from WCR
    create_resp = client.post(
        f"/api/wcr/{doc_id}/create-well",
        json={
            "well_name": f"DIB-REGRESS-{run_id}",
            "operator": "Oil India Limited",
            "field": "Dibrugarh Exploration",
            "basin": "Assam-Arakan",
            "latitude": 27.24521,
            "longitude": 94.81872,
            "total_depth": 3820.0,
            "formation": "Tipam Sandstone",
            "coordinate_source": "WCR_DOCUMENT",
            "force_confirm": True,
        }
    )
    assert create_resp.status_code == 200
    c_data = create_resp.json()
    new_well_id = c_data["well_id"]
    assert c_data["source_document"] == doc_id

    # Verify GET /api/wells/{new_well_id}/document
    link_resp = client.get(f"/api/wells/{new_well_id}/document")
    assert link_resp.status_code == 200
    link_data = link_resp.json()
    assert link_data["well_id"] == new_well_id
    assert link_data["document_id"] == doc_id
    assert link_data["document_type"] == "WCR"
    assert link_data["has_document"] is True

    # Verify Review Page API
    review_resp = client.get(f"/api/documents/{doc_id}")
    assert review_resp.status_code == 200

    # Verify map marker carries source_document
    marker_resp = client.get("/api/wells/map-markers?include_new=true")
    assert marker_resp.status_code == 200
    markers = marker_resp.json().get("markers", [])
    new_marker = next((m for m in markers if m.get("well_id") == new_well_id), None)
    assert new_marker is not None
    assert new_marker["source_document"] == doc_id
    assert new_marker["is_new_well"] is True
