import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

SAMPLE_WELL_ID = "WELL-000001"
INVALID_WELL_ID = "WELL-NONEXISTENT-999999"


# 1. Well lookup
def test_well_lookup():
    response = client.get(f"/api/wells/{SAMPLE_WELL_ID}")
    assert response.status_code == 200
    data = response.json()
    assert data["well_id"] == SAMPLE_WELL_ID
    assert "well_name" in data
    assert "operator" in data
    assert "field" in data
    assert "basin" in data
    assert "latitude" in data
    assert "longitude" in data


# 2. Well search
def test_well_search():
    response = client.get("/api/wells/search?q=WELL-000001")
    assert response.status_code == 200
    results = response.json()
    assert isinstance(results, list)
    assert len(results) > 0
    assert any(w["well_id"] == SAMPLE_WELL_ID for w in results)

    # Search by keyword
    resp2 = client.get("/api/wells/search?q=RAJASTHAN")
    assert resp2.status_code == 200
    assert len(resp2.json()) > 0


# 3. Nearby wells
def test_nearby_wells():
    response = client.get(f"/api/wells/{SAMPLE_WELL_ID}/nearby?radius_km=30&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "source_well" in data
    assert data["source_well"]["well_id"] == SAMPLE_WELL_ID
    assert "nearby_wells" in data
    assert isinstance(data["nearby_wells"], list)
    assert len(data["nearby_wells"]) > 0

    first = data["nearby_wells"][0]
    assert "well_id" in first
    assert "distance_km" in first
    assert first["distance_km"] <= 30.0
    assert "same_field" in first
    assert "same_block" in first
    assert "same_basin" in first
    assert "proximity_class" in first


# 4. Invalid well ID
def test_invalid_well_id():
    response = client.get(f"/api/wells/{INVALID_WELL_ID}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# 5. Radius filtering
def test_radius_filtering():
    # Small radius
    resp_small = client.get(f"/api/wells/{SAMPLE_WELL_ID}/nearby?radius_km=5&limit=50")
    assert resp_small.status_code == 200
    small_data = resp_small.json()
    for w in small_data["nearby_wells"]:
        assert w["distance_km"] <= 5.0

    # Large radius
    resp_large = client.get(f"/api/wells/{SAMPLE_WELL_ID}/nearby?radius_km=50&limit=50")
    assert resp_large.status_code == 200
    large_data = resp_large.json()
    assert len(large_data["nearby_wells"]) >= len(small_data["nearby_wells"])


# 6. Historical event retrieval
def test_historical_event_retrieval():
    response = client.get(f"/api/wells/{SAMPLE_WELL_ID}/events")
    assert response.status_code == 200
    data = response.json()
    assert data["well_id"] == SAMPLE_WELL_ID
    assert "events" in data
    assert isinstance(data["events"], list)
    assert len(data["events"]) > 0
    evt = data["events"][0]
    assert "event_id" in evt
    assert "event_type" in evt
    assert "severity" in evt
    assert "depth_md" in evt
    assert "source_document" in evt


# 7. Formation retrieval
def test_formation_retrieval():
    response = client.get(f"/api/wells/{SAMPLE_WELL_ID}/formations")
    assert response.status_code == 200
    data = response.json()
    assert data["well_id"] == SAMPLE_WELL_ID
    assert "formations" in data
    assert len(data["formations"]) > 0
    f = data["formations"][0]
    assert "formation_id" in f
    assert "formation_name" in f
    assert "lithology" in f
    assert "depth_from_md" in f
    assert "depth_to_md" in f


# 8. Drilling parameter retrieval
def test_drilling_parameter_retrieval():
    response = client.get(f"/api/wells/{SAMPLE_WELL_ID}/drilling")
    assert response.status_code == 200
    data = response.json()
    assert data["well_id"] == SAMPLE_WELL_ID
    assert "records" in data
    assert len(data["records"]) > 0
    r = data["records"][0]
    assert "drilling_record_id" in r
    assert "depth_md" in r
    assert "rop_m_per_hr" in r
    assert "wob_klbf" in r
    assert "mud_weight_ppg" in r


# 9. Mud logging filtering
def test_mud_logging_filtering():
    response = client.get(f"/api/wells/{SAMPLE_WELL_ID}/mud-logging?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["well_id"] == SAMPLE_WELL_ID
    assert "records" in data
    assert len(data["records"]) <= 10
    if data["records"]:
        m = data["records"][0]
        assert "depth_m" in m
        assert "mud_weight_ppg" in m
        assert "gas_total_units" in m


# 10. Offset event correlation
def test_offset_event_correlation():
    response = client.get(f"/api/wells/{SAMPLE_WELL_ID}/offset-intelligence?radius_km=30&depth_window_m=300")
    assert response.status_code == 200
    data = response.json()
    assert "current_well" in data
    assert "current_depth" in data
    assert "nearby_wells" in data
    assert "historical_events" in data
    assert "formation_matches" in data
    assert "depth_matches" in data
    assert "event_matches" in data
    assert "supporting_wells" in data

    if data["historical_events"]:
        ev = data["historical_events"][0]
        assert "event_id" in ev
        assert "well_id" in ev
        assert "depth_md" in ev
        assert "depth_difference_m" in ev
        assert ev["source_dataset"] == "nwis_historical_drilling_events_15108.csv"


# 11. Risk retrieval
def test_risk_retrieval():
    response = client.get(f"/api/wells/{SAMPLE_WELL_ID}/risks")
    assert response.status_code == 200
    data = response.json()
    assert data["well_id"] == SAMPLE_WELL_ID
    assert "disclaimer" in data
    assert "PROTOTYPE" in data["disclaimer"]
    assert "recommendations" in data
    if data["recommendations"]:
        r = data["recommendations"][0]
        assert "predicted_event" in r
        assert "risk_score" in r
        assert "risk_level" in r
        assert "recommended_action" in r


# 12. API error handling
def test_api_error_handling():
    # 404 for non-existent well in nearby
    resp1 = client.get(f"/api/wells/{INVALID_WELL_ID}/nearby")
    assert resp1.status_code == 404

    # 404 for non-existent well in offset-intelligence
    resp2 = client.get(f"/api/wells/{INVALID_WELL_ID}/offset-intelligence")
    assert resp2.status_code == 404

    # 422 for invalid query parameters (e.g. radius_km < 0.1)
    resp3 = client.get(f"/api/wells/{SAMPLE_WELL_ID}/nearby?radius_km=-5")
    assert resp3.status_code == 422


# 13. Dashboard stats
def test_dashboard_stats():
    response = client.get("/api/dashboard/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_wells"] >= 15108
    assert data["wells_with_drilling_data"] > 0
    assert data["wells_with_historical_events"] > 0
    assert data["wells_with_documents"] > 0
    assert "basin_distribution" in data
    assert "recent_historical_events" in data
