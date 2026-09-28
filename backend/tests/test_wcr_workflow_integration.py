"""
NWIS WCR Workflow Comprehensive Integration Tests
=================================================
Verifies complete WCR PDF → New Well Extraction → Database → Map Integration:
1. Coordinate extraction and normalization (Decimal, DMS, Dash)
2. Strict anti-hallucination (INSUFFICIENT_EVIDENCE when missing)
3. Duplicate well detection (normalized name, ID, proximity)
4. New well creation with PostGIS POINT(lon lat) logic
5. Document linking and drilling events extraction
6. Map integration with dynamic well count increment (15,108 + 1 = 15,109)
"""

import io
import uuid
import pytest
import pypdf
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.document_ai.wcr_extractor import wcr_extractor, dms_to_decimal
from backend.document_ai.document_repository import document_repository
from backend.app.repositories.well_repository import well_repository
from backend.app.services.well_service import well_service

client = TestClient(app)


def build_wcr_pdf(pages_text: list[str]) -> bytes:
    """Helper to generate standard-compliant PDF bytes with text stream."""
    writer = pypdf.PdfWriter()
    for txt in pages_text:
        lines = [line.strip() for line in txt.split("\n") if line.strip()]
        stream_cmds = ["BT", "/F1 12 Tf", "50 750 Td"]
        for idx, l in enumerate(lines):
            clean_l = l.replace("(", "[").replace(")", "]")
            if idx > 0:
                stream_cmds.append("0 -18 Td")
            stream_cmds.append(f"({clean_l}) Tj")
        stream_cmds.append("ET")
        stream_data = " ".join(stream_cmds).encode("latin-1", "replace")
        header = f"5 0 obj <</Length {len(stream_data)}>>\nstream\n".encode("latin-1")
        raw_pdf = (
            b"%PDF-1.4\n"
            b"1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n"
            b"2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj\n"
            b"3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources <</Font <</F1 4 0 R>>>> /Contents 5 0 R>> endobj\n"
            b"4 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj\n"
            + header + stream_data + b"\nendstream\nendobj\n"
            b"xref\n0 6\n0000000000 65535 f \n"
            b"0000000009 00000 n \n0000000056 00000 n \n0000000111 00000 n \n0000000227 00000 n \n0000000298 00000 n \n"
            b"trailer <</Size 6 /Root 1 0 R>>\nstartxref\n500\n%%EOF\n"
        )
        r = pypdf.PdfReader(io.BytesIO(raw_pdf))
        writer.add_page(r.pages[0])
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# =============================================================================
# 1. Coordinate Parsing & Normalization Tests
# =============================================================================

def test_dms_to_decimal_conversion():
    """Verifies that DMS coordinates normalize to exact decimal degrees."""
    # 27° 12' 34.5" N -> 27.209583
    lat = dms_to_decimal(27, 12, 34.5, "N")
    assert lat == 27.209583

    # 95° 07' 24.2" E -> 95.123389
    lon = dms_to_decimal(95, 7, 24.2, "E")
    assert lon == 95.123389


def test_wcr_extractor_dms_symbols():
    """Verifies extraction of coordinates in DMS format with symbols."""
    text = "WELL COMPLETION REPORT\nLatitude: 27° 12' 34.5\" N\nLongitude: 95° 07' 24.2\" E\nWell Name: TEST-DMS-1"
    res = wcr_extractor.extract_coordinates(text)
    assert res["location_status"] == "VALID"
    assert res["latitude"] == 27.209583
    assert res["longitude"] == 95.123389
    assert res["coordinate_source"] == "WCR_DOCUMENT"
    assert res["is_india_region"] is True
    assert res["postgis_point"] == "POINT(95.123389 27.209583)"


def test_wcr_extractor_dash_format():
    """Verifies extraction of coordinates in dash format."""
    text = "Surface Coordinates: 27-12-34.5 N, 95-07-24.2 E\nWell Name: TEST-DASH-1"
    res = wcr_extractor.extract_coordinates(text)
    assert res["location_status"] == "VALID"
    assert res["latitude"] == 27.209583
    assert res["longitude"] == 95.123389
    assert res["is_india_region"] is True


