import os
import io
import json
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.well_service import well_service
from backend.app.repositories.well_repository import well_repository
from backend.document_ai.wcr_extractor import wcr_extractor

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_pristine_database_state():
    """
    Ensures dynamic wells start with exactly 51 base dynamic wells (WELL-015109 to WELL-015159)
    so total active well count is exactly 15,159 prior to the WCR test.
    """
    base_file = "backend/data/documents/base_51_dynamic_wells.json"
    dyn_file = well_repository._dynamic_wells_file
    if os.path.exists(base_file):
        with open(base_file, "r", encoding="utf-8") as f:
            base_data = json.load(f)
        with open(dyn_file, "w", encoding="utf-8") as f:
            json.dump(base_data, f, indent=2)
    well_repository.reload_dynamic_wells()
    assert well_repository.get_total_count() == 15159


def test_1_current_database_count_is_read_dynamically():
    """TEST 1: Current database count is read dynamically from API / database."""
    resp = client.get("/api/wells/count")
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data
    assert data["count"] == 15159
    assert data["original_seed_count"] == 15108
    assert data["data_source"] == "DYNAMIC_DATABASE"


def test_2_and_3_nhk_542_produces_well_015160_and_count_15160():
    """
    TEST 2: If database count is 15,159, next WCR gets WELL-015160.
    TEST 3: After insertion, count = 15,160.
    TEST 10: Valid NHK-542 WCR produces WELL-015160, 27.311833, 95.354111, 3 drilling events.
    """
    # 1. Verify count before
    resp_before = client.get("/api/wells/count").json()
    count_before = resp_before["count"]
    assert count_before == 15159

    # Read real_wcr_nhk_542.pdf
    pdf_path = "real_wcr_nhk_542.pdf"
    assert os.path.exists(pdf_path), "real_wcr_nhk_542.pdf must exist"
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    # Upload WCR
    upload_resp = client.post(
        "/api/wcr/upload",
        files={"file": ("real_wcr_nhk_542.pdf", pdf_bytes, "application/pdf")},
        data={"uploaded_by": "Senior Drilling Engineer"}
    )
    assert upload_resp.status_code == 200
    u_data = upload_resp.json()
    doc_id = u_data["document_id"]
    coords = u_data["coordinates"]
    meta = u_data["extracted_metadata"]
    events = u_data["drilling_events"]

    # Verify extracted data
    assert meta["well_name"] == "NHK-542"
    assert meta["operator"] == "Oil India Limited"
    assert meta["field"] == "Nahorkatiya"
    assert meta["formation"] == "Barail Sandstone"
    assert meta["total_depth"] == 3450.0
    assert abs(coords["latitude"] - 27.311833) < 0.001
    assert abs(coords["longitude"] - 95.354111) < 0.001
    assert coords["coordinate_source"] == "WCR_DOCUMENT"
    assert len(events) >= 3, f"Expected at least 3 drilling events, got {len(events)}"

    # Add well to NWIS
    create_payload = {
        "well_name": meta["well_name"],
        "latitude": coords["latitude"],
        "longitude": coords["longitude"],
        "coordinate_source": "WCR_DOCUMENT",
        "operator": meta["operator"],
        "field": meta["field"],
        "basin": meta["basin"],
        "total_depth": meta["total_depth"],
        "formation": meta["formation"],
        "spud_date": meta["spud_date"],
        "completion_date": meta["completion_date"],
        "force_confirm": True,
        "reviewer": "Chief Drilling Engineer"
    }

    create_resp = client.post(f"/api/wcr/{doc_id}/create-well", json=create_payload)
    assert create_resp.status_code == 200
    c_data = create_resp.json()
    
    assert c_data["success"] is True
    # If starting at 15159, becomes WELL-015160
    assert c_data["well_id"] == "WELL-015160"
    assert c_data["total_wells"] == 15160

    # Verify count after insertion is 15,160
    resp_after = client.get("/api/wells/count").json()
    assert resp_after["count"] == 15160


