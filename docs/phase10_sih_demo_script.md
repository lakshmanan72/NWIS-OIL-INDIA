# NWIS — SIH Grand Finale 5–7 Minute Engineering Demo Script
**Nearby Wells Intelligence System (NWIS)**  
*Subsurface Drilling Intelligence, Offset Correlation & Advisory Early Warning Platform*  
*Demonstration Track: Smart India Hackathon (SIH) Grand Finale*

---

## Executive Demonstration Overview
- **Target Audience:** Technical Evaluation Committee, Ministry of Petroleum & Natural Gas (MoPNG) Evaluators, Industry Jury (ONGC/OIL).
- **Duration:** 5 to 7 Minutes.
- **Tone:** Senior Petroleum Systems Architect / Drilling Operations Technologist.
- **Safety Stance:** Advisory Decision-Support Only — Autonomous Machine Actuation Strictly Prohibited.

---

## Step-by-Step Demonstration Timeline

### 1. The Core Engineering Problem (0:00 – 0:45)
- **Presenter:**  
  *"Respected Jury, exploratory and development drilling in complex Indian sedimentary basins involves severe subsurface hazards: catastrophic mud losses into depleted zones, stuck drillstrings, overpressure zones, and kicks. Upwards of 40% of non-productive time (NPT) is driven by lack of rapid, contextualized correlation with nearby legacy offset wells. Historical data exists in paper or scanned Well Completion Reports (WCRs), while real-time rig surface measurements arrive disconnected from offset institutional experience. NWIS bridges this gap by unifying 15,108 canonical wells with AI-driven offset risk prediction, strict document provenance, and real-time advisory telemetry."*

---

### 2. Multi-Dataset Geospatial Exploration (0:45 – 1:30)
- **UI Location:** `http://127.0.0.1:5173/` (`Interactive Map`)
- **Action:**  
  1. Show full-screen map with **15,148 loaded wells** (15,108 baseline public wells + dynamically ingested WCR wells).
  2. Point out the top header: `Wells Loaded: 15,148` pulse badge and `NWIS DATA ● CSV DEMO` status indicator.
  3. Filter or zoom into the high-density Assam-Arakan or Cambay Basin basin cluster.
- **Talking Point:**  
  *"The interactive spatial engine indexes 15,108 public petroleum wells across Indian onshore and offshore basins with dual database agility (CSV demo archive and PostgreSQL/PostGIS spatial index). Every point represents a canonical well with verified geographic coordinates, operator metadata, and formation stratigraphy."*

---

### 3. Canonical Well Selection & Offset Intelligence (1:30 – 2:30)
- **UI Location:** `Interactive Map` → click `WELL-000050` (or `WELL-000001`) → `Analyze in Well Intelligence` (`http://127.0.0.1:5173/well/WELL-000050`).
- **Action:**  
  1. Demonstrate seamless zero-404 navigation from map to Well Intelligence Cockpit.
  2. Walk through the 10 data tabs: **Overview, Geology, Formations, Drilling History, Mud Logging, Events, Risks, Completion, Documents, Offset Intelligence**.
  3. Adjust the offset radius slider (25 km) and depth window (±100 m).
- **Talking Point:**  
  *"Notice the canonical identifier WELL-000050. When we query offset intelligence at the active measured depth of 1,132 m, NWIS computes spatial Euclidean distance to nearby wells, isolates stratigraphically matched formations (e.g., Barail sandstones), and pulls forward offset drilling events: lost circulation incidents and torque anomalies encountered by offset wells within 25 km."*

---

### 4. Historical Drilling Evidence & WCR Approval Governance (2:30 – 3:30)
- **UI Location:** `http://127.0.0.1:5173/documents` (`Documents`) and `/documents/upload` (`Upload WCR`)
- **Action:**  
  1. Show Technical Document Repository with verified WCRs and DDRs.
  2. Explain the uncompromised governance model: uploaded WCR PDFs pass through text extraction, OCR, field parsing, and event extraction into a `REVIEW REQUIRED` queue.
  3. Demonstrate that raw extractions are NEVER automatically promoted into Institutional Memory without explicit engineer approval.
- **Talking Point:**  
  *"Crucially for audit compliance, NWIS enforces human-in-the-loop engineering governance. Unverified document extractions stay in staging. Only when a drilling engineer reviews, verifies, and formally signs off on extracted casing intervals and hazard depths does the record earn a cryptographic `EVID-*` identifier and get indexed into the semantic vector store."*

---

### 5. Semantic RAG & Engineering Copilot (3:30 – 4:15)
- **UI Location:** `http://127.0.0.1:5173/institutional-memory` (`Institutional Memory`)
- **Action:**  
  1. Ask Copilot query: *"What were the mud losses in offset wells near WELL-000001?"*
  2. Show instant retrieval grounded in `[EVID-001]` from approved WCR records.
  3. Point out strict separation: Copilot uses `EVID-*` for document evidence and never fabricates telemetry.
- **Talking Point:**  
  *"Our Engineering Copilot operates with strict zero-hallucination discipline. Answers cite exact `[EVID-001]` citations linking to verified offset well records. If no verified evidence exists for an interval, the engine explicitly returns an Insufficient Evidence response rather than generating unsubstantiated assumptions."*