def test_wcr_extractor_decimal_format():
    """Verifies extraction of coordinates in decimal degrees format."""
    text = "Location: 27.123456, 95.123456\nOperator: Oil India Limited"
    res = wcr_extractor.extract_coordinates(text)
    assert res["location_status"] == "VALID"
    assert res["latitude"] == 27.123456
    assert res["longitude"] == 95.123456
    assert res["is_india_region"] is True


# =============================================================================
# 2. Strict Anti-Hallucination Tests
# =============================================================================

def test_anti_hallucination_when_no_coordinates():
    """Verifies that coordinates are NOT invented when absent in WCR."""
    text = "WELL COMPLETION REPORT\nWell Name: WILDCAT-NO-COORDS\nField: Digboi\nBasin: Assam-Arakan"
    res = wcr_extractor.extract_coordinates(text)
    assert res["location_status"] == "INSUFFICIENT_EVIDENCE"
    assert res["latitude"] is None
    assert res["longitude"] is None
    assert "cannot be placed on the geographic map" in res["message"]


def test_invalid_coordinates_rejected():
    """Verifies that physically invalid coordinates are not silently accepted."""
    text = "Latitude: 127.500000 N, Longitude: 295.123456 E"
    res = wcr_extractor.extract_coordinates(text)
    assert res["location_status"] == "INVALID_COORDINATES"
    assert res["latitude"] is None
    assert res["longitude"] is None


# =============================================================================
# 3. Duplicate Well Detection Tests
# =============================================================================

def test_duplicate_well_detection_by_normalized_name():
    """Verifies that an identical normalized well name triggers POSSIBLE DUPLICATE."""
    # Existing canonical well WELL-000001
    cand = {
        "well_name": "RAJASTHAN-WELL-00001",
        "operator": "ONGC",
        "field": "Mangala",
        "latitude": 25.75,
        "longitude": 71.50,
    }
    dup_res = wcr_extractor.detect_duplicate(cand, existing_wells_repo=well_repository)
    assert dup_res["is_duplicate"] is True
    assert "Identical normalized well name" in dup_res["similarity_reason"]
    assert dup_res["existing_well"]["well_id"] == "WELL-000001"


def test_duplicate_well_detection_by_proximity():
    """Verifies that well within 100 meters triggers duplicate warning."""
    # Get actual coordinates of WELL-000001 from repository
    w1 = well_repository.get_well("WELL-000001")
    assert w1 is not None
    cand = {
        "well_name": "UNIQUE-NEW-NAME",
        "operator": "ONGC",
        "field": "DifferentField",
        "latitude": round(w1.latitude + 0.0002, 6),
        "longitude": round(w1.longitude + 0.0002, 6),
    }
    dup_res = wcr_extractor.detect_duplicate(cand, existing_wells_repo=well_repository)
    assert dup_res["is_duplicate"] is True
    assert "within" in dup_res["similarity_reason"]
    assert dup_res["distance_m"] < 100.0


# =============================================================================
# 4. End-to-End API Pipeline: Upload → Validate → Create Well → Map
# =============================================================================

