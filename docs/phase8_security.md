# NWIS PHASE 8 — SECURITY, RBAC & AUDIT ARCHITECTURE
## Upstream Integration Hardening, Credential Protection & Audit Trails

---

## 1. Zero Credential Exposure Policy

- All integration secrets (`ERTMAC_API_KEY`, `ERTMAC_PASSWORD`, `WITSML_PASSWORD`, `JWT_SECRET`) must be provided via operating system environment variables or container secrets.
- Diagnostic endpoints (e.g. `/api/integrations/status`, `/api/health`, `/api/ready`) explicitly scrub credentials:
  - URLs have basic auth credentials masked: `https://user:***@host/path`.
  - Passwords and API keys return `configured: true/false` or `***REDACTED***`.
  - Raw telemetry persistence (when `STORE_RAW_TELEMETRY=true`) strips HTTP `Authorization` headers, cookies, and bearer tokens before saving.

---

## 2. Role-Based Access Control (RBAC) Matrix

| Endpoint | Action | ADMIN | DRILLING_ENGINEER | GEOLOGIST | VIEWER |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `/api/integrations/status` | View health & metrics | Allowed | Allowed | Allowed | Allowed |
| `/api/integrations/{provider}/connect` | Trigger upstream connection | Allowed | Allowed | Denied (403) | Denied (403) |
| `/api/integrations/{provider}/disconnect` | Terminate stream | Allowed | Allowed | Denied (403) | Denied (403) |
| `/api/realtime/alerts/{id}/acknowledge` | Acknowledge alert | Allowed | Allowed | Denied (403) | Denied (403) |
| `/api/realtime/alerts/{id}/close` | Close alert with notes | Allowed | Allowed | Denied (403) | Denied (403) |
| `/api/live/{well_id}/telemetry/latest` | View live telemetry | Allowed | Allowed | Allowed | Allowed |

`VIEWER` and unauthenticated callers are strictly restricted to read-only monitoring.

---

## 3. Append-Only Audit Logging

Every critical integration action creates an immutable record in `audit_logs`:
- **`INTEGRATION_CONNECT`**: Provider, initiator, timestamp, IP address.
- **`INTEGRATION_DISCONNECT`**: Provider, reason, initiator.
- **`ALERT_ACKNOWLEDGE`**: Alert ID, well ID, engineer identity, review note.
- **`ALERT_CLOSE`**: Alert ID, closure justification, timestamp.
- **`WELL_MAPPING_UPDATED`**: External ID, canonical well ID mapping.
