# NWIS PHASE 8 — eRTMAC INTEGRATION SPECIFICATION
## Real-Time Monitoring & eRTMAC Gateway Telemetry Adapter

---

## 1. Overview & Operational Role

The **eRTMAC (electronic Real-Time Monitoring and Control)** integration layer provides a standardized telemetry adapter connecting NWIS to upstream Oil & Gas real-time telemetry systems.

> **CRITICAL DOMAIN SAFETY MANDATE**:
> NWIS is strictly an **advisory decision-support platform**. The eRTMAC adapter operates in **read-only telemetry ingestion mode**.
> Under NO circumstances does NWIS transmit actuation commands, automated setpoint alterations, mud pump modulations, or automated rig shut-in signals back into eRTMAC or rig instrumentation. All operational interventions remain solely with certified rig engineers.

---

## 2. Integration Modes & Readiness States

To prevent misleading claims of active telemetry feeds when physical credentials or private networks are unavailable, NWIS enforces explicit health states:

| Status | Condition | UI Indication | Diagnostic Meaning |
| :--- | :--- | :--- | :--- |
| **`DISABLED`** | `ERTMAC_ENABLED=false` | Gray Status Pill | Adapter configured off. No network calls executed. |
| **`DISCONNECTED`** | Enabled, credentials provisioned, but endpoint unreachable | Red Status Pill | Gateway unreachable or authentication failed. |
| **`CONNECTED`** | Handshake verified, telemetry actively arriving within cadence | Green Status Pill | Live data stream validated and flowing. |
| **`DEGRADED`** | Stream active but experiencing latency spikes or dropped packets | Amber Status Pill | Data arriving with latency > 5000ms or high warning rate. |
| **`STALE`** | Last verified packet timestamp > 60 seconds old | Amber Pulsing | Upstream rig telemetry paused or connection stalled. |

---

## 3. Data Schema & Ingestion Mapping

eRTMAC JSON/REST payloads are received via polling or server-sent events, mapped to `RealtimeTelemetryRecord`:

| eRTMAC Channel Mnemonic | NWIS Standard Field | Unit | Physical Range Check |
| :--- | :--- | :--- | :--- |
| `HOLE_DEPTH` / `MD` | `depth_md` | meters (m) | `[0.0, 12000.0]` |
| `ROP` / `DRILL_RATE` | `rop_m_hr` | m/hr | `[0.0, 300.0]` |
| `WOB` / `BIT_WEIGHT` | `wob_klbf` | klbf | `[0.0, 150.0]` |
| `SURF_RPM` | `rpm` | RPM | `[0.0, 350.0]` |
| `TORQUE` / `SURF_TORQ` | `torque_kftlb` | kft-lb | `[0.0, 100.0]` |
| `STANDPIPE_PRESS` / `SPP` | `standpipe_pressure_psi` | psi | `[0.0, 10000.0]` |
| `FLOW_IN` | `mud_flow_in_lpm` | LPM | `[0.0, 6000.0]` |
| `FLOW_OUT_PCT` / `FLOW_OUT` | `mud_flow_out_lpm` | LPM | `[0.0, 6000.0]` |
| `TOTAL_GAS` | `gas_units` | units | `[0.0, 10000.0]` |
| `MUD_WEIGHT` / `MW_IN` | `mud_weight_ppg` | ppg | `[6.0, 22.0]` |
| `HOOK_LOAD` | `hookload` | klbf | `[0.0, 1500.0]` |
| `PUMP_PRESS` | `pump_pressure` | psi | `[0.0, 10000.0]` |

---

## 4. Bounded Exponential Reconnect Strategy

When upstream connection issues arise, the adapter implements a strict bounded exponential backoff policy:
- Base delay: `1.0s`
- Backoff multiplier: `2.0`
- Maximum backoff interval: `30.0s`
- Max consecutive retry window: `5` attempts
- If failures exceed maximum threshold: Transition state to `DISCONNECTED`, record an audit entry, and enter a passive health-check polling state every 60 seconds without exhausting memory or sockets.

---

## 5. Security & Redaction

- Upstream endpoint URLs, usernames, passwords, and API keys are parsed strictly from environment variables:
  - `ERTMAC_ENABLED`
  - `ERTMAC_BASE_URL`
  - `ERTMAC_USERNAME`
  - `ERTMAC_PASSWORD`
  - `ERTMAC_API_KEY`
  - `ERTMAC_WELL_ID`
- Diagnostic logs and API responses (`/api/integrations/status`) automatically redact any authentication tokens, HTTP Authorization headers, or password query strings.
