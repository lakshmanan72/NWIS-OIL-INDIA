# NWIS Phase 7: Production Data Platform Architecture
## PostgreSQL + PostGIS + Persistent Telemetry + RBAC + Audit Trail

> **CRITICAL OPERATIONAL ADVISORY & SAFETY GOVERNANCE**  
> **NWIS is strictly an ADVISORY DECISION-SUPPORT SYSTEM, NOT an autonomous drilling or rig-control system.**  
> Autonomous machine actuation and automated rig intervention are strictly prohibited. All real-time streaming telemetry, rolling anomaly detections, Phase 3.1 Model Risk Indicators, and live alerts are advisory notifications designed to augment situational awareness. All drilling parameter adjustments, mud treatment modifications, and operational interventions require formal licensed human engineer review and sign-off.

---

## 1. System Evolution & Repository Abstraction Map

Phase 7 upgrades the persistence tier of NWIS from prototype CSV/JSON files to a production-grade **PostgreSQL + PostGIS** platform without breaking or rewriting any upstream services, ML models, RAG copilot, or real-time pipelines.

```
                      ┌─────────────────────────────────┐
                      │    NWIS CONFIGURATION (.env)    │
                      │ DATA_BACKEND = csv | postgres   │
                      └────────────────┬────────────────┘
                                       │
                ┌──────────────────────┴──────────────────────┐
                ▼                                             ▼
  ┌───────────────────────────┐                 ┌───────────────────────────┐
  │      CSV REPOSITORY       │                 │    POSTGRES REPOSITORY    │
  │  (Pandas / In-Memory /    │                 │    (SQLAlchemy 2.x /      │
  │   JSON Audit & Alerts)    │                 │   PostGIS ST_DWithin /    │
  │                           │                 │  pgvector / Timescale)    │
  └─────────────┬─────────────┘                 └─────────────┬─────────────┘
                │                                             │
                └──────────────────────┬──────────────────────┘
                                       │
                                       ▼
                     ┌───────────────────────────────────┐
                     │   COMMON REPOSITORY INTERFACES    │
                     │  - IWellRepository                │
                     │  - IGeologyRepository             │
                     │  - IFormationRepository           │
                     │  - IDrillingRepository            │
                     │  - IMudLoggingRepository          │
                     │  - IEventRepository               │
                     │  - ICompletionRepository          │
                     │  - IDocumentRepository            │
                     │  - ISpatialRepository             │
                     │  - IRiskRepository                │
                     │  - ITelemetryRepository           │
                     │  - IAlertRepository               │
                     │  - IAuditRepository               │
                     └─────────────────┬─────────────────┘
                                       │
                                       ▼
                     ┌───────────────────────────────────┐
                     │           NWIS SERVICES           │
                     │  - WellService                    │
                     │  - SpatialService                 │
                     │  - GeologyService                 │
                     │  - MudLoggingService              │
                     │  - DocumentService                │
                     │  - RealtimeDrillingService        │
                     │  - AlertEngine                    │
                     │  - ContextBuilder / RAG           │
                     └─────────────────┬─────────────────┘
                                       │
       ┌───────────────────────────────┼───────────────────────────────┐
       ▼                               ▼                               ▼
┌──────────────┐               ┌──────────────┐                ┌──────────────┐
│  PHASE 3.1   │               │   PHASE 5    │                │   PHASE 6    │
│  ML MODELS   │               │   SEMANTIC   │                │  REAL-TIME   │
│ (CatBoost /  │               │ RAG COPILOT  │                │ eRTMAC LIVE  │
│  RF / XGB)   │               │ (EVID-XXX)   │                │ (LIVE-XXX)   │
└──────┬───────┘               └──────┬───────┘                └──────┬───────┘
       └───────────────────────────────┼───────────────────────────────┘
                                       │
                                       ▼
                     ┌───────────────────────────────────┐
                     │       ENGINEERING INTELLIGENCE    │
                     │     & ADVISORY DECISION SUPPORT   │
                     └─────────────────┬─────────────────┘
                                       │
                                       ▼
                     ┌───────────────────────────────────┐
                     │     ENGINEER OPERATIONS CONSOLE   │
                     │   (React 18 / Vite / Leaflet)     │
                     │   - GIS Map & Spatial Search      │
                     │   - Well Intelligence Cockpit     │
                     │   - Document Approval Gateway     │
                     │   - Engineering Copilot           │
                     │   - Live Telemetry Console        │
                     │   - RBAC & Audit Trail            │
                     └───────────────────────────────────┘
```

---

## 2. Core Pillars & Design Decisions

### A. Dual Repository Architecture & Zero Downtime Fallback
- `DATA_BACKEND=csv` (Default): Loads verified baseline CSV files and JSON files (`data/raw/*.csv`, `data/documents/*.json`). Ensures zero-configuration operation for development, continuous integration, and edge scenarios without active database engines.
- `DATA_BACKEND=postgres`: Connects to PostgreSQL via SQLAlchemy 2.0. Leverages native PostGIS spatial operators, relational indexing, transaction guarantees, and server-side filtering.
- **Strict Interface Compliance**: Every service interacts only with repository interfaces (`IWellRepository`, `ISpatialRepository`, etc.). Swapping `DATA_BACKEND` requires zero modifications to upstream controllers or frontend API contracts.

### B. Canonical Well & Dynamic WCR Safety
- Canonical wells (`WELL-000001` through `WELL-015108`) remain immutable baseline records.
- Newly discovered wells from approved WCR documents (`WELL-015109+`) must traverse the mandatory Phase 5.1 approval gate (`REVIEW_REQUIRED` $\rightarrow$ Engineer Sign-off $\rightarrow$ Canonical Registration).
- In Postgres mode, approved new wells are committed with `is_new_well = True` and indexed in PostGIS. In CSV mode, they are cached in `data/documents/new_canonical_wells.json`.

