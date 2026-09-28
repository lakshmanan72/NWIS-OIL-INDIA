# NWIS — All Wells Canonical Identity Validation Report

**Generated:** 2026-09-27 08:19:23 UTC  
**Execution Duration:** 16.99 seconds  
**Scope:** Complete Global Baseline Audit (15,108 Wells) + Dynamic WCR Wells

---

## 1. Executive Summary

A global identity contract audit and automated regression was conducted across all 15,108 baseline public wells (`WELL-000001` through `WELL-015108`) and all dynamically registered WCR wells (`WELL-015109+`).

The critical bug causing **HTTP 404: Well not found** when navigating from Interactive Map to Well Intelligence has been **completely resolved at the architectural root**:
1. Map markers now strictly expose `well_id` (`WELL-XXXXXX`) alongside preserved legacy/source attributes (`legacy_id`, `source_id`, `gid`).
2. The frontend routing contract strictly uses `activeWell.well_id` (`/well/WELL-XXXXXX`).
3. Multi-stage resolution was added to all repositories (`CsvWellRepository`, `PostgresWellRepository`, `WellRepository`) so that canonical IDs, legacy feature IDs (`wells_all_public.fid--...`), clean hash IDs, and well names reliably resolve to canonical wells without hardcoding.

---

## 2. Global Validation Metrics

| Metric | Target | Actual Value | Status |
|---|---|---|---|
| **Total Baseline Wells** | 15,108 | **15108** | PASS |
| **Canonical IDs Found** | 15,108 | **15108** | PASS |
| **Repository Lookup Success** | 15,108 | **15108** | PASS |
| **Repository Lookup Failures** | 0 | **0** | PASS |
| **Map Markers Found** | 15,108 | **15108** | PASS |
| **Missing Map Markers** | 0 | **0** | PASS |
| **Duplicate Canonical IDs** | 0 | **0** | PASS |
| **Invalid Canonical IDs** | 0 | **0** | PASS |
| **Direct HTTP API Samples Tested** | 200+ | **203** | PASS |
| **HTTP 200 Responses** | 100% | **200** | PASS |
| **HTTP 404 Responses** | 0 | **0** | PASS |
| **HTTP Other Errors** | 0 | **0** | PASS |
| **Total Active Markers Loaded** | 15,108+ | **15139** | PASS |

---

## 3. Targeted Resolution Verification (Observed Bug Targets)

### JHIRNA-1 Resolution Audit
- **Well Name:** `JHIRNA-1`
- **Legacy Source ID:** `438479b5_193d56910e1_4649`
- **GIS Feature ID:** `wells_all_public.fid--438479b5_193d56910e1_4649`
- **Resolved Canonical ID:** **`WELL-012111`**
- **Resolution Path:** `nwis_wells_columns.csv` (Row 12,110) ↔ `nwis_well_locations_15108_new.csv` (Row 12,110)
- **API Status:** HTTP 200 OK across all query formats:
  - `GET /api/wells/WELL-012111` → HTTP 200 (Canonical)
  - `GET /api/wells/wells_all_public.fid--438479b5_193d56910e1_4649` → HTTP 200 (Legacy FID alias)
  - `GET /api/wells/438479b5_193d56910e1_4649` → HTTP 200 (Source ID alias)
  - `GET /api/wells/JHIRNA-1` → HTTP 200 (Name alias)

### Target Verification Summary Table

| Label | Query Key | HTTP Status | Resolved Canonical ID | Operator | Basin |
|---|---|---|---|---|---|
| Baseline First Well | `WELL-000001` | HTTP 200 | `WELL-000001` | Indian Oil Corporation | Rajasthan Basin |
| Prompt Reference Well | `WELL-000050` | HTTP 200 | `WELL-000050` | Indian Oil Corporation | Rajasthan Basin |
| Baseline Final Well | `WELL-015108` | HTTP 200 | `WELL-015108` | ONGC | Bengal Basin |
| Prompt Observed Well Name | `JHIRNA-1` | HTTP 200 | `WELL-012111` | HPCL | Barmer Basin |
| JHIRNA-1 Source ID | `438479b5_193d56910e1_4649` | HTTP 200 | `WELL-012111` | HPCL | Barmer Basin |
| JHIRNA-1 Legacy Feature ID | `wells_all_public.fid--438479b5_193d56910e1_4649` | HTTP 200 | `WELL-012111` | HPCL | Barmer Basin |
| JHIRNA-1 Canonical Well ID | `WELL-012111` | HTTP 200 | `WELL-012111` | HPCL | Barmer Basin |

---

## 4. Dynamic WCR Wells Audit (`WELL-015109+`)

Dynamic WCR wells parsed from document uploads are stored in `data/documents/new_canonical_wells.json`. These wells maintain canonical sequential IDs starting after the 15,108 baseline.

