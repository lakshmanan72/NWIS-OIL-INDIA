import pytest
import math
from backend.app.services.spatial_service import spatial_service
from backend.app.repositories.csv_repository import haversine_distance

def test_nearby_wells_radius_strict_filtering():
    """
    Test 1, 2, 3: Verify strict distance_km <= radius_km constraint for various radii.
    """
    test_well_id = "WELL-01226"  # Aliased to WELL-012265
    
    for radius in [5.0, 10.0, 25.0, 50.0]:
        resp = spatial_service.get_nearby_wells(test_well_id, radius_km=radius, limit=100)
        
        # Verify API contract
        assert resp.radius_km == radius
        assert resp.count == len(resp.nearby_wells)
        assert resp.count == len(resp.wells)
        assert resp.center["well_id"] == test_well_id
        
        src_lat = resp.center["latitude"]
        src_lon = resp.center["longitude"]
        
        # Strict server-side condition (Section 4 & Section 18)
        for w in resp.nearby_wells:
            assert w.distance_km <= radius, f"Well {w.well_id} distance {w.distance_km} > {radius}!"
            
            # Verify live Haversine calculation against real coordinates (Section 9)
            true_d = round(haversine_distance(src_lat, src_lon, w.latitude, w.longitude), 2)
            assert abs(true_d - w.distance_km) <= 0.05, f"Discrepancy for {w.well_id}: API={w.distance_km}, True={true_d}"

def test_nearby_wells_count_monotonicity():
    """
    Test 4: Verify monotonic count progression when expanding radius.
    """
    test_well_id = "WELL-01226"
    resp_5 = spatial_service.get_nearby_wells(test_well_id, radius_km=5.0)
    resp_10 = spatial_service.get_nearby_wells(test_well_id, radius_km=10.0)
    resp_25 = spatial_service.get_nearby_wells(test_well_id, radius_km=25.0)
    
    assert resp_5.count <= resp_10.count <= resp_25.count
    # Specifically for WELL-012265, exactly 13 wells are within 10 km
    assert resp_10.count == 13
    assert max(w.distance_km for w in resp_10.nearby_wells) <= 10.0

def test_nearby_wells_canonical_well_000001():
    """
    Test 5: Verify behavior with other canonical wells.
    """
    resp = spatial_service.get_nearby_wells("WELL-000001", radius_km=10.0, limit=50)
    assert resp.count == len(resp.nearby_wells)
    for w in resp.nearby_wells:
        assert w.distance_km <= 10.0
