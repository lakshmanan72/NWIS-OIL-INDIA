# NWIS Phase 6: Real-Time eRTMAC Integration & Live Risk / Alert Engine Architecture

> **CRITICAL OPERATIONAL ADVISORY**  
> **NWIS is strictly an ADVISORY DECISION-SUPPORT SYSTEM, NOT an autonomous drilling or rig-control system.**  
> Autonomous machine actuation is strictly prohibited. All real-time streaming telemetry, rolling anomaly detections, Phase 3.1 Model Risk Indicators, and live alerts are advisory notifications designed to augment engineering situational awareness. All drilling parameter adjustments, mud treatment actions, and operational interventions require formal human engineer review and sign-off.

---

## 1. Architectural Pipeline Overview

NWIS Phase 6 extends the established Phase 2 (GIS / Offset Wells), Phase 3.1 (ML Risk Prediction & Leakage Audit), Phase 4 (Document Intelligence & OCR), and Phase 5/5.1 (Semantic RAG & Engineering Copilot) foundations by introducing an enterprise-grade real-time streaming intelligence and alerting layer.

```
LIVE DRILLING TELEMETRY (WITS0 / WITSML / eRTMAC Stream / Demo Replay)
        ↓
INGESTION & PAYLOAD VALIDATION (Range validation, unit sanity, schema checks)
        ↓
LIVE WELL STATE & FRESHNESS MONITOR (Buffer, signal quality, age tracking: LIVE / REPLAY / DELAYED / STALE / DISCONNECTED)
        ↓
STREAMING FEATURE ENGINE (Rolling mean, std, ROC [rate of change], flow imbalance Δ and %)
        ↓
STREAMING ANOMALY DETECTOR (Deterministic rules: torque spike, SPP surge/loss, mud loss/gain, ROP drilling break)
        ↓
LIVE RISK ENGINE (Dual-channel correlation: Phase 3.1 Model Inference + Stratigraphic Formation context)
        ↓
STRICT SOURCE SEPARATION ([LIVE-XXX] Telemetry Observations vs [EVID-XXX] Approved Institutional Records)
        ↓
ALERT ENGINE (Depth-window deduplication [5m], hysteresis cooldown [60s], lifecycle state machine)
        ↓
REAL-TIME DASHBOARD (/live) + WEBSOCKET BROADCAST + MAP INTEGRATION + WELL INTELLIGENCE + COPILOT CITATION
```

---

## 2. Core Architectural Pillars

### A. Strict Data Provenance & Evidence Separation
In compliance with enterprise oil & gas engineering standards, real-time observational data and approved historical documentation are never conflated:
1. **Real-Time Telemetry Identifiers**: Every real-time observation, streaming anomaly, and parameter threshold violation is tagged with a distinct `LIVE-XXX` identifier (e.g., `LIVE-TRQ-1132`, `LIVE-FLW-1132`).
2. **Institutional Memory Identifiers**: Historical technical documentation and offset well evidence retain immutable `EVID-XXX` identifiers (e.g., `EVID-DOC-5D84-C002`).
3. **Synthesis Grounding**: The Engineering Copilot and citation validator explicitly distinguish between what is actively observed at surface/downhole right now (`LIVE-XXX`) versus historical precedent documented in offset WCR/DDR records (`EVID-XXX`).

### B. Streaming Telemetry Ingestion & Freshness State Machine
- **Supported Adapters**: Pluggable provider hierarchy implementing `RealtimeDrillingProvider`:
  - `DemoReplayProvider`: Replays authentic historical daily drilling records (WELL-000050) at configurable intervals (1.0s - 5.0s). Labeled transparently as `DEMO REPLAY` in the UI to prevent operational confusion.
  - `RESTPollingProvider`: Integrates with upstream eRTMAC HTTP REST endpoints.
  - `WebSocketProvider`: Real-time bidirectional streaming gateway.
  - `KafkaProvider` & `MQTTProvider`: Enterprise message broker stubs for field edge gateways.