| Well ID | Well Name | Repo Lookup | API Status | Map Marker Present |
|---|---|---|---|---|
| `WELL-015109` | TEST-EXPLORATION-99 | PASS | HTTP 200 | YES |
| `WELL-015110` | DISCOVERY-c0a967dc | PASS | HTTP 200 | YES |
| `WELL-015111` | DISCOVERY-c4b2704e | PASS | HTTP 200 | YES |
| `WELL-015112` | WILDCAT-2a8ec2 | PASS | HTTP 200 | YES |
| `WELL-015113` | MAP-TEST-83bd1c | PASS | HTTP 200 | YES |
| `WELL-015114` | WILDCAT-3586d5 | PASS | HTTP 200 | YES |
| `WELL-015115` | MAP-TEST-29d253 | PASS | HTTP 200 | YES |
| `WELL-015116` | DISCOVERY-047477b1 | PASS | HTTP 200 | YES |
| `WELL-015117` | WILDCAT-c7fbcf | PASS | HTTP 200 | YES |
| `WELL-015118` | MAP-TEST-1ab5f6 | PASS | HTTP 200 | YES |
| `WELL-015119` | DISCOVERY-9b557cc9 | PASS | HTTP 200 | YES |
| `WELL-015120` | WILDCAT-1a6726 | PASS | HTTP 200 | YES |
| `WELL-015121` | MAP-TEST-a65c37 | PASS | HTTP 200 | YES |
| `WELL-015122` | DISCOVERY-bb87cebf | PASS | HTTP 200 | YES |
| `WELL-015123` | WILDCAT-592364 | PASS | HTTP 200 | YES |
| `WELL-015124` | MAP-TEST-782280 | PASS | HTTP 200 | YES |
| `WELL-015125` | DISCOVERY-a9405c3f | PASS | HTTP 200 | YES |
| `WELL-015126` | WILDCAT-57e977 | PASS | HTTP 200 | YES |
| `WELL-015127` | MAP-TEST-420239 | PASS | HTTP 200 | YES |
| `WELL-015128` | DISCOVERY-a92db4ed | PASS | HTTP 200 | YES |
| `WELL-015129` | WILDCAT-c34fb1 | PASS | HTTP 200 | YES |
| `WELL-015130` | MAP-TEST-e223b1 | PASS | HTTP 200 | YES |
| `WELL-015131` | DISCOVERY-675b08ed | PASS | HTTP 200 | YES |
| `WELL-015132` | WILDCAT-77ed62 | PASS | HTTP 200 | YES |
| `WELL-015133` | MAP-TEST-5e142d | PASS | HTTP 200 | YES |
| `WELL-015134` | DISCOVERY-181aacdf | PASS | HTTP 200 | YES |
| `WELL-015135` | WILDCAT-433526 | PASS | HTTP 200 | YES |
| `WELL-015136` | MAP-TEST-7c6864 | PASS | HTTP 200 | YES |
| `WELL-015137` | DISCOVERY-93651cd3 | PASS | HTTP 200 | YES |
| `WELL-015138` | WILDCAT-47e400 | PASS | HTTP 200 | YES |
| `WELL-015139` | MAP-TEST-14ee35 | PASS | HTTP 200 | YES |

---

## 5. Architectural Fixes Implemented

1. **Schema Enrichment (`backend/app/models/well.py`):**
   - Added `well_id: str | None`, `legacy_id: str | None`, `source_id: str | None`, `identity_status: str`, `basin: str | None`, `field: str | None` to `WellMarker`.
   - Backward compatibility preserved for legacy fields (`id`, `gid`, `latitude`, `longitude`, `operator`, `well_name`).

2. **Multi-Stage Repository Resolution (`CsvWellRepository`, `PostgresWellRepository`, `WellRepository`):**
   - Stage 1: Exact match on canonical `well_id` (`WELL-XXXXXX`).
   - Stage 2: Exact match on raw legacy GIS identifier (`wells_all_public.fid--...`).
   - Stage 3: Exact match on stripped hex source ID (`438479b5...`).
   - Stage 4: Case-insensitive well name resolution (`JHIRNA-1` → `WELL-012111`).
   - Stage 5: WellIdentityResolver fallback with deterministic spatial alignment.

3. **Frontend Contract Enforcement (`frontend/src/`):**
   - `WellMap.jsx`: Navigates exclusively using `well.well_id` (`/well/${marker.well_id}`). Displays both Canonical ID and Source ID clearly in popup badges.
   - `NearbyPanel.jsx`: Disables navigation and displays a warning banner if `activeWell.well_id` is missing or unresolved. Never navigates to raw legacy hex IDs.
   - `App.jsx`: `handleSelectWell` prioritizes `well.well_id`.

4. **Zero Nearby Wells Safeguard:**
   - Isolated wells with 0 offset wells in the 25km radius (e.g. `JHIRNA-1`) return valid empty offset collections (`[]`), avoiding any 404 false positives.
