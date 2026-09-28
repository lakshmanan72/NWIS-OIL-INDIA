# NWIS — Nearby Wells Intelligence System

> **Evidence-Backed Drilling Risk Intelligence Platform**  
> *Smart India Hackathon (SIH 2026) | Problem Statement by Oil India Limited (OIL)*

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3+-61DAFB.svg?logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-5.4+-646CFF.svg?logo=vite&logoColor=white)](https://vitejs.dev)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue.svg?logo=python&logoColor=white)](https://www.python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%2B%20PostGIS-336791.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![License](https://img.shields.io/badge/License-Proprietary%20%2F%20SIH%20Evaluation-orange.svg)](#33-license)

---

## 1. Project Overview

**NWIS (Nearby Wells Intelligence System)** is an evidence-backed drilling risk intelligence platform designed to help drilling engineers analyze historical wells, identify comparable offset wells, detect historical risk zones, and receive traceable early-warning insights during drilling operations.

NWIS aggregates canonical well records across India's sedimentary basins, synthesizes historical Well Completion Reports (WCR) and Daily Drilling Reports (DDR), trains calibrated machine learning models across critical drilling hazards, and fuses real-time telemetry with historical offset memory to provide actionable decision support at the drill-rig floor and remote monitoring centers.

> **Operational Scope Notice**: NWIS is advisory decision-support software. It does **not** autonomously control drilling equipment or blowout preventers (BOPs). All operational interventions remain under the direct command of certified drilling engineers and rig superintendents.

---

## 2. Problem Statement

Drilling complex hydrocarbons and exploratory wells entails severe operational hazards, including:
- **Catastrophic Mud Loss & Lost Circulation** into depleted or fractured formations.
- **Differential & Mechanical Stuck Pipe** causing millions in non-productive time (NPT).
- **Influx / Well Kicks** leading to severe well-control situations if unmitigated.
- **Overpressure Formations & Narrow Mud Weight Windows** triggering wellbore collapse or blowouts.
- **Torque & Drag Spikes / Bit Balling** compromising drill string integrity.

During live drilling, engineers routinely operate with fragmented offset-well data buried across physical paper archives, unstructured PDFs, and disparate databases. Synthesizing relevant offset hazards for an ongoing bit depth within seconds is virtually impossible manually.

---

## 3. Solution

NWIS solves this challenge through a multi-tiered, closed-loop intelligence architecture:
1. **Interactive Spatial Map**: Visualizes canonical exploration and production wells across India with fast clustering, basin/field filtering, and spatial radius search.
2. **Twin Well Engine**: Calculates multi-attribute offset similarity across geographical proximity, total vertical depth (TVD), stratigraphic formations, trajectory, and lithology.
3. **Risk-Ahead Engine**: Evaluates hazards ahead of the drill bit ($+50\text{ m}$ to $+300\text{ m}$) based on historical offset events.
4. **Calibrated Machine Learning Models**: Evaluates continuous hazard probabilities for Stuck Pipe, Mud Loss, Kick, Overpressure, and Torque Spikes.
5. **Traceable Document AI & RAG**: Ingests unstructured WCR/DDR documents with OCR, regex extraction, confidence scoring, approval gating, and semantic search with strict provenance.
6. **Real-Time Telemetry & Anomaly Engine**: Ingests live or simulated WITSML / eRTMAC feeds, computes rolling telemetry trends, detects anomalies, and fires tiered early-warning alerts.

---

## 4. Key Features

- **Spatial Intelligence**: PostGIS-accelerated geospatial nearest-neighbor and radius search across 15,108 canonical wells.
- **Multi-Factor Twin Well Matching**: Weighted distance, formation overlap, mud weight profile correlation, and depth bracket alignment.
- **Multi-Hazard ML Ensemble**: CatBoost, Random Forest, and XGBoost classifiers calibrated with class-imbalance mitigations and validation-only threshold tuning.
- **Risk-Ahead Early Warning**: Proactive warnings prior to penetrating known depleted or overpressured stratigraphic markers.
- **Evidence-Grounded Engineering Copilot**: Semantic RAG with vector retrieval, multi-factor reranking, prompt injection defense, and source citation traceability.
- **WCR/DDR Ingestion Pipeline**: Extracts well name, operator, spud date, total depth, casing points, lithological tops, and recorded drilling events with confidence validation.
- **Operational Approval Gate**: Staging area requiring human engineer sign-off before newly extracted document events merge into the permanent knowledge base.
- **Role-Based Access Control (RBAC)**: Secure JWT authentication with defined roles: `ADMIN`, `DRILLING_ENGINEER`, `GEOLOGIST`, and `VIEWER`.

---

## 5. NWIS Workflow

### Real-Time & Planning Decision Workflow
```
Engineer
   ↓
Current Well
   ↓
Geological Context
   ↓
Nearby / Similar Wells
   ↓
Twin Well Engine
   ↓
Historical Drilling Events
   ↓
Risk Zone Detection
   ↓
Current Drilling Depth
   ↓
Risk-Ahead Engine
   ↓
Evidence Fusion
   ↓
Alert
   ↓
Engineer Review
```

### Document Upload & Ingestion Workflow
```
Engineer uploads WCR/DDR
   ↓
Document validation
   ↓
PDF extraction / OCR
   ↓
Structured event extraction
   ↓
Extraction confidence
   ↓
Well identification
   ↓
Depth / formation / event extraction
   ↓
Database update
   ↓
Geospatial well placement
   ↓
Historical intelligence
   ↓
Risk analysis
```

---

## 6. System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        NWIS FRONTEND (React 18 + Vite)                │
│   Interactive Map  │  Twin Well  │  Live Ops  │  Copilot  │  WCR Review │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / WebSocket REST API
┌───────────────────────────────────▼────────────────────────────────────┐
│                        NWIS BACKEND (FastAPI + Python)                 │
│  ┌───────────────────────┐  ┌───────────────────┐  ┌────────────────┐  │
│  │   Twin Well Engine    │  │  Risk-Ahead Engine│  │ Alert Engine   │  │
│  └───────────────────────┘  └───────────────────┘  └────────────────┘  │
│  ┌───────────────────────┐  ┌───────────────────┐  ┌────────────────┐  │
│  │  ML Hazard Predictor  │  │  Document AI / OCR│  │ Telemetry Svc  │  │
│  └───────────────────────┘  └───────────────────┘  └────────────────┘  │
│  ┌───────────────────────┐  ┌───────────────────┐  ┌────────────────┐  │
│  │  Auth & RBAC (JWT)    │  │  Audit Logger     │  │ Data Store Svc │  │
│  └───────────────────────┘  └───────────────────┘  └────────────────┘  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
       ┌────────────────────────────┼────────────────────────────┐
       ▼                            ▼                            ▼
┌──────────────────┐       ┌──────────────────┐        ┌──────────────────┐
│  PostgreSQL 16   │       │  Local File Data │        │ Industrial Feeds │
│   + PostGIS 3.4  │       │  Canonical CSVs  │        │ (eRTMAC/WITSML)  │
│   (pgvector)     │       │  Models & Config │        │ Simulated / Live │
└──────────────────┘       └──────────────────┘        └──────────────────┘
```

---

## 7. Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React 18, Vite 5, Tailwind CSS, Leaflet, leaflet.markercluster, Lucide React, React Router 7 |
| **Backend API** | FastAPI, Uvicorn, Pydantic v2, Python 3.11 / 3.12 / 3.13 |
| **Databases** | PostgreSQL 16 + PostGIS 3.4, SQLAlchemy, Alembic, SQLite fallback |
| **Machine Learning** | Scikit-learn, CatBoost, XGBoost, SHAP, Joblib, Pandas, NumPy |
| **Document AI & RAG**| PyPDF, Tesseract OCR, Sentence-Transformers / TF-IDF, NumPy vector store |
| **Security & Auth** | PyJWT, Passlib (Argon2 / BCrypt), Cryptography, HTTP Bearer tokens |
| **Containerization** | Docker, Docker Compose, Nginx Alpine reverse proxy |

---

## 8. AI/ML Components

NWIS incorporates trained supervised models predicting five operational hazards:
1. **Kick / Formation Influx**: CatBoost classifier trained on differential standpipe pressure, gas units, flow-out changes, and mud weight margins.
2. **Mud Loss / Lost Circulation**: Calibrated Random Forest detecting fractures, permeability steps, and severe mud weight imbalances.
3. **Overpressure Formation**: CatBoost model tracking abnormal ROP surges, connection gas spikes, and drillability trends.
4. **Stuck Pipe**: XGBoost classifier detecting torque fluctuations, drag trends, and lithological transitions.
5. **Torque Spikes & Bit Balling**: XGBoost model identifying mechanical instability and string vibration signatures.

### Rigorous ML Methodology
- **Zero Train-Test Contamination**: Stratified well-grouped splits prevent identical well leakage between training and validation folds.
- **Validation-Only Threshold Selection**: Decision thresholds are tuned on held-out validation sets to balance Recall and Precision under severe class imbalance without test set overfitting.
- **Explainable AI (SHAP)**: Models output local feature contribution scores highlighting which telemetry channels elevated risk.

---

## 9. RAG Architecture

The Institutional Memory Copilot combines domain-specific retrieval-augmented generation:
- **Chunking Engine**: Hierarchical section-aware parsing of completion summaries, geological logs, and daily morning reports.
- **Vector Index**: Dense embedding representations coupled with lexical keyword matching.
- **Multi-Factor Reranker**: Adjusts retrieval rankings by geographic proximity, depth alignment, and formation relevance to the active query well.
- **Citation Validator**: Grounding checks verify that every generated claim contains explicit references to source document IDs, pages, and historical depth intervals.
- **Security Guardrails**: Input sanitizer defends against prompt injection and instruction overrides.

---

## 10. Twin Well Engine

The Twin Well Engine identifies the most informative historical offset wells for an ongoing drilling operation:
- **Spatial Weight ($W_{geo}$)**: Haversine / PostGIS geodesic distance from current surface or bottom-hole location.
- **Depth Alignment ($W_{depth}$)**: Total depth and target formation reach parity.
- **Stratigraphic Stratum Match ($W_{strat}$)**: Jaccard overlap of penetrated geological formations.
- **Lithological Similarity ($W_{litho}$)**: Lithology profile correlation across identical depth slices.
- **Composite Score**: Outputs a ranked list of offset wells with explicit breakdown of similarity factors.

---

## 11. Risk-Ahead Engine

As the drill bit advances:
1. Computes the active bit depth (e.g., $2,450\text{ m}$).
2. Scans offset twin wells across the forward lookahead window ($[2,450\text{ m}, 2,650\text{ m}]$).
3. Identifies historical drilling events (e.g., severe losses at $2,510\text{ m}$ in offset well *NHK-542* within Barail formation).
4. Synthesizes risk alerts advising casing shoe confirmation, mud weight adjustment, or lost circulation material (LCM) pre-staging.

---

## 12. Evidence-Backed Alert Engine

Alerts in NWIS conform to strict evidence levels:
- **CRITICAL**: Immediate hazard detected by both live telemetry anomaly AND historical offset precedent within $\pm 25\text{ m}$.
- **WARNING**: Impending hazard identified ahead of bit by offset correlation or elevated ML probability.
- **ADVISORY**: Lithological boundary approach or routine parameter shift.
- Every alert includes:
  - Triggering criteria.
  - Affected depth bracket.
  - Source offset well IDs and report citations.
  - Recommended mitigation protocol.

---

## 13. WCR / DDR Document Upload and Extraction

- **Document Ingestion**: Supports PDF uploads of historical Well Completion Reports and Daily Drilling Reports.
- **Extraction Pipeline**:
  - Text layer extraction with OCR fallback for scanned legacy logs.
  - Entity recognition for well metadata (operator, spud date, total depth, basin, block).
  - Formation tops and event log extraction.
  - Extraction confidence scoring ($0.0 - 1.0$).
- **Human-in-the-Loop Review**: Extracted entries remain in a staging gate until reviewed and approved by an authorized engineer before persisting to the production well catalog.

---

## 14. Interactive India Well Map

- Interactive Leaflet-based geospatial visualization centered across India.
- Dynamic clustering supporting smooth performance across 15,100+ well markers.
- Filter by basin (Assam-Arakan, Cambay, Rajasthan, Krishna-Godavari, Mumbai Offshore, Cauvery).
- Filter by operator (Oil India Limited, ONGC, etc.).
- Radius query tool: Click any point to retrieve all historical wells within a designated radius ($1\text{ km} - 50\text{ km}$).

---

## 15. Historical Drilling Event Analysis

Historical events are cataloged under standardized taxonomy:
- `MUD_LOSS`: Minor seepages to catastrophic total lost circulation.
- `STUCK_PIPE`: Differential sticking, mechanical pack-off, and key seating.
- `WELL_KICK`: Gas or water influx requiring shut-in and kill procedures.
- `OVERPRESSURE`: Transition zones requiring mud weight elevation.
- `EQUIPMENT_FAILURE`: Twist-offs, MWD failure, bit nozzle plugging.

---

## 16. Risk Zone Identification

Geological formations are automatically mapped into depth-based risk zones based on empirical incident density:
- **Depth Interval Risk Density**: Event frequency per 100 meters.
- **Formation Hazard Profiling**: Aggregated risk profiles for key formations (e.g., Barail Coal-Shale, Tipam Sandstone, Kopili Formation).
- **Hazard Co-occurrence**: Correlation between high-permeability sands and adjacent overpressured shales.

---

## 17. Real-Time Drilling Feed (Live & Simulated)

NWIS supports dual-mode telemetry processing:
- **Live Stream**: Ingests WITS0 / WITSML / eRTMAC time-series packets over TCP/HTTP.
- **Deterministic Rig Simulator**: Replays high-resolution historical telemetry logs to simulate active drilling runs with real-time parameter streaming:
  - Measured Depth (MD) & True Vertical Depth (TVD)
  - Rate of Penetration (ROP)
  - Weight on Bit (WOB)
  - Rotary Table / Top Drive RPM & Torque
  - Flow In / Flow Out & Standpipe Pressure (SPP)
  - Pit Volume & Total Gas Readings

---

## 18. Database Architecture

NWIS employs a dual-storage strategy optimized for development simplicity and production scalability:

1. **Relational / Spatial (PostgreSQL 16 + PostGIS 3.4)**:
   - `users`: Credentials, RBAC roles, audit timestamps.
   - `wells`: Canonical well identifiers, coordinates (`GEOMETRY(Point, 4326)`), elevation, field, basin.
   - `well_geology` & `formation_lithology`: Stratigraphic columns and lithological markers.
   - `historical_events`: Standardized incident logs referenced by well ID and depth.
   - `document_metadata` & `document_chunks`: Ingested PDF records with vector embeddings.
   - `telemetry_records`: Time-series sensor packets with spatial indexes.
2. **File-Based Engine (Development Default)**:
   - Automated fallback to optimized Pandas / NumPy / JSON stores for rapid local testing without external database dependencies.

---

## 19. Security / RBAC

- **Authentication**: JWT Bearer tokens signed with HS256 / RS256 algorithms.
- **RBAC Matrix**:
  - `ADMIN`: Full administrative control, user provisioning, system configuration.
  - `DRILLING_ENGINEER`: Full access to live operations, ML prediction, risk-ahead alerts, WCR upload.
  - `GEOLOGIST`: Access to geological mapping, twin well analysis, formation correlation, document review.
  - `VIEWER`: Read-only access to map visualization, published well summaries, and historical archives.
- **Audit Logging**: Structured security audit log records every login, document review, and telemetry state transition.
- **No Hardcoded Secrets**: Configuration is managed strictly via environment variables.

---

## 20. Installation

### Prerequisites
- **Python**: Version 3.11, 3.12, or 3.13
- **Node.js**: Version 18.x or 20.x with `npm`
- **Git**: Installed and accessible in PATH
- *(Optional)* **Docker & Docker Compose**: For containerized deployment

### Repository Setup
```bash
# Clone the repository
git clone https://github.com/<USERNAME>/<REPOSITORY>.git
cd "sih well"

# Create Python Virtual Environment (recommended)
python -m venv .venv

# Activate Virtual Environment:
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Windows (CMD):
.venv\Scripts\activate.bat
# On Linux/macOS:
source .venv/bin/activate

# Install Backend Dependencies
pip install -r backend/requirements.txt

# Install Frontend Dependencies
cd frontend
npm install
cd ..
```

---

## 21. Environment Configuration

Copy the example environment configuration to `.env`:
```bash
cp .env.example .env
```

Key environment settings:
```ini
ENVIRONMENT=development
DATA_BACKEND=csv             # 'csv' for local development, 'postgres' for production
DATABASE_URL=                # Set when DATA_BACKEND=postgres
JWT_SECRET=your_secure_random_jwt_secret_min_32_chars
LOG_LEVEL=INFO

# Industrial Connectors (Optional / Inactive by default)
ERTMAC_ENABLED=false
WITSML_ENABLED=false
```

---

## 22. Running Backend

Start the FastAPI application server:
```bash
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

- API Base URL: `http://127.0.0.1:8000`
- Interactive Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc Documentation: `http://127.0.0.1:8000/redoc`
- Health Check: `http://127.0.0.1:8000/health`

---

## 23. Running Frontend

Start the React/Vite development server:
```bash
cd frontend
npm run dev
```

- Frontend Application: `http://127.0.0.1:5173`
- Well Map View: `http://127.0.0.1:5173/`
- Well Intelligence: `http://127.0.0.1:5173/well-intelligence`
- Live Operations: `http://127.0.0.1:5173/live-operations`
- Institutional Memory: `http://127.0.0.1:5173/institutional-memory`
- WCR Upload & Review: `http://127.0.0.1:5173/upload-wcr`

### All-in-One Launcher (Windows PowerShell)
You can launch both backend and frontend servers with pre-flight port checks using:
```powershell
.\start_nwis.ps1
```

---

## 24. Docker Deployment

NWIS includes a multi-container Docker Compose configuration containing PostgreSQL/PostGIS, the FastAPI backend, and an Nginx-served frontend build.

```bash
# Build and start all services
docker compose up --build -d

# View service logs
docker compose logs -f

# Shut down services
docker compose down
```

| Service | Port | Endpoint |
| :--- | :--- | :--- |
| **Frontend (Nginx)** | `80` | `http://localhost/` |
| **Backend (FastAPI)**| `8000` | `http://localhost:8000/` |
| **PostgreSQL / PostGIS** | `5432` | `localhost:5432` |

---

## 25. Dataset Structure

| Dataset File | Records | Classification | Content Description |
| :--- | :--- | :--- | :--- |
| `nwis_well_locations_15108_new.csv` | 15,108 | Real Public | Canonical well master: names, coordinates, operators, basins, depths. |
| `nwis_well_geology_15108.csv` | 15,108 | Historical | Primary geological tops, formation markers, basin stratigraphy. |
| `nwis_formation_lithology_15108.csv` | Multi-layer | Historical | Lithological classifications, rock types, depth intervals. |
| `nwis_historical_drilling_events_15108.csv`| Multi-event | Historical | Historical incident logs: losses, kicks, stuck pipe, overpressure. |
| `nwis_daily_drilling_parameters_15108.csv` | 16,939 | Operational | Time-series daily drilling logs (WOB, ROP, torque, mud weight). |
| `nwis_document_metadata_15108.csv` | Catalogs | Metadata | Document catalog linking reports to canonical well IDs. |
| `nwis_spatial_well_relationships_15108.csv`| Matrix | Precomputed | Pairwise geodesic distances between nearby wells. |
| `nwis_risk_recommendations.csv` | Ruleset | Expert Rules | Mitigative operational guidelines mapped to specific hazard classes. |
| `nwis_mud_logging_15108_wells.csv` *(local)* | 453,240 | Telemetry | High-frequency sensor log (gas, pit levels). Kept locally due to size (126 MB). |

### Data Provenance & Integrity
- **Real Public Data**: Coordinates, well names, and operators originate from public exploratory well registries across Indian sedimentary basins.
- **Simulated & Demo Data**: Streaming telemetry and demonstration test PDFs are deterministically generated to demonstrate system workflows without compromising proprietary operator feeds.

---

## 26. Project Directory Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI routers (wells, risk, documents, auth, realtime)
│   │   ├── core/            # Observability and logging configuration
│   │   ├── db/              # SQLAlchemy models, sessions, connection pooling
│   │   ├── integrations/    # eRTMAC, WITSML, WITS0 industrial telemetry adapters
│   │   ├── models/          # Pydantic data schemas
│   │   ├── realtime/        # Live streaming engine, anomaly detection, alert engine
│   │   ├── repositories/    # Data persistence layer (PostgreSQL & CSV abstraction)
│   │   ├── security/        # JWT authentication, password hashing, audit log
│   │   ├── services/        # Business logic (Twin Well, Risk Ahead, Offset Intel)
│   │   └── main.py          # FastAPI application entry point
│   ├── document_ai/         # WCR/DDR parsing, OCR, vector store, semantic RAG
│   ├── migrations/          # Alembic database migration scripts
│   ├── ml/                  # ML training, feature engineering, SHAP explainability
│   ├── requirements.txt     # Python backend dependencies
│   └── tests/               # Backend test suite (pytest)
├── database/
│   └── schema/              # PostgreSQL 16 + PostGIS initialization DDL (01_init.sql)
├── data/                    # Canonical datasets, reports, taxonomies, metadata
│   └── raw/                 # Canonical CSV data files
├── docs/                    # Architectural specifications and phase validation reports
├── frontend/
│   ├── public/              # Static brand assets and icons
│   ├── src/
│   │   ├── components/      # React UI components (MapControls, RiskPanel, Search)
│   │   ├── pages/           # Application views (WellMap, Intelligence, LiveOps, etc.)
│   │   ├── App.jsx          # Route configuration
│   │   └── main.jsx         # React application entry point
│   ├── package.json         # Node.js dependencies and build scripts
│   ├── tailwind.config.js   # Tailwind styling configuration
│   └── vite.config.js       # Vite build configuration
├── models/                  # Trained Joblib ML model artifacts (CatBoost, RF, XGBoost)
├── scripts/                 # Operational, migration, and launcher utility scripts
├── .env.example             # Environment template (NO SECRETS)
├── .gitignore               # Comprehensive Git ignore rules
├── docker-compose.yml       # Production multi-container composition
├── Dockerfile.backend       # Production backend container definition
├── Dockerfile.frontend      # Production frontend container definition
├── nginx.conf               # Reverse proxy configuration
├── start_nwis.ps1           # Interactive development launcher
└── README.md                # System documentation
```

---

## 27. API Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Service health status and database connectivity check |
| `GET` | `/api/wells` | Paginated well query with state, basin, and operator filters |
| `GET` | `/api/wells/count` | Total active well count from the database |
| `GET` | `/api/wells/map-markers` | Clustered coordinate points for Leaflet map rendering |
| `GET` | `/api/wells/{well_id}` | Detailed well profile, geology, and history |
| `GET` | `/api/wells/{well_id}/nearby` | Geospatial nearest-neighbor offset wells within radius |
| `GET` | `/api/wells/{well_id}/twin-wells`| Multi-factor ranked twin offset wells |
| `POST`| `/api/prediction/predict` | ML hazard prediction for active drilling parameters |
| `GET` | `/api/prediction/explain` | Local SHAP feature importance breakdown |
| `POST`| `/api/documents/upload` | Upload WCR / DDR PDF for OCR & entity extraction |
| `GET` | `/api/documents/review-queue` | Staging queue of extracted events awaiting approval |
| `POST`| `/api/documents/approve/{id}` | Approve extracted events into the historical knowledge base |
| `POST`| `/api/intelligence/query` | Grounded Engineering Copilot question answering |
| `POST`| `/api/realtime/stream/start` | Start live telemetry stream / rig playback |
| `GET` | `/api/realtime/live-state` | Active drilling depth, parameters, and risk state |
| `GET` | `/api/realtime/alerts/active` | Active early-warning risk alerts |
| `POST`| `/api/auth/token` | User login to receive JWT Bearer token |

---

## 28. Evaluation / Backtesting

The machine learning models and spatial intelligence engines were validated using historical operational data:
- **Spatial Accuracy**: Haversine distance computations verified against PostGIS `ST_DistanceSphere` with sub-meter tolerance.
- **Stratigraphic Consistency**: Offset formation tops validated against basin stratigraphy tables.
- **Hazard Detection Calibration**: Probability scores calibrated with Platt scaling / isotonic regression on held-out validation sets.
- **System Performance Benchmarking**:
  - Marker clustering endpoint response time: $< 45\text{ ms}$.
  - Twin well ranking computation: $< 30\text{ ms}$.
  - Real-time telemetry processing throughput: $> 500\text{ packets/sec}$.
  - End-to-end alert latency: $< 200\text{ ms}$ from telemetry event to alert dispatch.

---

## 29. Important Evidence Policy

To prevent generative hallucinations and ensure drilling crew safety, NWIS enforces an explicit **Evidence Policy**:
1. **No Hallucinated Drilling Incidents**: The LLM Copilot is prohibited from generating ungrounded historical events. All returned events must link to a valid document chunk ID, page number, and offset well identifier.
2. **Confidence-Gated Ingestion**: Extracted records with confidence below $0.70$ are flagged for mandatory manual engineer review.
3. **Traceable Recommendations**: Operational risk alerts cite specific historical offset well events as their empirical justification.

---

## 30. Limitations

- **Public Coordinate Resolution**: Exploration well coordinates are derived from public datasets and approximate to surface wellhead locations; deviation surveys must be verified against official well plans.
- **Model Generalization**: ML models reflect operational patterns in Indian sedimentary basins (e.g., Upper Assam, Cambay, KG); adaptation to novel geological settings requires retraining on local formation logs.
- **Advisory Role**: NWIS does not execute physical rig control or override rig safety instrumented systems (SIS).

---

## 31. Future Enhancements

- **Direct WITSML 2.1 ETP (Energistics Transfer Protocol)**: Real-time bi-directional WebSocket streaming directly from rig-floor telemetry servers.
- **3D Subsurface Trajectory Visualizer**: Three-dimensional WebGL wellbore collision and proximity viewer.
- **Automated Anti-Collision Scanning**: Real-time 3D ellipse-of-uncertainty calculations for high-density multi-well pads.
- **Automated Daily Drilling Report (DDR) Summarization**: Multi-lingual NLP parsing of field hand-written logs in regional languages.

---

## 32. SIH Project Context

- **Event**: Smart India Hackathon (SIH 2026)
- **Problem Statement Title**: Development of Nearby Wells Intelligence System (NWIS) for Enhanced Drilling Risk Assessment and Decision Support
- **Organization**: Oil India Limited (OIL), Ministry of Petroleum and Natural Gas, Government of India
- **Core Focus**: Transforming archival well reports and real-time drilling telemetry into predictive, traceable, early-warning intelligence to reduce NPT and prevent wellbore disasters.

---

## 33. License

This repository is submitted as part of the **Smart India Hackathon (SIH 2026)** evaluation.  
All rights reserved by the development team and the submitting institution, subject to SIH and Oil India Limited evaluation guidelines.