- **Freshness Classification**:
  - `LIVE`: Telemetry age $\le 5.0\text{ s}$
  - `DELAYED`: $5.0\text{ s} < \text{age} \le 30.0\text{ s}$
  - `STALE`: $30.0\text{ s} < \text{age} \le 60.0\text{ s}$
  - `DISCONNECTED`: Telemetry age $> 60.0\text{ s}$ or heartbeat lost
  - `REPLAY`: Active simulation/replay mode (persisted with explicit visual badge)

### C. Streaming Feature Extraction Engine
The `RealtimeFeatureEngine` maintains a rolling temporal window ($N = 20$ records) to extract real-time kinematic and hydraulic dynamics without batch recomputations:
- **Rolling Statistics**: Rolling mean ($\mu$) and standard deviation ($\sigma$) across Depth, ROP, WOB, RPM, Torque, SPP, and Mud Flow.
- **Rate of Change (ROC)**: First-order derivative with respect to time ($\frac{\Delta x}{\Delta t}$) for Torque ($\text{kft}\cdot\text{lb}/\text{min}$), SPP ($\text{psi}/\text{min}$), and ROP ($\text{m}/\text{hr}/\text{min}$).
- **Flow Imbalance**:
  $$\Delta Q = Q_{\text{in}} - Q_{\text{out}}$$
  $$\text{Flow Imbalance \%} = \frac{|Q_{\text{in}} - Q_{\text{out}}|}{\max(Q_{\text{in}}, 1.0)} \times 100\%$$

### D. Streaming Anomaly Detection
Deterministic physics and engineering threshold rules evaluate real-time signals against baseline parameters:
1. **Torque Spike**: Rolling torque exceeds $\mu + 2.5\sigma$ or instantaneous surge $> 22.0\text{ kft}\cdot\text{lb}$ ($\Delta \tau > 4.0\text{ kft}\cdot\text{lb}/\text{min}$). Primary indicator for impending stuck pipe, pack-off, or bit balling.
2. **Pressure Loss / Surge**: SPP drops $> 300\text{ psi}$ (washout / severe mud loss) or spikes $> 400\text{ psi}$ (pack-off / annulus bridging).
3. **Mud Loss / Kick Influx**:
   - Influx / Kick: $Q_{\text{out}} > Q_{\text{in}} + 150\text{ LPM}$ or imbalance $> 15\%$ with gas elevation.
   - Circulation Loss: $Q_{\text{out}} < Q_{\text{in}} - 150\text{ LPM}$ or imbalance $> 15\%$.
4. **ROP Sudden Drop / Drilling Break**:
   - Drilling Break: Sudden ROP doubling ($\text{ROC} > +15\text{ m/h/min}$), indicating porous/permeable formation transition.
   - ROP Drop: Sudden ROP collapse with constant WOB, indicating bit wear or severe hard stringers.

### E. Live Multi-Signal Risk Engine
The `LiveRiskEngine` combines:
1. **Phase 3.1 Validated ML Models**: Pre-trained Random Forest, XGBoost, and CatBoost models evaluate current depth, formation lithology, and operating parameters against validated validation-only decision thresholds (`nwis-v1.0`).
2. **Subsurface Stratigraphy Context**: Formations traversed at current bit depth (e.g., Eocene Limestone, Cretaceous Shale) pulled from canonical geological markers.
3. **Real-Time Operational Signals**: Synthesizes Model Risk + Real-Time Anomaly + Historical Offset Precedent into four categorical states:
   - `NORMAL`: No model elevation or active anomalies.
   - `ELEVATED_MODEL`: Model risk exceeds threshold, but surface signals remain nominal.
   - `ELEVATED_SIGNAL`: Real-time anomaly detected, but offset model risk is moderate.
   - `CRITICAL_CORRELATION`: Both Phase 3.1 model predicts elevated risk AND real-time surface anomaly is actively detected at the current depth interval.

