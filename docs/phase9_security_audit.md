# NWIS Phase 9 — Production Security Audit & Hardening Matrix

## 1. Executive Summary & Advisory Constraint
The **Nearby Wells Intelligence System (NWIS)** is an engineering decision-support platform designed to provide subsurface intelligence, offset well risk indicators, and real-time drilling situational awareness. 

> [!CRITICAL]
> **Advisory Boundary Constraint:**  
> NWIS is strictly a decision-support system. It has **no automated actuator access, autonomous rig control, closed-loop choke adjustment, or downhole tool steering capability**. All operational changes require licensed drilling engineer evaluation and authorized rig-floor intervention.

This audit establishes the security baseline, identifies potential operational and cyber risks, details applied mitigations, and confirms verification status.

---

## 2. Security Controls & Architecture Baseline

| Domain | Control Baseline | Implementation |
|---|---|---|
| **Authentication** | Cryptographic token-based | JWT (HS256) with PBKDF2-SHA256 password hashing. Tokens expire after 480 minutes (configurable). Missing credentials in production trigger strict HTTP 401. |
| **Authorization (RBAC)** | Principle of Least Privilege | Enforces 4 distinct roles: `ADMIN`, `DRILLING_ENGINEER`, `GEOLOGIST`, and `VIEWER`. Write/approval endpoints strictly deny `VIEWER` (HTTP 403). |
| **Secrets Management** | Zero-Secret Repository | Secrets injected solely through environment variables (`.env`). Default secrets rejected in production mode. Passwords masked in logs and health endpoints. |
| **Document Upload Security** | Defense-in-Depth Quarantine | Strict 50 MB limit, extension whitelist (`.pdf`, `.txt`), magic-bytes validation (`%PDF-`), PyPDF structural verification, SHA-256 deduplication, UUID disk storage, and quarantine review state. |
| **Audit Logging** | Immutable Append-Only | Security events (login success/failure, document approve/reject, alert ack/close, integration connect/disconnect) written to append-only audit repository. |
| **API Boundary Protection** | Parameter & Size Validation | Pydantic v2 schemas enforce typed bounds on coordinates, depths, radii, and pagination clamps (`limit <= 500`). Path traversal patterns (`..`, `/`, `\`) rejected. |
| **Error Handling** | Sanitized Public Payloads | Global exception handler prevents exposure of Python tracebacks, database connection strings, or filesystem paths to end users. |

---

## 3. Comprehensive Risk Assessment & Verification Matrix

| ID | Threat Vector | Risk Description | Severity | Mitigation Applied | Verification Status |
|---|---|---|---|---|---|
| **SEC-01** | Default Secret in Production | Using default dev JWT secret or dev database password in production could allow token forgery. | **HIGH** | `DatabaseConfig.validate_production_security()` raises a fatal runtime exception if production mode is active without an explicit, strong secret (>= 32 chars). | **VERIFIED** (Passed automated check) |
| **SEC-02** | Path Traversal in File Upload | Malicious filename (e.g. `../../etc/passwd.pdf`) attempting to overwrite system files. | **HIGH** | Filename traversal check (`..`, `/`, `\`) rejected with HTTP 400. Uploaded files stored as UUIDs in dedicated quarantine directory. | **VERIFIED** (Automated test passed) |
| **SEC-03** | Malformed / Corrupted PDF Upload | Malformed binary payload causing parser crash or denial of service. | **MEDIUM** | Magic bytes `%PDF-` checked, PyPDF structural check, encrypted PDF detection, 0-page check. Rejection with HTTP 400 on invalid format. | **VERIFIED** (Automated test passed) |
| **SEC-04** | Role Privilege Escalation | Read-only VIEWER attempting to approve WCR extractions or alter rig alerts. | **HIGH** | `require_role(ROLE_ADMIN, ROLE_DRILLING_ENGINEER)` enforced via FastAPI dependency on all review, mutation, and operational endpoints. Returns HTTP 403. | **VERIFIED** (Automated test passed) |
| **SEC-05** | Sensitive Data Leakage in Traces | Unhandled exception exposing SQL queries, table schemas, or filesystem paths in HTTP 500 responses. | **MEDIUM** | Global exception handler catches unhandled exceptions, generates an audit correlation ID (`X-Request-ID`), logs diagnostic info internally, and returns a sanitized generic JSON message. | **VERIFIED** (Automated test passed) |
| **SEC-06** | Brute Force Authentication | Rapid credential guessing on `/api/auth/login`. | **MEDIUM** | Failed logins log audit events with client IP and reason. Password hashing utilizes PBKDF2 with high iteration count. | **VERIFIED** (Automated test passed) |
| **SEC-07** | Client-Side Secret Exposure | Frontend bundles leaking backend database passwords or private API keys. | **HIGH** | Audited `frontend/` source: zero `eval()`, zero `dangerouslySetInnerHTML`, zero `localStorage` token persistence. Only `VITE_API_BASE_URL` is configured in frontend `.env.example`. | **VERIFIED** (Codebase grep verified) |
| **SEC-08** | Inadvertent Restore Data Loss | Executing restore script accidentally drops live production database tables. | **HIGH** | `scripts/restore_postgres.ps1` requires explicit confirmation typing `'RESTORE'` (or `-Force` switch) and verifies SHA-256 backup checksum before proceeding. | **VERIFIED** (Script logic validated) |

---

## 4. Residual Risks & Production Prerequisites
1. **Transport Layer Security (TLS/HTTPS):**  
   Local development runs on HTTP `127.0.0.1`. In production, a reverse proxy (e.g., Nginx, Traefik, or Cloud Load Balancer) must terminate TLS (TLS 1.3) with HSTS enabled.
2. **Database Network Isolation:**  
   PostgreSQL port `5432` must be bound exclusively to internal private container networks or VPC subnets, never exposed to the public internet.
3. **Upstream Rig Integration Credentials:**  
   External SCADA/eRTMAC and WITSML adapters remain disabled by default. Upstream credentials must be supplied via enterprise vault or environment variables upon field commissioning.
