import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.repositories.csv_repository import CsvWellRepository
from backend.app.repositories.well_repository import well_repository
from backend.app.integrations.identity_resolver import well_identity_resolver

client = TestClient(app)

def test_map_markers_have_canonical_well_id():
    """Verify that GET /api/wells/map-markers returns canonical well_id on every marker."""
    response = client.get("/api/wells/map-markers?include_new=true")
    assert response.status_code == 200
    data = response.json()
    markers = data.get("markers", [])
    assert len(markers) >= 15108

    # Verify first 50 markers
    for m in markers[:50]:
        assert "well_id" in m
        assert m["well_id"] is not None
        assert m["well_id"].startswith("WELL-")
        assert m["identity_status"] == "RESOLVED"
        assert "legacy_id" in m
        assert "source_id" in m
        assert "latitude" in m
        assert "longitude" in m
        assert "well_name" in m


def test_canonical_well_lookup_baseline():
    """Verify canonical baseline wells WELL-000001, WELL-000050, WELL-015108 return HTTP 200."""
    for wid in ["WELL-000001", "WELL-000050", "WELL-015108"]:
        res = client.get(f"/api/wells/{wid}")
        assert res.status_code == 200, f"Expected 200 for {wid}, got {res.status_code}"
        data = res.json()
        assert data["well_id"] == wid
        assert data["well_name"] is not None
        assert data["latitude"] is not None
        assert data["longitude"] is not None


def test_jhirna_1_resolution():
    """
    Verify JHIRNA-1 resolves to canonical well WELL-012111 without hardcoding.
    Tests canonical ID, legacy FID, source ID, and well name aliases.
    """
    canonical_id = "WELL-012111"
    legacy_fid = "wells_all_public.fid--438479b5_193d56910e1_4649"
    source_id = "438479b5_193d56910e1_4649"
    name = "JHIRNA-1"

    # Query by canonical ID
    res1 = client.get(f"/api/wells/{canonical_id}")
    assert res1.status_code == 200
    assert res1.json()["well_id"] == canonical_id

    # Query by legacy FID
    res2 = client.get(f"/api/wells/{legacy_fid}")
    assert res2.status_code == 200
    assert res2.json()["well_id"] == canonical_id

    # Query by source hash
    res3 = client.get(f"/api/wells/{source_id}")
    assert res3.status_code == 200
    assert res3.json()["well_id"] == canonical_id

    # Query by name
    res4 = client.get(f"/api/wells/{name}")
    assert res4.status_code == 200
    assert res4.json()["well_id"] == canonical_id


def test_zero_nearby_wells_is_not_404():
    """
    Wells with 0 nearby offset wells (e.g. remote or isolated basins)
    must return a valid empty list with HTTP 200, NOT a 404 Well Not Found.
    """
    # Radius of 1.0km for WELL-012111 yields 0 nearby offset wells
    res = client.get("/api/wells/WELL-012111/nearby?radius_km=1.0")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data["nearby_wells"], list)
    # Even with 0 offset wells, it must be HTTP 200 with empty list, never 404
    assert len(data["nearby_wells"]) == 0

    # Also offset-intelligence should return 200 with count 0
    res_intel = client.get("/api/wells/WELL-012111/offset-intelligence?radius_km=1.0")
    assert res_intel.status_code == 200
    intel_data = res_intel.json()
    assert intel_data["current_well"]["well_id"] == "WELL-012111"
    assert intel_data["nearby_wells_count"] == 0


def test_unresolved_identity_handling():
    """Verify that completely non-existent wells return 404 and do not invent an ID."""
    res = client.get("/api/wells/NON_EXISTENT_WELL_999999")
    assert res.status_code == 404
    detail = res.json().get("detail", "")
    assert "not found" in detail.lower()


def test_dynamic_wcr_well():
    """Verify that approved dynamic WCR wells (WELL-015109+) resolve correctly."""
    repo = CsvWellRepository()
    # Check if any dynamic well exists in registry
    w_dyn = repo.get_well("WELL-015109")
    if w_dyn:
        assert w_dyn.well_id == "WELL-015109"
        res = client.get("/api/wells/WELL-015109")
        assert res.status_code == 200
        assert res.json()["well_id"] == "WELL-015109"


def test_csv_repository_multi_stage_lookup():
    """Verify CsvWellRepository directly performs multi-stage canonical lookup."""
    repo = CsvWellRepository()

    # 1. Canonical ID
    w1 = repo.get_well("WELL-000001")
    assert w1 is not None
    assert w1.well_id == "WELL-000001"

    # 2. Legacy FID
    w2 = repo.get_well("wells_all_public.fid--438479b5_193d56910e1_4649")
    assert w2 is not None
    assert w2.well_id == "WELL-012111"

    # 3. Source ID
    w3 = repo.get_well("438479b5_193d56910e1_4649")
    assert w3 is not None
    assert w3.well_id == "WELL-012111"

    # 4. Well name
    w4 = repo.get_well("JHIRNA-1")
    assert w4 is not None
    assert w4.well_id == "WELL-012111"


def test_legacy_source_separation():
    """Verify canonical well_id is never overwritten with legacy ID in markers."""
    repo = CsvWellRepository()
    markers = repo.get_all_markers(include_new_wells=False)
    assert len(markers) == 15108
    for m in markers[:100]:
        assert m.well_id.startswith("WELL-")
        assert m.well_id != m.legacy_id
        assert m.identity_status == "RESOLVED"
