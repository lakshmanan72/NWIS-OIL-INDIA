import requests
import json
import math
import sys

BASE_URL = "http://127.0.0.1:8000"

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2.0) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def test_well_radius(well_id: str, radius_km: float):
    url = f"{BASE_URL}/api/wells/{well_id}/nearby?radius_km={radius_km}&limit=100"
    resp = requests.get(url)
    assert resp.status_code == 200, f"API returned {resp.status_code}: {resp.text}"
    data = resp.json()
    
    # Contract checks (Section 5)
    assert "center" in data or "source_well" in data, "Missing center/source_well in response"
    assert "radius_km" in data, "Missing radius_km in response"
    assert "count" in data, "Missing count in response"
    
    wells = data.get("wells") or data.get("nearby_wells", [])
    count = data["count"]
    
    # Section 6: count must equal actual returned filtered wells
    assert count == len(wells), f"Count mismatch: reported {count}, actual list length {len(wells)}"
    
    # Source coordinates
    src_lat = data.get("center", {}).get("latitude") or data.get("source_well", {}).get("latitude")
    src_lon = data.get("center", {}).get("longitude") or data.get("source_well", {}).get("longitude")
    
    print(f"\n[TEST] Well: {well_id} (Lat: {src_lat}, Lon: {src_lon}) | Radius: {radius_km} km")
    print(f"       Found {count} nearby wells within {radius_km} km")
    
    max_d = 0.0
    min_d = 999999.0
    
    for w in wells:
        d = w["distance_km"]
        assert d <= radius_km, f"VIOLATION: Well {w['well_id']} has distance {d} km > {radius_km} km!"
        
        # Verify independent distance calculation (Section 9 & 10)
        actual_calc = haversine(src_lat, src_lon, w["latitude"], w["longitude"])
        calc_round = round(actual_calc, 2)
        diff = abs(calc_round - d)
        assert diff <= 0.05, f"Distance discrepancy for {w['well_id']}: API said {d}, true haversine is {calc_round}"
        
        if d > max_d:
            max_d = d
        if d < min_d:
            min_d = d

    if count > 0:
        print(f"       Min Dist: {min_d:.2f} km | Max Dist: {max_d:.2f} km (All <= {radius_km} km: PASS)")
    else:
        print("       (No offset wells found within this radius)")
        
    return count, max_d

def main():
    print("==================================================")
    print("RUNNING NEARBY WELL RADIUS STRICT VERIFICATION")
    print("==================================================")
    
    # Ready check
    ready = requests.get(f"{BASE_URL}/api/ready")
    print(f"Backend readiness: {ready.status_code}")
    
    # Test 1: WELL-01226 at 5 km
    c5, max5 = test_well_radius("WELL-01226", 5.0)
    assert max5 <= 5.0, f"Max dist {max5} > 5.0"
    
    # Test 2: WELL-01226 at 10 km
    c10, max10 = test_well_radius("WELL-01226", 10.0)
    assert max10 <= 10.0, f"Max dist {max10} > 10.0"
    assert c10 >= c5, "10km count must be >= 5km count"
    
    # Test 3: WELL-01226 at 25 km
    c25, max25 = test_well_radius("WELL-01226", 25.0)
    assert max25 <= 25.0, f"Max dist {max25} > 25.0"
    assert c25 >= c10, "25km count must be >= 10km count"
    
    # Test 4: Switching sequence 25 -> 10 -> 5 -> 50
    c50, max50 = test_well_radius("WELL-01226", 50.0)
    assert max50 <= 50.0
    c10_again, _ = test_well_radius("WELL-01226", 10.0)
    assert c10 == c10_again, "Results must be reproducible"
    
    # Test 5: Different well
    c_other, max_other = test_well_radius("WELL-000001", 10.0)
    assert max_other <= 10.0
    
    c_other2, max_other2 = test_well_radius("WELL-000050", 15.0)
    assert max_other2 <= 15.0
    
    print("\nALL RADIUS FILTERING AND CONTRACT TESTS PASSED PERFECTLY!")

if __name__ == "__main__":
    main()
