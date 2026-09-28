# NWIS Phase 9 — PostgreSQL / PostGIS Backup & Disaster Recovery Guide

## 1. Overview
The **Nearby Wells Intelligence System (NWIS)** relies on a PostgreSQL 16 + PostGIS 3.4 database when running in `DATA_BACKEND=postgres` mode. This runbook establishes verified procedures for automated backups, integrity checks, and controlled point-in-time restores.

> [!WARNING]
> **Safety Guard:** Database restore operations are **destructive** to existing records in the target database. NWIS utilities strictly enforce explicit interactive confirmation (`-Force` switch required for automated scripts) and mandate pre-restore SHA-256 integrity validation.

---

## 2. Backup Procedure

Backups are executed via [`scripts/backup_postgres.ps1`](file:///d:/Internship/sih%20well/scripts/backup_postgres.ps1).

### Execution Command:
```powershell
# Native PostgreSQL client backup
.\scripts\backup_postgres.ps1 -OutputDir "database/backups" -Database "nwis" -User "nwis_admin"

# Docker container backup
.\scripts\backup_postgres.ps1 -UseDocker -OutputDir "database/backups"
```

### Artifacts Generated:
- SQL Dump: `database/backups/nwis_backup_YYYYMMDD_HHMMSS.sql`
- Checksum: `database/backups/nwis_backup_YYYYMMDD_HHMMSS.sql.sha256`

### Backup Scope:
1. **Users & RBAC:** Users, credentials, roles, and permissions.
2. **Canonical Wells & Offset Spatial Data:** All well headers, coordinates, and PostGIS `GEOGRAPHY(Point, 4326)` geometries.
3. **Subsurface Data:** Geological formations, lithology intervals, daily drilling parameters, and mud logging records.
4. **Historical Drilling Events:** Loss circulation, kicks, stuck pipe, and wellbore stability incidents.
5. **Real-Time Telemetry & Alerts:** Historical sensor streams and drilling alert audit records.
6. **Document AI Registry:** Ingested technical documents, extracted entities, and verified events.
7. **Immutable Audit Logs:** Security actions, approvals, and system state transitions.

---

## 3. Verification Procedure

Every backup automatically generates an accompanying `.sha256` checksum file.

To manually verify backup integrity:
```powershell
$backupFile = "database/backups/nwis_backup_20260927_120000.sql"
$expectedHash = (Get-Content "$backupFile.sha256").Trim().Split(" ")[0]
$actualHash = (Get-FileHash -Path $backupFile -Algorithm SHA256).Hash

if ($expectedHash -eq $actualHash) {
    Write-Host "[OK] Backup integrity verified." -ForegroundColor Green
} else {
    Write-Host "[ALERT] Backup checksum mismatch!" -ForegroundColor Red
}
```

---

## 4. Restore Procedure

Restores are executed via [`scripts/restore_postgres.ps1`](file:///d:/Internship/sih%20well/scripts/restore_postgres.ps1).

### Interactive Safety Gate:
By default, the script prompts for user confirmation:
```text
WARNING: A database restore will DROP and RECREATE tables in 'nwis'.
All existing uncommitted changes in 'nwis' will be overwritten.
Are you absolutely sure you want to proceed with this restore? Type 'RESTORE' to confirm:
```

### Non-Interactive (Automation / CI):
```powershell
# Native restore
.\scripts\restore_postgres.ps1 -BackupFile "database/backups/nwis_backup_20260927_120000.sql" -Force

# Docker-managed restore
.\scripts\restore_postgres.ps1 -BackupFile "database/backups/nwis_backup_20260927_120000.sql" -UseDocker -Force
```

### Post-Restore Verification:
1. Validate API readiness:
   ```bash
   curl -s http://127.0.0.1:8000/api/ready
   ```
   Verify `database_connected: true` and `postgis: true`.
2. Inspect canonical well count:
   ```bash
   curl -s http://127.0.0.1:8000/api/wells | jq .total
   ```
   Verify expected count (~15,108+ wells).

---

## 5. Recovery Assumptions & Limitations

| Dimension | Specification |
|---|---|
| **Recovery Point Objective (RPO)** | **1 Hour** (with scheduled hourly pg_dump or WAL archiving). In CSV fallback mode, canonical records are versioned in git. |
| **Recovery Time Objective (RTO)** | **< 15 Minutes** for full PostgreSQL rebuild from backup SQL. **< 1 Minute** when toggling to CSV fallback mode (`DATA_BACKEND=csv`). |
| **Storage Architecture** | Backups must be stored on resilient, off-instance block storage or encrypted cloud object store (e.g. AWS S3 with Object Lock or Azure Blob Storage). |
| **File Uploads Storage** | Physical uploaded PDFs (`data/uploads/`) are backed up separately as file assets; the database stores document metadata, extractions, and SHA-256 hashes. |
| **Advisory Boundary** | During database recovery, rig operations are unaffected as NWIS does not perform active rig control. |
