import os
import requests

BASE_URL = "http://127.0.0.1:8000"

def test_workflow():
    print("==================================================")
    print("NWIS WCR PDF -> NEW WELL EXTRACTION -> DATABASE -> MAP INTEGRATION TEST")
    print("==================================================")

    # 0. Initial Well Count from map-markers
    resp0 = requests.get(f"{BASE_URL}/api/wells/map-markers?include_new=true")
    assert resp0.status_code == 200, f"Failed to get markers: {resp0.text}"
    initial_count = resp0.json()["count"]
    print(f"[STEP 0] Baseline Well Count: {initial_count}")

    # 1. Anti-hallucination test with wcr_no_coords_demo.pdf
    print("\n[STEP 1] Testing Anti-Hallucination on WCR without coordinates...")
    with open("wcr_no_coords_demo.pdf", "rb") as f:
        files = {"file": ("wcr_no_coords_demo.pdf", f, "application/pdf")}
        r1 = requests.post(f"{BASE_URL}/api/wcr/upload", files=files, data={"uploaded_by": "Test Engineer"})
    assert r1.status_code == 200, f"Upload failed: {r1.text}"
    data1 = r1.json()
    coords1 = data1["coordinates"]
    print(f" -> Location Status: {coords1['location_status']}")
    print(f" -> Coordinates: Lat={coords1['latitude']}, Lon={coords1['longitude']}")
    assert coords1["location_status"] == "INSUFFICIENT_EVIDENCE"
    assert coords1["latitude"] is None
    assert coords1["longitude"] is None
    print(" [PASSED] Zero-hallucination verified: missing coordinates were NOT invented.")

    # 2. Upload Real WCR with coordinates: real_wcr_nhk_542.pdf
    print("\n[STEP 2] Uploading realistic WCR PDF: real_wcr_nhk_542.pdf...")
    with open("real_wcr_nhk_542.pdf", "rb") as f:
        files = {"file": ("real_wcr_nhk_542.pdf", f, "application/pdf")}
        r2 = requests.post(f"{BASE_URL}/api/wcr/upload", files=files, data={"uploaded_by": "Drilling Engineer"})
    assert r2.status_code == 200, f"Upload failed: {r2.text}"
    data2 = r2.json()
    doc_id = data2["document_id"]
    coords2 = data2["coordinates"]
    meta2 = data2["extracted_metadata"]
    events2 = data2["drilling_events"]

    print(f" -> Document ID: {doc_id}")
    print(f" -> Extracted Well Name: {meta2['well_name']}")
    print(f" -> Extracted Operator: {meta2['operator']}")
    print(f" -> Extracted Field: {meta2['field']}")
    print(f" -> Extracted Formation: {meta2['formation']}")
    print(f" -> Extracted Total Depth: {meta2['total_depth']} m")
    print(f" -> Normalized Latitude: {coords2['latitude']:.6f}")
    print(f" -> Normalized Longitude: {coords2['longitude']:.6f}")
    print(f" -> Coordinate Status: {coords2['location_status']}")
    print(f" -> Coordinate Source: {coords2['coordinate_source']}")
    print(f" -> Drilling Events Extracted: {len(events2)}")
    for ev in events2:
        print(f"     * [{ev['event_type']}] Depth: {ev['depth']}m - {ev['description'][:60]}...")

    assert coords2["location_status"] == "VALID"
    assert abs(coords2["latitude"] - 27.311833) < 0.001
    assert abs(coords2["longitude"] - 95.354111) < 0.001
    assert len(events2) >= 2

    # 3. Create Well in Database with PostGIS
    print(f"\n[STEP 3] Creating new canonical well in NWIS database from Document {doc_id}...")
    create_payload = {
        "well_name": meta2["well_name"],
        "latitude": coords2["latitude"],
        "longitude": coords2["longitude"],
        "coordinate_source": coords2["coordinate_source"],
        "operator": meta2["operator"],
        "field": meta2["field"],
        "basin": meta2["basin"],
        "total_depth": meta2["total_depth"],
        "formation": meta2["formation"],
        "spud_date": meta2["spud_date"],
        "completion_date": meta2["completion_date"],
        "force_confirm": True,
        "reviewer": "Senior Drilling Superintendent"
    }
    r3 = requests.post(f"{BASE_URL}/api/wcr/{doc_id}/create-well", json=create_payload)
    assert r3.status_code == 200, f"Well creation failed: {r3.text}"
    data3 = r3.json()
    new_well_id = data3["well_id"]
    new_total = data3["total_wells"]

    print(f" -> New Canonical Well ID: {new_well_id}")
    print(f" -> Map Action: {data3['map_action']}")
    print(f" -> Total Wells Reported: {new_total}")
    print(f" -> Events Linked: {data3['events_count']}")
    assert data3["success"] is True
    assert data3["map_action"] == "FOCUS_NEW_WELL"
    assert new_total == initial_count + 1

    # 4. Verify Map Markers API contains new well
    print(f"\n[STEP 4] Verifying map markers API includes new well {new_well_id}...")
    resp_map = requests.get(f"{BASE_URL}/api/wells/map-markers?include_new=true")
    assert resp_map.status_code == 200
    map_data = resp_map.json()
    assert map_data["count"] == initial_count + 1
    new_marker = next((m for m in map_data["markers"] if m["well_id"] == new_well_id), None)
    assert new_marker is not None, f"Marker {new_well_id} not found in map markers!"
    print(f" -> Marker Found: {new_marker['well_name']} ({new_marker['well_id']})")
    print(f" -> is_new_well: {new_marker['is_new_well']}")
    print(f" -> Coordinates: ({new_marker['latitude']}, {new_marker['longitude']})")
    print(f" -> Source Document: {new_marker['source_document']}")
    assert new_marker["is_new_well"] is True

    # 5. Verify Documents API for the new well
    print(f"\n[STEP 5] Verifying documents catalog for well {new_well_id}...")
    r_docs = requests.get(f"{BASE_URL}/api/wells/{new_well_id}/documents")
    assert r_docs.status_code == 200
    docs_data = r_docs.json()
    print(f" -> Linked Documents: {docs_data['count']}")
    assert any(d["document_id"] == doc_id for d in docs_data["documents"])

    print("\n==================================================")
    print("ALL VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print(f"Count successfully incremented from {initial_count} -> {initial_count + 1}")
    print("==================================================")

if __name__ == "__main__":
    test_workflow()