### F. Alert Lifecycle & Suppression Architecture
The `AlertEngine` enforces strict operational hygiene to prevent alert fatigue on the rig floor or remote monitoring center:
1. **Deduplication across Depth Windows**: Alerts of the same hazard type occurring within a $\pm 5.0\text{ m}$ depth window are consolidated rather than duplicated.
2. **Hysteresis & Cooldown Suppression**: Once an alert triggers for a hazard, repeated identical alerts are suppressed for a minimum cooldown duration ($60.0\text{ s}$) unless severity escalates.
3. **Lifecycle State Machine**:
   $$\text{DETECTED} \longrightarrow \text{EVALUATED} \longrightarrow \text{ACTIVE} \xrightarrow{\text{Engineer Ack}} \text{ACKNOWLEDGED} \xrightarrow{\text{Resolution}} \text{CLOSED}$$
4. **Engineer Accountability**: Acknowledging or closing an alert requires recording the engineer's identity, timestamp, and operational review notes.

---

## 3. API Surface & Integration Endpoints

| Protocol | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/realtime/telemetry` | Ingest single real-time telemetry record |
| `POST` | `/api/realtime/telemetry/batch` | Ingest batch telemetry payload |
| `GET` | `/api/realtime/latest/{well_id}` | Query current telemetry record, freshness, and buffer status |
| `GET` | `/api/realtime/features/{well_id}` | Retrieve rolling mean, std, ROC, and flow imbalance metrics |
| `GET` | `/api/realtime/anomalies/{well_id}` | List actively detected streaming anomalies |
| `GET` | `/api/realtime/risks/{well_id}` | Multi-signal synthesis combining Phase 3.1 ML + live signals |
| `GET` | `/api/realtime/alerts` | Query active/acknowledged alerts with well/severity filters |
| `POST` | `/api/realtime/alerts/{id}/ack` | Human engineer acknowledgment with operational note |
| `POST` | `/api/realtime/alerts/{id}/close` | Formally close alert upon operational mitigation |
| `POST` | `/api/realtime/replay/start` | Launch demo replay stream from authentic historical records |
| `POST` | `/api/realtime/replay/stop` | Halt active demo replay stream |
| `POST` | `/api/realtime/demo/inject-anomaly` | Inject controlled operational anomaly for test/verification |
| `GET` | `/api/realtime/stream/{well_id}` | HTTP polling/streaming endpoint for lightweight dashboard sync |
| `WS` | `/ws/realtime/{well_id}` | Bidirectional WebSocket stream for sub-second telemetry broadcast |

---

## 4. Frontend Operations Cockpit

The frontend implementation delivers a dedicated, high-density operations center:
1. **Live Operations Console (`/live`)**:
   - High-contrast operational header with real-time status pill (`LIVE`, `DEMO REPLAY`, `DELAYED`, `STALE`, `DISCONNECTED`) and data age counter.
   - 8-Card Telemetry Grid: Bit Depth (MD), ROP, WOB, RPM, Surface Torque, SPP, Mud Flow In/Out, and Total Gas. Dynamic threshold coloring for visual alerts.
   - Dual-Panel Synthesis: Streaming Observational Signals (left) alongside Phase 3.1 Model Risk Indicators with pre-computed ROC metrics (right).
   - Real-Time Alerts Queue: Displays active alerts sorted by severity (CRITICAL, HIGH, MEDIUM, LOW) with depth, formation, recommended mitigation action, and full evidence packet drill-down.
   - Interactive Modals: Fully validated Engineer Acknowledgment and Alert Closure workflows with mandatory engineer sign-off.
2. **Interactive Map Integration (`/`)**:
   - Real-time indicator badges on active drilling well markers with one-click navigation to `/live`.
3. **Well Intelligence Cockpit (`/well/{well_id}`)**:
   - Integrated "Live Telemetry & Alerts" tab offering live parameter tracking and alert status directly alongside subsurface logs, offset wells, and document history.