def test_4_next_insertion_produces_well_015161():
    """TEST 4: Next insertion produces WELL-015161."""
    # Check count before
    cnt_before = client.get("/api/wells/count").json()["count"]
    assert cnt_before == 15160

    # Create dummy canonical well
    payload = {
        "well_name": "WILDCAT-TEST-015161",
        "latitude": 27.450000,
        "longitude": 95.600000,
        "operator": "Oil India Limited",
        "field": "Nahorkatiya",
        "basin": "Assam-Arakan",
        "force_confirm": True,
        "reviewer": "Test Suite",
    }
    try:
        created_well = well_repository.create_canonical_well(payload)
        assert created_well.well_id == "WELL-015161"

        # Count becomes 15,161
        cnt_after = client.get("/api/wells/count").json()["count"]
        assert cnt_after == 15161
    finally:
        # Revert temporary 015161 well so state after test 2 and 3 stays at 15,160
        dyn_file = well_repository._dynamic_wells_file
        if os.path.exists(dyn_file):
            with open(dyn_file, "r", encoding="utf-8") as f:
                wells_data = json.load(f)
            wells_data = [w for w in wells_data if w.get("well_id") != "WELL-015161"]
            with open(dyn_file, "w", encoding="utf-8") as f:
                json.dump(wells_data, f, indent=2)
        well_repository.reload_dynamic_wells()


def test_5_duplicate_detection_searches_all_wells():
    """TEST 5: Duplicate detection searches all current wells, not only the 15,108 seed wells."""
    # NHK-542 is WELL-015160, a dynamic well beyond 15,108
    cand = {
        "well_name": "NHK-542",
        "operator": "Oil India Limited",
        "latitude": 27.311833,
        "longitude": 95.354111,
    }
    dup_res = wcr_extractor.detect_duplicate(cand, existing_wells_repo=well_repository)
    assert dup_res["is_duplicate"] is True
    assert dup_res["existing_well"]["well_id"] == "WELL-015160"


def test_6_no_existing_well_is_deleted_or_modified():
    """TEST 6: Seed wells (e.g. WELL-000001, WELL-015108) remain intact."""
    w1 = well_repository.get_well("WELL-000001")
    assert w1 is not None
    assert w1.well_id == "WELL-000001"

    w_seed_last = well_repository.get_well("WELL-015108")
    assert w_seed_last is not None
    assert w_seed_last.well_id == "WELL-015108"


def test_7_header_count_matches_database_count():
    """TEST 7: Verify /api/wells/count equals total canonical count."""
    resp = client.get("/api/wells/count").json()
    assert resp["count"] == well_repository.get_total_count()


def test_8_map_marker_dataset_matches_database_count():
    """TEST 8: Map marker count matches dynamic count."""
    resp_map = client.get("/api/wells/map-markers?include_new=true").json()
    resp_cnt = client.get("/api/wells/count").json()
    assert resp_map["count"] == resp_cnt["count"]


def test_9_missing_coordinates_produce_insufficient_evidence():
    """TEST 9: Missing coordinates produce INSUFFICIENT_EVIDENCE and are not placed on map."""
    assert os.path.exists("wcr_no_coords_demo.pdf")
    with open("wcr_no_coords_demo.pdf", "rb") as f:
        pdf_bytes = f.read()

    upload_resp = client.post(
        "/api/wcr/upload",
        files={"file": ("wcr_no_coords_demo.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_resp.status_code == 200
    u_data = upload_resp.json()
    assert u_data["pipeline_status"] == "INSUFFICIENT_EVIDENCE"
    assert u_data["coordinates"]["location_status"] == "INSUFFICIENT_EVIDENCE"
    assert u_data["coordinates"]["latitude"] is None
    assert u_data["coordinates"]["longitude"] is None