---

### 6. Live Operations: Indian Petroleum Control Room Cockpit (4:15 – 5:30)
- **UI Location:** `http://127.0.0.1:5173/live` (`Live Operations`)
- **Action:**  
  1. **Visual Walkthrough:** Point out the Indian petroleum control room visual theme, full-width sunset rig hero, Ministry of Petroleum & Natural Gas / IndianOil insignia, advisory safety banner, and the 8 telemetry cards in a 4×2 desktop grid (**DEPTH, ROP, WOB, RPM, TORQUE, SPP, FLOW, GAS**).
  2. **Transparency:** Point out the right-hand **Telemetry Source** card: `● DEMO REPLAY`, `DEMO MODE — NOT LIVE RIG CONNECTIVITY`, `NWIS Historical Telemetry Archive`. Open `[ ⓘ Source Details → ]` modal to show sensor envelope checks and supported provider architecture.
  3. **Start Replay:** Click `▶ Start Replay`. Observe the live status pill update to `● DEMO REPLAY — RUNNING`, green pulse dot, and the real-time SVG drilling chart animating with glowing endpoint.
  4. **Observational Signals:** Show the 5 deterministic cards (**Torque Spike, Mud Loss, Stuck Pipe, Pressure Surge, Kick**) in `NORMAL` state.
  5. **Model Risk Indicators:** Show the 5 ML indicators (**Mud Loss 12%, Stuck Pipe 8%, Kick 3%, Overpressure 15%, Torque Spike 9%**) with underlying algorithms (`Random Forest` / `Ensemble`).
- **Talking Point:**  
  *"In our Live Operations Cockpit, we observe real-time bit telemetry. Notice our strict industrial transparency: we clearly state DEMO REPLAY. We do not fabricate live rig connectivity or pretend unconfigured WITSML feeds are streaming. All 8 channels are continuously evaluated against physical domain limits."*

---

### 7. Real-Time Anomaly Injection & Alert Lifecycle (5:30 – 6:30)
- **UI Location:** `Live Operations` (`Replay Controls` & `Active Alerts`)
- **Action:**  
  1. Click `⚡ Inject Torque Spike (Simulation Only)`.
  2. Observe observational signal for **Torque Spike** transition from `NORMAL` to `ELEVATED` / `CRITICAL`.
  3. Observe **Active Alerts** panel trigger with alert: `TORQUE SPIKE DETECTED | High Severity | Depth: 2434.6 m MD`.
  4. Click `Acknowledge`: modal opens with Engineer Sign-Off name and Review Notes. Click `Confirm Acknowledgement`.
  5. Observe alert badge update to `✓ ACKNOWLEDGED`.
  6. Click `Close Alert`. Status updates to `CLOSED`, and panel returns to `✓ NO ACTIVE ALERTS — Operational parameters remain within the currently monitored envelope.`
  7. Click `Open Well Intelligence Cockpit (WELL-000001) →` to close the loop back to offset correlation.
- **Talking Point:**  
  *"When a sudden torque anomaly occurs, deterministic thresholds and ML inference flags trigger concurrently. The alert lifecycle requires formal engineer review and sign-off before closure. No alerts are silently auto-dismissed."*

---

### 8. Safety Boundaries & Final Impact Summary (6:30 – 7:00)
- **UI Location:** `Advisory Decision-Support Banner`
- **Closing Statement:**  
  *"To conclude, NWIS is built on unyielding engineering principles:
  - **Advisory Decision-Support Only:** Machine actuation is prohibited; human engineer sign-off is mandatory.
  - **Data Provenance:** Historical data uses `EVID-*`, real-time streams use `LIVE-*`, and unverified data is never indexed.
  - **Operational Truth:** Transparent demo replay mode prevents dangerous illusions of live connectivity.
  NWIS delivers faster correlation, reduced NPT, and institutional memory retention for India's upstream energy security. Thank you."*

---

## Jury Q&A Quick Defense Guide

| Anticipated Jury Question | Verified Technical Answer |
| :--- | :--- |
| **"Are you connected to an active OIL/ONGC rig right now?"** | *"No. We operate with strict industrial transparency. The system currently streams from the NWIS Historical Telemetry Archive in DEMO REPLAY mode. Our backend possesses fully architected adapters for eRTMAC, WITSML 1.4.1.1, and WITS0, but live rig connectivity is never fabricated without approved on-site credentials."* |
| **"Can NWIS autonomously adjust rig drawworks or mud pumps?"** | *"Never. Our advisory safety banner explicitly states that autonomous actuation is prohibited. NWIS is an engineering decision-support tool. All parameter adjustments require licensed drilling engineer review."* |
| **"How do you prevent RAG hallucinations in technical answers?"** | *"The Context Builder enforces strict cosine-similarity thresholds, spatial radius bounding, and formation filtering. Answers are synthesized exclusively from approved `EVID-*` chunks. When evidence is insufficient, the system explicitly reports insufficient evidence rather than guessing."* |
| **"Does the platform scale beyond CSV demo files?"** | *"Yes. NWIS features dual-mode persistence. It runs standalone on high-speed CSV repositories for demonstration and switches seamlessly to enterprise PostgreSQL 16 with PostGIS spatial indexing for multi-basin production scale."* |
