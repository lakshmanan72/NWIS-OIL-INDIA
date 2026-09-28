import csv
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.well_service import well_service

client = TestClient(app)


def get_independent_valid_csv_count(csv_file_path: Path) -> int:
    """
    Independently reads the CSV and calculates the expected count of valid coordinate rows.
    Does NOT hardcode any number.
    """
    valid_count = 0
    with open(csv_file_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lat_raw = row.get("latitude")
            lon_raw = row.get("longitude")
            if not lat_raw or not lon_raw:
                continue
            try:
                lat = float(str(lat_raw).strip())
                lon = float(str(lon_raw).strip())
            except (ValueError, TypeError):
                continue

            if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                valid_count += 1
    return valid_count


def test_api_status_and_provenance():
    response = client.get("/api/wells/map-markers")
    assert response.status_code == 200
    data = response.json()

    assert "count" in data
    assert "data_source" in data
    assert "dataset_name" in data
    assert "markers" in data

    assert data["data_source"] == "REAL_PUBLIC"
    assert data["dataset_name"] == "nwis_wells_columns.csv"
    assert isinstance(data["markers"], list)


def test_api_count_matches_independent_csv_count():
    csv_path = well_service.csv_path
    expected_valid_count = get_independent_valid_csv_count(csv_path)

    response = client.get("/api/wells/map-markers")
    assert response.status_code == 200
    data = response.json()

    # Compare API count == independently calculated count (no hardcoding!)
    assert data["count"] == expected_valid_count
    assert len(data["markers"]) == expected_valid_count


def test_coordinates_not_swapped():
    """
    Verify that latitude and longitude are NEVER swapped in API responses.
    Latitude for KK-DW-17-1 is ~13.525, longitude is ~72.5564.
    If swapped, lat would be 72.5564 which is completely wrong.
    """
    response = client.get("/api/wells/map-markers")
    assert response.status_code == 200
    data = response.json()

    well_lookup = {m["well_name"]: m for m in data["markers"]}

    assert "KK-DW-17-1" in well_lookup
    kk = well_lookup["KK-DW-17-1"]

    assert kk["latitude"] == pytest.approx(13.525, abs=1e-4)
    assert kk["longitude"] == pytest.approx(72.5564, abs=1e-4)
    # Explicit negative check against swapped order
    assert kk["latitude"] != pytest.approx(72.5564, abs=1.0)
    assert kk["longitude"] != pytest.approx(13.525, abs=1.0)


def test_exact_required_wells():
    """
    Verify the 3 exact test wells required by user specification:
    1. KK-DW-17-1: latitude = 13.525, longitude = 72.5564
    2. KK4C-A-1: latitude = 9.9635, longitude = 75.2054
    3. CH-1-1: latitude = 9.7339, longitude = 75.6544
    """
    response = client.get("/api/wells/map-markers")
    assert response.status_code == 200
    data = response.json()

    well_lookup = {m["well_name"]: m for m in data["markers"]}

    # 1. KK-DW-17-1
    assert "KK-DW-17-1" in well_lookup
    w1 = well_lookup["KK-DW-17-1"]
    assert w1["operator"] == "ONGC"
    assert w1["gid"] == 7766
    assert w1["latitude"] == pytest.approx(13.525, abs=1e-4)
    assert w1["longitude"] == pytest.approx(72.5564, abs=1e-4)

    # 2. KK4C-A-1
    assert "KK4C-A-1" in well_lookup
    w2 = well_lookup["KK4C-A-1"]
    assert w2["operator"] == "ONGC"
    assert w2["gid"] == 7773
    assert w2["latitude"] == pytest.approx(9.9635, abs=1e-4)
    assert w2["longitude"] == pytest.approx(75.2054, abs=1e-4)

    # 3. CH-1-1
    assert "CH-1-1" in well_lookup
    w3 = well_lookup["CH-1-1"]
    assert w3["operator"] == "ONGC"
    assert w3["gid"] == 2963
    assert w3["latitude"] == pytest.approx(9.7339, abs=1e-4)
    assert w3["longitude"] == pytest.approx(75.6544, abs=1e-4)


def test_all_markers_within_coordinate_bounds():
    response = client.get("/api/wells/map-markers")
    assert response.status_code == 200
    data = response.json()

    for m in data["markers"]:
        assert -90.0 <= m["latitude"] <= 90.0
        assert -180.0 <= m["longitude"] <= 180.0
        assert m["id"] != ""
        assert m["well_name"] != ""
