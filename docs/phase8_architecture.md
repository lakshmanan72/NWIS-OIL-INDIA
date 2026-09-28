# NWIS PHASE 8 ARCHITECTURE — REAL eRTMAC / WITSML INTEGRATION
## Production Streaming + Telemetry Adapter + Live Engineering Intelligence

```
========================================================================================
NWIS Phase 8 — End-to-End Real-Time Drilling Telemetry Architecture
========================================================================================

   EXTERNAL RIG & TELEMETRY SOURCES
   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
   │    eRTMAC   │   │   WITSML    │   │    WITS0    │   │ REST / Poll │   │ Demo Replay │
   │ REST / SOAP │   │ SOAP Store  │   │ Level 0 TCP │   │  Rig Agent  │   │ CSV Archive │
   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘
          │                 │                 │                 │                 │
          ▼                 ▼                 ▼                 ▼                 ▼
   ┌─────────────────────────────────────────────────────────────────────────────────┐
   │                        INTEGRATION ADAPTER LAYER                                │
   │  - ERTMACAdapter    - WITSMLAdapter    - WITS0Adapter   - Polling / WebSocket   │
   │  - TLS Verification - Auth Redaction   - Exponential Bounded Reconnect          │
   └────────────────────────────────────────┬────────────────────────────────────────┘
                                            │
                                            ▼
   ┌─────────────────────────────────────────────────────────────────────────────────┐
   │                   WELL IDENTITY RESOLVER & QUARANTINE GATING                   │
   │  - Maps External IDs (e.g. eRTMAC 'RIG1_WELL_A') -> Canonical 'WELL-000050'    │
   │  - UNMATCHED_WELL Isolation: Rejects unmapped rigs from canonical telemetry     │
   └────────────────────────────────────────┬────────────────────────────────────────┘
                                            │
                                            ▼
   ┌─────────────────────────────────────────────────────────────────────────────────┐
   │                  RAW VALIDATION & NORMALIZED TELEMETRY CONTRACT                 │
   │  - RealtimeTelemetryRecord (UTC Normalized, Source Timestamps, Ingestion MS)   │
   │  - Physical Plausibility Rules (MD>=0, ROP 0-300, WOB 0-150, SPP 0-10000, etc.) │
   │  - Quality Classification: VALID | VALID_WITH_WARNINGS | SUSPECT | DUPLICATE   │
   └────────────────────────────────────────┬────────────────────────────────────────┘
                                            │
                                            ▼
   ┌─────────────────────────────────────────────────────────────────────────────────┐
   │              BOUNDED INGESTION PIPELINE & BACKPRESSURE CONTROLLER               │
   │  - TELEMETRY_QUEUE_MAX_SIZE (Default: 5000 slots)                               │
   │  - Drop Policy & Health Counters: Ingestion Rate, Drops, Reconnects, Latency   │
   └───────────────────┬─────────────────────────────────────────┬───────────────────┘
                       │                                         │
        (In-Memory Fast Path)                   (Safe Non-Blocking Persistence)
                       │                                         │
                       ▼                                         ▼
   ┌────────────────────────────────────────┐  ┌────────────────────────────────────┐
   │            LIVE WELL STATE             │  │       TELEMETRY REPOSITORY         │
   │  - Thread-Safe Ring Buffer (100 pts)   │  │  - PostgreSQL: telemetry_records   │
   │  - Authoritative Snapshot Persistence  │  │    & well_live_state upsert        │
   │  - Restart Recovery State              │  │  - CSV Fallback Mode Support       │
   └───────────────────┬────────────────────┘  └────────────────────────────────────┘
                       │
                       ▼
   ┌─────────────────────────────────────────────────────────────────────────────────┐
   │                     ROLLING FEATURE ENGINE (30m & 60m Windows)                  │
   │  - Running Means, Standard Deviations, Maxima, Minima                           │
   │  - Delta Rates-of-Change (dTorque/dt, dSPP/dt, dROP/dt)                         │
   │  - Flow Imbalance Calculation (Q_in vs Q_out)                                   │
   └───────────────────┬─────────────────────────────────────────────────────────────┘
                       │
                       ▼
   ┌─────────────────────────────────────────────────────────────────────────────────┐
   │                    DETERMINISTIC ANOMALY DETECTOR (LIVE-XXX)                    │
   │  - Torque Spikes, SPP Surges / Losses, Flow Imbalance, ROP Drilling Breaks      │
   │  - Gas Surges, Wob Wobble                                                       │
   │  - Emits Distinct LIVE-XXX Telemetry Evidence Tokens                            │
   └───────────────────┬─────────────────────────────────────────────────────────────┘
                       │
                       ▼
   ┌─────────────────────────────────────────────────────────────────────────────────┐
   │               DEPTH SAFETY CHECK & PHASE 3.1 ML RISK EVALUATION                 │
   │  - Depth Safety Check: Depth > Well Total Depth?                                │
   │    -> Flags EXTRAPOLATED_BEYOND_TOTAL_DEPTH (blocks false certainty)            │
   │  - Phase 3.1 Models: Mud Loss (RF), Stuck Pipe (XGB), Kick (CatBoost), Overpres  │
   │  - Model Risk Indicators (Decision Support, Not Calibrated Probabilities)       │
   └───────────────────┬─────────────────────────────────────────────────────────────┘
                       │
                       ▼
   ┌─────────────────────────────────────────────────────────────────────────────────┐
   │               EVIDENCE CORRELATION & ALERT LIFECYCLE ENGINE                     │
   │  - Separation of LIVE-XXX (Realtime) vs EVID-XXX (Historical Offset Documents)  │
   │  - Lifecycle: DETECTED -> EVALUATED -> ACTIVE -> ACKNOWLEDGED -> CLOSED         │
   │  - Spatial/Depth Deduplication: +/- 5.0m window                                 │
   │  - Cooldown: 60 seconds minimum recurrence buffer                               │
   │  - Severity Hysteresis Escalation                                               │
   │  - AlertRepository (PostgreSQL alerts table & active_alerts.json fallback)      │
   └───────────────────┬─────────────────────────────────────────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
   ┌───────────────────────────┐   ┌───────────────────────────────────────────────┐
   │    WEBSOCKET BROADCAST    │   │           REST APIS & AUDIT TRAIL             │
   │ /ws/realtime/{well_id}    │   │  /api/integrations/status                     │
   │ Real-time UI updates at   │   │  /api/integrations/{provider}/connect         │
   │ 1 Hz continuous cadence   │   │  /api/live/{well_id}/telemetry/latest         │
   │ Zero secret leakage       │   │  RBAC: Admin / Engineer control, Viewer read  │
   └─────────────┬─────────────┘   └───────────────────────┬───────────────────────┘
                 │                                         │
                 └───────────────────┬─────────────────────┘
                                     │
                                     ▼
   ┌─────────────────────────────────────────────────────────────────────────────────┐
   │                 NWIS LIVE OPERATIONS CONSOLE (FRONTEND UI)                      │
   │  - Multi-Provider Integrations Panel (eRTMAC, WITSML, Demo Replay)              │
   │  - Status Badges: CONNECTED | DEGRADED | STALE | DISCONNECTED | DISABLED        │
   │  - Telemetry Telemetry Gauges + Freshness Heartbeat                             │
   │  - Dual Evidence Inspector (LIVE-XXX vs EVID-XXX)                               │
   │  - Advisory Banner: "Advisory decision-support system. Operator review req."    │
   └─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Core Integration Objectives

1. **Multi-Protocol Telemetry Ingestion**:
   Standardized ingestion adapters for eRTMAC (REST/JSON), WITSML (1.3.1.1/1.4.1.1 XML Store queries), WITS0 (Level 0 serial/TCP stream), external HTTP Polling, and deterministic Demo Replay.
2. **Authentic Readiness Without Fake Claims**:
   If upstream rig credentials or endpoints are not provisioned in `.env`, the adapter states are explicitly marked `DISABLED` or `DISCONNECTED` ("Integration-ready"). Zero mock claims of live OIL connection.
3. **Strict Domain & Depth Safety**:
   If drill depth surpasses the canonical well's verified Total Depth (TD), the system emits `EXTRAPOLATED_BEYOND_TOTAL_DEPTH`, suppressing unvalidated ML inference.
4. **Strict Dual Evidence Provenance**:
   - `LIVE-XXX`: Transient, telemetry-derived anomalies with physical signal records.
   - `EVID-XXX`: Historical document-derived offset evidence with page/section citations.
   Never confused or blended into a single token namespace.
5. **Robust Backpressure & Stream Hygiene**:
   - Bounded ingestion queue (`TELEMETRY_QUEUE_MAX_SIZE`).
   - Monotonic UTC timestamp normalization.
   - Ingestion latency metrics tracking.
   - Duplicate message suppression via `(well_id, source, source_timestamp, depth_md)`.
   - Out-of-order arrival tolerance preserving newest valid live state.
6. **Unified Security, RBAC & Auditability**:
   - Upstream secrets strictly redacted and parsed only from environment variables.
   - Integration lifecycle controls (`connect`, `disconnect`) restricted to `ADMIN` and `DRILLING_ENGINEER`.
   - Immutable audit logging for all connection state transitions and alert resolutions.
