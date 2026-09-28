# NWIS Phase 9 — Deployment & Operations Guide

## 1. System Architecture Overview
The **Nearby Wells Intelligence System (NWIS)** architecture supports two operational deployment profiles:
1. **Local Engineering Development:** Lightweight startup using native Python and Node.js runtimes with CSV dataset fallback or local PostgreSQL.
2. **Containerized Multi-Service Deployment:** Production-oriented Docker Compose stack orchestrating PostgreSQL 16 + PostGIS 3.4, FastAPI Backend, and Nginx Reverse Proxy serving the compiled React frontend.

> [!IMPORTANT]
> **Advisory Safety Disclaimer:**  
> NWIS is an advisory decision-support system. It must **never autonomously control drilling equipment or issue rig-control commands**.

---

## 2. Environment Variables Configuration

Before deploying, create an environment file:
```powershell
Copy-Item .env.example .env
```

### Core Configuration Parameters:
| Variable | Default (Dev) | Production Recommendation | Description |
|---|---|---|---|
| `ENVIRONMENT` | `development` | `production` | Enables strict security checks and disables dev fallbacks. |
| `DATA_BACKEND` | `csv` | `postgres` | Data persistence layer (`csv` or `postgres`). |
| `DATABASE_URL` | `postgresql://...` | `postgresql://user:pass@host:5432/nwis` | Connection URL for PostgreSQL + PostGIS. |
| `POSTGIS_ENABLED` | `true` | `true` | Enables spatial PostGIS index and offset radius calculations. |
| `JWT_SECRET` | *(Dev default)* | *(Cryptographic 32+ char secret)* | Secret key for signing and validating JWT bearer tokens. |
| `JWT_EXPIRE_MINUTES` | `480` | `480` (8 Hours) | Access token expiration window. |
| `LOG_LEVEL` | `INFO` | `INFO` | Logging threshold (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `STRUCTURED_LOGGING` | `false` | `true` | Formats stdout/stderr logs as single-line JSON records. |

---

## 3. Development Deployment Profile

### Quick Launch (Both Services):
```powershell
.\scripts\start_nwis.ps1
```
*Validates Python, Node.js, and ports 8000/5173. Spawns persistent terminal sessions and verifies HTTP 200 responses.*

### Manual Service Execution:
#### Backend Server:
```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
- API Base: `http://127.0.0.1:8000`
- Liveness Probe: `http://127.0.0.1:8000/health`
- Readiness Probe: `http://127.0.0.1:8000/api/ready`
- Metrics: `http://127.0.0.1:8000/api/metrics`
- Swagger Docs: `http://127.0.0.1:8000/docs`

#### Frontend Dev Server:
```powershell
cd frontend
npm run dev
```
- Frontend Web App: `http://127.0.0.1:5173/`

---

## 4. Production-Oriented Container Deployment

The multi-container stack is orchestrated via `docker-compose.yml`.

### Launch All Services:
```bash
docker compose up -d
```

### Verify Container Status & Health:
```bash
docker compose ps
```
Expected output:
- `nwis-postgres-postgis` (healthy) - Port 5432
- `nwis-backend` (healthy) - Port 8000
- `nwis-frontend` (healthy) - Port 80

### Application Verification:
```bash
# Verify Backend Health
curl -s http://127.0.0.1:8000/health

# Verify Backend Readiness
curl -s http://127.0.0.1:8000/api/ready

# Verify Metrics
curl -s http://127.0.0.1:8000/api/metrics

# Verify Frontend Web App
curl -s http://127.0.0.1/
```

### Graceful Shutdown Procedure:
```bash
docker compose down
```
*Database volumes (`pgdata`) and upload documents (`uploads_data`) persist across container lifecycle restarts.*
