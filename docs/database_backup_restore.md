# NWIS Database Backup, Restore & Disaster Recovery Guide

This document describes the operational procedures for backing up, restoring, and managing schema migrations for the NWIS PostgreSQL + PostGIS database.

---

## 1. Database Backup Procedures

### A. Full Logical Backup (`pg_dump`)
To create a complete compressed backup of the canonical database including PostGIS spatial geometries, schema definitions, and table data:

```bash
# Set environment variables
export PGPASSWORD="your_secure_password"
HOST="localhost"
PORT="5432"
USER="nwis_admin"
DBNAME="nwis"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/nwis"

# Ensure directory exists
mkdir -p "$BACKUP_DIR"

# Execute custom-format compressed backup (-Fc enables parallel restore and selective extraction)
pg_dump \
  -h "$HOST" \
  -p "$PORT" \
  -U "$USER" \
  -F c \
  -b \
  -v \
  -f "$BACKUP_DIR/nwis_backup_${DATE}.dump" \
  "$DBNAME"
```

### B. Schema-Only Backup (Excluding Data)
Useful when verifying DDL versions or creating test environments:
```bash
pg_dump -h "$HOST" -p "$PORT" -U "$USER" -s -F p -f "$BACKUP_DIR/nwis_schema_${DATE}.sql" "$DBNAME"
```

### C. Data-Only Backup (Excluding DDL)
```bash
pg_dump -h "$HOST" -p "$PORT" -U "$USER" -a -F c -f "$BACKUP_DIR/nwis_data_${DATE}.dump" "$DBNAME"
```

---

## 2. Database Restore Procedures

### A. Full Restore to Fresh Database
```bash
# 1. Create target database and enable PostGIS
createdb -h "$HOST" -p "$PORT" -U "$USER" nwis_restored
psql -h "$HOST" -p "$PORT" -U "$USER" -d nwis_restored -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# 2. Restore from custom-format dump
pg_restore \
  -h "$HOST" \
  -p "$PORT" \
  -U "$USER" \
  -d nwis_restored \
  -v \
  --clean \
  --if-exists \
  "$BACKUP_DIR/nwis_backup_20260927_093000.dump"
```

### B. Restoring Individual Tables (e.g., Wells or Documents)
```bash
pg_restore \
  -h "$HOST" \
  -p "$PORT" \
  -U "$USER" \
  -d nwis \
  -t wells \
  -v \
  "$BACKUP_DIR/nwis_backup_20260927_093000.dump"
```

---

## 3. Migration Rollback Procedures (Alembic)

NWIS uses Alembic for forward and reverse schema evolution.

### A. Check Current Migration Revision
```bash
cd backend
python -m alembic current
```

### B. Roll Back to Specific Previous Revision
```bash
# Revert 1 migration step
python -m alembic downgrade -1

# Revert to specific revision hash
python -m alembic downgrade <revision_id>

# Revert all migrations back to base
python -m alembic downgrade base
```

---

## 4. Disaster Recovery & Availability Notice

- **Current Implementation**: Single-node PostgreSQL with PostGIS extension. High Availability (e.g. Patroni / pgpool-II / multi-region streaming replication) is **not** currently implemented.
- **Failover Strategy**: If the PostgreSQL database becomes unavailable, NWIS automatically logs a degraded persistence warning and falls back to read-only `CSVRepository` mode (`DATA_BACKEND=csv`) to maintain operational continuity of the well map and offset intelligence.