### C. PostGIS Spatial Intelligence
- Wells store geographic location in `geom GEOGRAPHY(Point, 4326)`.
- A spatial GiST index (`idx_wells_geom`) accelerates proximity queries:
  - Radius queries: `ST_DWithin(geom, ST_SetSRID(ST_Point(lon, lat), 4326)::geography, radius_meters)`
  - Exact spherical distance: `ST_Distance(geom, ST_SetSRID(ST_Point(lon, lat), 4326)::geography) / 1000.0`
  - Nearest $K$ offset wells: `ORDER BY geom <-> ST_SetSRID(ST_Point(lon, lat), 4326)::geography LIMIT K`
- Replaces expensive Python-side Haversine loops when PostgreSQL is active while keeping the precomputed spatial relationship CSV as instant cache/fallback.

### D. Server-Side Mud Logging & Daily Parameters
- High-volume datasets (`nwis_mud_logging_15108_wells.csv` is 133MB; daily parameters are 2MB) are never loaded entirely into application memory.
- Tables are indexed by `(well_id, depth_md)` and `(well_id, recorded_at)` with server-side pagination, depth windowing (`depth_from` to `depth_to`), and limit bounds.

### E. Telemetry & Alert Persistence
- **Telemetry Records (`telemetry_records`)**: Indexed on `(well_id, timestamp DESC)` and `(well_id, depth_md)`. Asynchronous / non-blocking ingestion guarantees that telemetry buffering never stalls the live streaming loop.
- **Alerts Table (`alerts`)**: Enforces state machine lifecycle (`DETECTED` $\rightarrow$ `EVALUATED` $\rightarrow$ `ACTIVE` $\rightarrow$ `ACKNOWLEDGED` $\rightarrow$ `CLOSED`) with depth-window deduplication ($5.0\text{ m}$) and cooldown suppression ($60.0\text{ s}$).

### F. Security: Role-Based Access Control (RBAC) & Audit Trail
- **Roles**:
  - `ADMIN`: Full system access, user management, configuration, audit review.
  - `DRILLING_ENGINEER`: Live operations, alert acknowledge/close, document upload & review, engineering copilot.
  - `GEOLOGIST`: Well stratigraphy, formation logs, WCR view, spatial queries, copilot.
  - `VIEWER`: Read-only map, dashboard, and well intelligence. Prohibited from uploading, approving, acknowledging, or altering data.
- **Authentication**: JWT tokens with role claims, secure password hashing (PBKDF2/bcrypt via passlib), token expiry, and protected FastAPI dependencies.
- **Audit Logs (`audit_logs`)**: Append-only audit record capturing every sensitive engineering action: WCR approval/rejection, alert acknowledgement/closure, configuration update, and user access.

---

## 3. Database Schema Overview

| Table Name | Primary Purpose | Key Indexes & Constraints |
| :--- | :--- | :--- |
| `wells` | Canonical & dynamic wells | `well_id` (UNIQUE), `geom` (GIST), `operator`, `field`, `basin` |
| `well_geology` | Stratigraphy & lithological descriptions | `(well_id, depth_from, depth_to)`, `formation_name` |
| `well_formations` | Geological formation markers & tops | `(well_id, top_depth_md)`, `formation_name` |
| `historical_events` | Historical drilling incidents & NPT | `(well_id, depth_md)`, `event_type`, `severity` |
| `daily_drilling_parameters` | Daily drilling engineering logs | `(well_id, depth_md)`, `recorded_date` |
| `mud_logging` | High-frequency chromatograph & cuttings | `(well_id, depth_md)`, `(well_id, recorded_at)` |
| `well_completion_wcr` | 54-field WCR technical completion data | `well_id`, `document_id`, `approval_status` |
| `documents` | Ingested PDF document registry | `document_id` (UNIQUE), `sha256`, `approval_status` |
| `document_chunks` | RAG vectorized semantic chunks | `chunk_id` (UNIQUE), `(document_id, page)`, `approval_status` |
| `telemetry_records` | Real-time streaming parameters | `(well_id, timestamp DESC)`, `(well_id, depth_md)` |
| `well_live_state` | Authoritative latest state for recovery | `well_id` (UNIQUE), `connection_status`, `updated_at` |
| `alerts` | Real-time operational alerts & lifecycle | `alert_id` (UNIQUE), `(well_id, status)`, `depth_md`, `severity` |
| `users` | User credentials & assigned roles | `username` (UNIQUE), `email` (UNIQUE), `role` |
| `audit_logs` | Append-only security & operational audit | `timestamp DESC`, `well_id`, `user_id`, `action` |

---

## 4. Migration & Fallback Execution Flow

1. **Extraction**: `scripts/migrate_csv_to_postgres.py` reads raw CSVs from `data/raw/` in streaming chunks using Pandas / Python CSV readers.
2. **Transform**: Validates numeric types, dates, coordinates, and strips string padding. Preserves `NULL` for missing values; never fabricates dummy coordinates.
3. **Load**: Upserts into PostgreSQL inside scoped transactions with batch commits. Generates `data/postgres_migration_report.json`.
4. **Verification**: Compares row counts between CSV and Postgres, validates foreign keys, checks coordinate ranges, and ensures zero unexplained data loss.
5. **Runtime Switching**: When `DATA_BACKEND=postgres`, services query Postgres. If Postgres connection fails or is unconfigured, system logs a structured warning and safely falls back to `CSVRepository`.
