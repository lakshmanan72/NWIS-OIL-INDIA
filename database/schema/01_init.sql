-- ============================================================
-- NWIS PHASE 7: PRODUCTION DATABASE INITIALIZATION SCHEMA
-- PostgreSQL 16 + PostGIS 3.4
-- ============================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- 1. USERS & RBAC
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    email VARCHAR(128) UNIQUE NOT NULL,
    hashed_password VARCHAR(256) NOT NULL,
    full_name VARCHAR(128),
    role VARCHAR(32) NOT NULL DEFAULT 'VIEWER', -- ADMIN, DRILLING_ENGINEER, GEOLOGIST, VIEWER
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- ============================================================
-- 2. CANONICAL WELLS
-- ============================================================
CREATE TABLE IF NOT EXISTS wells (
    id SERIAL PRIMARY KEY,
    well_id VARCHAR(32) UNIQUE NOT NULL,
    well_name VARCHAR(128) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL CHECK (latitude >= -90.0 AND latitude <= 90.0),
    longitude DOUBLE PRECISION NOT NULL CHECK (longitude >= -180.0 AND longitude <= 180.0),
    state VARCHAR(64),
    district VARCHAR(64),
    field VARCHAR(128),
    block VARCHAR(128),
    basin VARCHAR(128),
    operator VARCHAR(128),
    status VARCHAR(64),
    well_type VARCHAR(64),
    trajectory_type VARCHAR(64),
    total_depth DOUBLE PRECISION CHECK (total_depth IS NULL OR total_depth >= 0.0),
    spud_date VARCHAR(32),
    completion_date VARCHAR(32),
    source VARCHAR(64) DEFAULT 'REAL_PUBLIC',
    is_canonical BOOLEAN DEFAULT TRUE,
    is_new_well BOOLEAN DEFAULT FALSE,
    geom GEOGRAPHY(Point, 4326),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wells_well_id ON wells(well_id);
CREATE INDEX IF NOT EXISTS idx_wells_operator ON wells(operator);
CREATE INDEX IF NOT EXISTS idx_wells_field ON wells(field);
CREATE INDEX IF NOT EXISTS idx_wells_basin ON wells(basin);
CREATE INDEX IF NOT EXISTS idx_wells_geom ON wells USING GIST(geom);

-- ============================================================
-- 3. GEOLOGY & STRATIGRAPHY
-- ============================================================
CREATE TABLE IF NOT EXISTS well_geology (
    id SERIAL PRIMARY KEY,
    well_id VARCHAR(32) NOT NULL REFERENCES wells(well_id) ON DELETE CASCADE,
    formation_name VARCHAR(128),
    lithology VARCHAR(128),
    depth_from DOUBLE PRECISION,
    depth_to DOUBLE PRECISION,
    thickness DOUBLE PRECISION,
    description TEXT,
    source VARCHAR(64) DEFAULT 'REGIONAL_SURVEY',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_geology_well_id ON well_geology(well_id);
CREATE INDEX IF NOT EXISTS idx_geology_depth ON well_geology(well_id, depth_from, depth_to);
CREATE INDEX IF NOT EXISTS idx_geology_formation ON well_geology(formation_name);

CREATE TABLE IF NOT EXISTS well_formations (
    id SERIAL PRIMARY KEY,
    well_id VARCHAR(32) NOT NULL REFERENCES wells(well_id) ON DELETE CASCADE,
    formation_name VARCHAR(128) NOT NULL,
    top_depth_md DOUBLE PRECISION,
    bottom_depth_md DOUBLE PRECISION,
    age_era VARCHAR(64),
    permeability_class VARCHAR(64),
    source VARCHAR(64),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_formations_well_id ON well_formations(well_id);
CREATE INDEX IF NOT EXISTS idx_formations_top_depth ON well_formations(well_id, top_depth_md);

-- ============================================================
-- 4. HISTORICAL DRILLING EVENTS
-- ============================================================
CREATE TABLE IF NOT EXISTS historical_events (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(64) UNIQUE,
    well_id VARCHAR(32) NOT NULL REFERENCES wells(well_id) ON DELETE CASCADE,
    event_type VARCHAR(64) NOT NULL,
    event_subtype VARCHAR(64),
    depth_md DOUBLE PRECISION,
    depth_from DOUBLE PRECISION,
    depth_to DOUBLE PRECISION,
    severity VARCHAR(32), -- CRITICAL, HIGH, MEDIUM, LOW
    description TEXT,
    source_document_id VARCHAR(64),
    event_date VARCHAR(32),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_well_id ON historical_events(well_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON historical_events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_depth ON historical_events(depth_md);
CREATE INDEX IF NOT EXISTS idx_events_severity ON historical_events(severity);

-- ============================================================
-- 5. DAILY DRILLING PARAMETERS
-- ============================================================
CREATE TABLE IF NOT EXISTS daily_drilling_parameters (
    id SERIAL PRIMARY KEY,
    well_id VARCHAR(32) NOT NULL REFERENCES wells(well_id) ON DELETE CASCADE,
    recorded_date VARCHAR(32),
    depth_md DOUBLE PRECISION,
    progress_m DOUBLE PRECISION,
    wob_klbf DOUBLE PRECISION,
    rpm DOUBLE PRECISION,
    rop_m_hr DOUBLE PRECISION,
    torque_kftlb DOUBLE PRECISION,
    standpipe_pressure_psi DOUBLE PRECISION,
    flow_rate_gpm DOUBLE PRECISION,
    mud_weight_ppg DOUBLE PRECISION,
    operation_summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_daily_well_depth ON daily_drilling_parameters(well_id, depth_md);
CREATE INDEX IF NOT EXISTS idx_daily_well_date ON daily_drilling_parameters(well_id, recorded_date);

-- ============================================================
-- 6. MUD LOGGING (HIGH FREQUENCY)
-- ============================================================
CREATE TABLE IF NOT EXISTS mud_logging (
    id BIGSERIAL PRIMARY KEY,
    well_id VARCHAR(32) NOT NULL REFERENCES wells(well_id) ON DELETE CASCADE,
    depth_md DOUBLE PRECISION NOT NULL,
    recorded_at VARCHAR(32),
    total_gas_units DOUBLE PRECISION,
    c1_methane_ppm DOUBLE PRECISION,
    c2_ethane_ppm DOUBLE PRECISION,
    c3_propane_ppm DOUBLE PRECISION,
    ic4_isobutane_ppm DOUBLE PRECISION,
    nc4_normalbutane_ppm DOUBLE PRECISION,
    c5_pentane_ppm DOUBLE PRECISION,
    flow_show_pct DOUBLE PRECISION,
    pit_volume_m3 DOUBLE PRECISION,
    lithology_observed VARCHAR(128),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mudlog_well_depth ON mud_logging(well_id, depth_md);
CREATE INDEX IF NOT EXISTS idx_mudlog_well_rec ON mud_logging(well_id, recorded_at);

-- ============================================================
-- 7. WCR & COMPLETION DATA
-- ============================================================
CREATE TABLE IF NOT EXISTS well_completion_wcr (
    id SERIAL PRIMARY KEY,
    well_id VARCHAR(32) NOT NULL REFERENCES wells(well_id) ON DELETE CASCADE,
    document_id VARCHAR(64),
    casing_size_inch DOUBLE PRECISION,
    casing_depth_m DOUBLE PRECISION,
    tubing_size_inch DOUBLE PRECISION,
    perforation_interval_top_m DOUBLE PRECISION,
    perforation_interval_bottom_m DOUBLE PRECISION,
    reservoir_name VARCHAR(128),
    initial_production_oil_bopd DOUBLE PRECISION,
    initial_production_gas_mscfd DOUBLE PRECISION,
    initial_reservoir_pressure_psi DOUBLE PRECISION,
    completion_type VARCHAR(64),
    approval_status VARCHAR(32) DEFAULT 'REVIEW_REQUIRED',
    raw_payload_json JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wcr_well_id ON well_completion_wcr(well_id);
CREATE INDEX IF NOT EXISTS idx_wcr_doc_id ON well_completion_wcr(document_id);

-- ============================================================
-- 8. DOCUMENTS, EXTRACTIONS & RAG CHUNKS
-- ============================================================
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(64) UNIQUE NOT NULL,
    filename VARCHAR(256) NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    well_id VARCHAR(32),
    document_type VARCHAR(64), -- WCR, DDR, MUD_LOG, COMPLETION_REPORT
    approval_status VARCHAR(32) NOT NULL DEFAULT 'REVIEW_REQUIRED', -- REVIEW_REQUIRED, APPROVED, REJECTED, UNMATCHED_WELL
    page_count INTEGER DEFAULT 1,
    file_size_bytes BIGINT,
    uploaded_by VARCHAR(64),
    approved_by VARCHAR(64),
    approved_at TIMESTAMPTZ,
    metadata_json JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_docs_doc_id ON documents(document_id);
CREATE INDEX IF NOT EXISTS idx_docs_well_id ON documents(well_id);
CREATE INDEX IF NOT EXISTS idx_docs_status ON documents(approval_status);

CREATE TABLE IF NOT EXISTS document_chunks (
    id SERIAL PRIMARY KEY,
    chunk_id VARCHAR(64) UNIQUE NOT NULL,
    document_id VARCHAR(64) NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    well_id VARCHAR(32),
    page_number INTEGER,
    section_name VARCHAR(128),
    chunk_text TEXT NOT NULL,
    formation VARCHAR(128),
    depth_from DOUBLE PRECISION,
    depth_to DOUBLE PRECISION,
    event_type VARCHAR(64),
    approval_status VARCHAR(32) NOT NULL DEFAULT 'REVIEW_REQUIRED',
    embedding_vector JSONB, -- fallback when pgvector is not loaded
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_chunk_id ON document_chunks(chunk_id);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_well_id ON document_chunks(well_id);
CREATE INDEX IF NOT EXISTS idx_chunks_status ON document_chunks(approval_status);

-- ============================================================
-- 9. RISK RECOMMENDATIONS (DECISION SUPPORT)
-- ============================================================
CREATE TABLE IF NOT EXISTS risk_recommendations (
    id SERIAL PRIMARY KEY,
    risk_id VARCHAR(64) UNIQUE,
    well_id VARCHAR(32) NOT NULL REFERENCES wells(well_id) ON DELETE CASCADE,
    hazard_type VARCHAR(64) NOT NULL,
    risk_score DOUBLE PRECISION NOT NULL,
    risk_level VARCHAR(32) NOT NULL,
    predicted_event VARCHAR(128),
    confidence DOUBLE PRECISION,
    recommended_action TEXT,
    supporting_event_id VARCHAR(64),
    model_version VARCHAR(32) DEFAULT 'nwis-v1.0',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risks_well_id ON risk_recommendations(well_id);
CREATE INDEX IF NOT EXISTS idx_risks_hazard ON risk_recommendations(hazard_type);

-- ============================================================
-- 10. REALTIME TELEMETRY & LIVE STATE
-- ============================================================
CREATE TABLE IF NOT EXISTS telemetry_records (
    id BIGSERIAL PRIMARY KEY,
    well_id VARCHAR(32) NOT NULL REFERENCES wells(well_id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ NOT NULL,
    depth_md DOUBLE PRECISION NOT NULL,
    rop DOUBLE PRECISION,
    wob DOUBLE PRECISION,
    rpm DOUBLE PRECISION,
    torque DOUBLE PRECISION,
    spp DOUBLE PRECISION,
    mud_flow_in DOUBLE PRECISION,
    mud_flow_out DOUBLE PRECISION,
    gas DOUBLE PRECISION,
    pump_pressure DOUBLE PRECISION,
    hookload DOUBLE PRECISION,
    source VARCHAR(64) DEFAULT 'eRTMAC',
    quality_status VARCHAR(32) DEFAULT 'GOOD',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_telem_well_time ON telemetry_records(well_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_telem_well_depth ON telemetry_records(well_id, depth_md);
CREATE INDEX IF NOT EXISTS idx_telem_time ON telemetry_records(timestamp DESC);

CREATE TABLE IF NOT EXISTS well_live_state (
    well_id VARCHAR(32) PRIMARY KEY REFERENCES wells(well_id) ON DELETE CASCADE,
    latest_depth_md DOUBLE PRECISION,
    connection_status VARCHAR(32) NOT NULL DEFAULT 'DISCONNECTED', -- LIVE, REPLAY, DELAYED, STALE, DISCONNECTED
    provider VARCHAR(64) DEFAULT 'DEMO_REPLAY',
    data_quality VARCHAR(32) DEFAULT 'NORMAL',
    last_seen_timestamp TIMESTAMPTZ,
    latest_telemetry_json JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 11. ALERTS & OPERATIONAL HYGIENE
-- ============================================================
CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    alert_id VARCHAR(64) UNIQUE NOT NULL,
    well_id VARCHAR(32) NOT NULL REFERENCES wells(well_id) ON DELETE CASCADE,
    depth_md DOUBLE PRECISION NOT NULL,
    alert_type VARCHAR(64) NOT NULL,
    severity VARCHAR(32) NOT NULL, -- CRITICAL, HIGH, MEDIUM, LOW
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE', -- DETECTED, EVALUATED, ACTIVE, ACKNOWLEDGED, CLOSED
    signal_source VARCHAR(64),
    model_source VARCHAR(64),
    message TEXT NOT NULL,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    evaluated_at TIMESTAMPTZ DEFAULT NOW(),
    activated_at TIMESTAMPTZ DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    acknowledged_by VARCHAR(64),
    closed_by VARCHAR(64),
    acknowledgement_note TEXT,
    closure_note TEXT,
    evidence_ids JSONB DEFAULT '[]'::jsonb,
    live_ids JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_well_status ON alerts(well_id, status);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at DESC);

-- ============================================================
-- 12. AUDIT TRAIL (APPEND-ONLY)
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id VARCHAR(64),
    username VARCHAR(64) NOT NULL,
    role VARCHAR(32) NOT NULL,
    action VARCHAR(64) NOT NULL,
    resource_type VARCHAR(64) NOT NULL,
    resource_id VARCHAR(64),
    well_id VARCHAR(32),
    depth_md DOUBLE PRECISION,
    old_value JSONB,
    new_value JSONB,
    reason TEXT,
    ip_address VARCHAR(45),
    request_id VARCHAR(64)
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_well_id ON audit_logs(well_id);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(username);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);