def test_wcr_upload_api_with_valid_coordinates():
    """Verifies POST /api/wcr/upload successfully parses PDF and extracts all fields."""
    run_id = uuid.uuid4().hex[:6]
    pdf_bytes = build_wcr_pdf([
        f"WELL COMPLETION REPORT\nWell Name: KHOWANG-{run_id}\nOperator: Oil India Limited\nField: Khowang\nBasin: Assam-Arakan\nBlock: AA-ONHP\nTotal Depth: 3850 m\nSpud Date: 2024-02-10\nCompletion Date: 2024-05-18\nTarget Formation: Barail Sandstone\nLatitude: 27 deg 12 min 34.5 sec N\nLongitude: 95 deg 07 min 24.2 sec E",
        "Mud loss of 85 bbls observed at 3120 m depth while drilling Barail formation."
    ])

    response = client.post(
        "/api/wcr/upload",
        files={"file": (f"WCR_KHOWANG_{run_id}.pdf", pdf_bytes, "application/pdf")},
        data={"uploaded_by": "Senior Operations Engineer"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["pipeline_status"] in ["READY_TO_ADD", "DUPLICATE_REVIEW"]

    # Verify extracted coordinates
    coords = data["coordinates"]
    assert coords["location_status"] == "VALID"
    assert coords["latitude"] == 27.209583
    assert coords["longitude"] == 95.123389
    assert coords["coordinate_source"] == "WCR_DOCUMENT"

    # Verify extracted metadata
    meta = data["extracted_metadata"]
    assert f"KHOWANG-{run_id}" in meta["well_name"]
    assert meta["operator"] == "Oil India Limited"
    assert meta["total_depth"] == 3850.0

    # Verify drilling events extracted
    events = data["drilling_events"]
    assert len(events) >= 1
    assert any(e["event_type"] == "Mud Loss" for e in events)


def test_wcr_upload_api_insufficient_evidence():
    """Verifies that PDF lacking coordinates enters INSUFFICIENT_EVIDENCE state."""
    run_id = uuid.uuid4().hex[:6]
    pdf_bytes = build_wcr_pdf([
        f"WELL COMPLETION REPORT\nWell Name: NO-COORD-WELL-{run_id}\nOperator: ONGC\nField: Deepwater\nTotal Depth: 4200 m"
    ])

    response = client.post(
        "/api/wcr/upload",
        files={"file": (f"WCR_NO_COORD_{run_id}.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["pipeline_status"] == "INSUFFICIENT_EVIDENCE"
    assert data["coordinates"]["location_status"] == "INSUFFICIENT_EVIDENCE"
    assert data["coordinates"]["latitude"] is None


def test_wcr_create_well_and_map_increment():
    """
    CRITICAL ACCEPTANCE TEST:
    Upload WCR → Extract → Create Well → PostGIS POINT → Map auto-focus → Count increases by 1.
    """
    run_id = uuid.uuid4().hex[:6]
    # Unique coordinates in Upper Assam (Digboi area)
    test_lat = round(27.380000 + (int(run_id, 16) % 1000) * 0.0002, 6)
    test_lon = round(95.620000 + (int(run_id, 16) % 500) * 0.0002, 6)

    pdf_bytes = build_wcr_pdf([
        f"WELL COMPLETION REPORT\nWell Name: DIBRUGARH-EXP-{run_id}\nOperator: Oil India Limited\nField: Dibrugarh\nBasin: Assam-Arakan\nBlock: AA-ONHP-2024\nTotal Depth: 3740 m\nFormation: Tipam\nLatitude: {test_lat}\nLongitude: {test_lon}",
        "Stuck pipe encountered at 2950 m depth. Jarred free after 4.5 hours."
    ])

    # 1. Upload WCR
    upload_resp = client.post(
        "/api/wcr/upload",
        files={"file": (f"WCR_DIB_{run_id}.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_resp.status_code == 200
    doc_id = upload_resp.json()["document_id"]

    # Check baseline marker count before adding
    markers_before = client.get("/api/wells/map-markers?include_new=true").json()
    initial_count = markers_before["count"]

    # 2. Add Well to NWIS
    create_payload = {
        "well_name": f"DIBRUGARH-EXP-{run_id}",
        "latitude": test_lat,
        "longitude": test_lon,
        "coordinate_source": "WCR_DOCUMENT",
        "operator": "Oil India Limited",
        "field": "Dibrugarh",
        "basin": "Assam-Arakan",
        "block": "AA-ONHP-2024",
        "total_depth": 3740.0,
        "formation": "Tipam",
        "force_confirm": True,
        "reviewer": "Chief Drilling Engineer",
    }

    create_resp = client.post(
        f"/api/wcr/{doc_id}/create-well",
        json=create_payload,
    )
    assert create_resp.status_code == 200
    create_data = create_resp.json()
    assert create_data["success"] is True
    new_well_id = create_data["well_id"]
    assert new_well_id.startswith("WELL-")
    assert create_data["map_action"] == "FOCUS_NEW_WELL"
    assert create_data["latitude"] == test_lat
    assert create_data["longitude"] == test_lon

    # 3. Verify Map Markers count has dynamically incremented by exactly 1
    markers_after = client.get("/api/wells/map-markers?include_new=true").json()
    assert markers_after["count"] == initial_count + 1

    # 4. Verify new well marker is present on map and marked as is_new_well
    new_marker = next((m for m in markers_after["markers"] if m["well_id"] == new_well_id), None)
    assert new_marker is not None
    assert new_marker["well_name"] == f"DIBRUGARH-EXP-{run_id}"
    assert new_marker["latitude"] == test_lat
    assert new_marker["longitude"] == test_lon
    assert new_marker["is_new_well"] is True
    assert new_marker["coordinate_source"] == "WCR_DOCUMENT"
    assert new_marker["source_document"] == doc_id
