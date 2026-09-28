# NWIS Phase 7 Database Architecture

This directory contains the database initialization schema, Docker configuration, migration files, and seed utilities for the NWIS production PostgreSQL + PostGIS platform.

---

## Directory Structure

```
database/
├── README.md               # Database operational guide (this file)
├── schema/
│   └── 01_init.sql         # Canonical PostgreSQL 16 + PostGIS 3.4 schema DDL
├── migrations/             # Alembic migration revisions
└── seed/                   # Seed fixtures and verification datasets
```

---

## Quickstart: Docker PostGIS Container

To spin up a local PostGIS container:

```bash
# Start PostGIS container
docker compose up -d

# Check logs
docker compose logs -f postgres-postgis

# Verify PostGIS extension
docker compose exec postgres-postgis psql -U nwis_admin -d nwis -c "SELECT PostGIS_Version();"
```

Connection string:
```
postgresql://nwis_admin:nwis_secure_password_2026@localhost:5432/nwis
```

---

## Zero-Docker / CSV Mode (Default)

NWIS does not require Docker or a running PostgreSQL instance for development and CI testing. When:

```bash
DATA_BACKEND=csv
```

The system automatically operates using high-performance in-memory Pandas indexing over canonical CSV files (`data/raw/`) and JSON document stores (`data/documents/`).

When:

```bash
DATA_BACKEND=postgres
DATABASE_URL=postgresql://user:password@localhost:5432/nwis
```

The system connects via SQLAlchemy 2.0 and executes PostGIS spatial queries (`ST_DWithin`, `ST_Distance`). If the database becomes unreachable, the dual repository architecture issues a structured log warning and seamlessly continues serving read traffic via the CSV fallback.
