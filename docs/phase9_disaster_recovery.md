# NWIS Phase 9 — Disaster Recovery (DR) & Business Continuity Plan

## 1. Executive Summary & Advisory Framing
The **Nearby Wells Intelligence System (NWIS)** provides advisory subsurface offset intelligence and drilling risk visualization. In the event of a catastrophic infrastructure outage (hardware failure, host corruption, or data center disruption), this Disaster Recovery Plan outlines recovery workflows.

> [!NOTE]
> **Advisory Safety Guarantee:**  
> NWIS is an advisory decision-support system. In the event of complete NWIS downtime, **active drilling rigs continue safe manual or rig-floor autonomous operations**. NWIS does not close blowout preventers (BOP), throttle mud pumps, or control drawworks.

---

## 2. Recovery Objectives & Assumptions

### Operational Assumptions:
- **Baseline Data:** Canonical public wells (15,108 wells) and historical events are preserved in version-controlled CSV repositories (`data/`).
- **Cold Standby Capability:** NWIS supports instant zero-database fallback (`DATA_BACKEND=csv`) allowing immediate platform access even if PostgreSQL/PostGIS is unavailable.
- **Hardware Targets:** Any standard x86_64 or ARM64 Linux/Windows host with >= 4 CPU cores, 8 GB RAM, and Docker or Python 3.11+.

### Target Recovery Metrics (Assumed Baseline):
| Metric | Assumed Target | Notes |
|---|---|---|
| **Recovery Point Objective (RPO)** | **1 Hour** (Relational/Spatial Database) | Assumes hourly scheduled snapshots or daily full backups + WAL retention. |
| **RPO (Baseline Public Wells)** | **0 Minutes (RPO = 0)** | Static baseline canonical records reside in immutable CSV files. |
| **RPO (Real-time Telemetry)** | **Continuous buffer loss** | Real-time streams during downtime are replayed via WITSML/WITS0 polling catch-up upon reconnect. |
| **Recovery Time Objective (RTO)** | **< 10 Minutes** (CSV Fallback) | Simply restart backend with `DATA_BACKEND=csv`. |
| **RTO (Full PostgreSQL/PostGIS)** | **< 45 Minutes** | Container launch + `restore_postgres.ps1` application. |

---

## 3. Component Recovery Runbooks

### A. Database Recovery (PostgreSQL + PostGIS)
1. Provision clean PostgreSQL 16 container with PostGIS 3.4:
   ```bash
   docker compose up -d postgres-postgis
   ```
2. Apply latest verified backup SQL:
   ```powershell
   .\scripts\restore_postgres.ps1 -BackupFile "database/backups/nwis_backup_LATEST.sql" -UseDocker -Force
   ```
3. Validate connection and PostGIS active state:
   ```bash
   curl http://127.0.0.1:8000/api/ready
   ```

### B. Application Service Recovery (Backend & Frontend)
1. Pull clean repository code or Docker images.
2. Ensure environment configuration template is populated:
   ```powershell
   Copy-Item .env.example .env
   # Populate production secrets
   ```
3. Launch services:
   ```powershell
   # Local native execution
   .\scripts\start_nwis.ps1

   # Or containerized deployment
   docker compose up -d
   ```

### C. Uploaded Technical Document Recovery
- Uploaded technical PDF documents reside in `data/uploads/` (or persistent volume `nwis_uploads`).
- **Disaster Workflow:**
  1. Restore PDF storage folder from daily file-level backup or S3 snapshot.
  2. Database restore brings back the document registry, extraction tables, and review status.
  3. Verify document accessibility via `GET /api/documents`.

### D. Vector Store & Semantic Index Recovery
- NWIS supports local embedding generation (Sentence-Transformers / TF-IDF) and PGVector.
- **Reindexing Procedure:**
  1. If vector storage is lost, invoke the re-embedding pipeline on approved documents:
     ```python
     python -c "from backend.document_ai.rag_service import rag_service; rag_service.rebuild_index()"
     ```
  2. Grounded RAG query endpoint `/api/intelligence/query` resumes operation immediately.

### E. Real-Time Telemetry & Alert State Recovery
1. The real-time telemetry pipeline reinitializes in a clean state with zero false alarms.
2. In-memory circular buffer begins accumulating fresh readings as upstream adapters reconnect.
3. If upstream vendor supports WITSML historical polling, adapter requests past telemetry window (`time_start`).

---

## 4. Disaster Recovery Drill Schedule
To ensure operational readiness for SIH Grand Finale and field deployment:
1. **Quarterly Simulated Database Outage:** Validate CSV fallback behavior under load.
2. **Semi-Annual Full Cold Restore:** Execute `restore_postgres.ps1` from cold storage onto an isolated test runner.
3. **Integrity Validation:** Audit SHA-256 checksums across all backup artifacts.
