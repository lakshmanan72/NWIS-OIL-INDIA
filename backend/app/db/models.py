from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Float,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    Index,
    JSON,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# ============================================================
# 1. USER & RBAC
# ============================================================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(128), unique=True, nullable=False, index=True)
    hashed_password = Column(String(256), nullable=False)
    full_name = Column(String(128), nullable=True)
    role = Column(String(32), nullable=False, default="VIEWER", index=True)  # ADMIN, DRILLING_ENGINEER, GEOLOGIST, VIEWER
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


# ============================================================
# 2. CANONICAL WELLS
# ============================================================
class Well(Base):
    __tablename__ = "wells"

    id = Column(Integer, primary_key=True, autoincrement=True)
    well_id = Column(String(32), unique=True, nullable=False, index=True)
    well_name = Column(String(128), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    state = Column(String(64), nullable=True)
    district = Column(String(64), nullable=True)
    field = Column(String(128), nullable=True, index=True)
    block = Column(String(128), nullable=True)
    basin = Column(String(128), nullable=True, index=True)
    operator = Column(String(128), nullable=True, index=True)
    status = Column(String(64), nullable=True)
    well_type = Column(String(64), nullable=True)
    trajectory_type = Column(String(64), nullable=True)
    total_depth = Column(Float, nullable=True)
    spud_date = Column(String(32), nullable=True)
    completion_date = Column(String(32), nullable=True)
    source = Column(String(64), default="REAL_PUBLIC")
    coordinate_source = Column(String(64), default="REAL_PUBLIC")
    coordinate_confidence = Column(Float, default=1.0)
    formation = Column(String(128), nullable=True)
    source_document = Column(String(64), nullable=True)
    is_canonical = Column(Boolean, default=True)
    is_new_well = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    geology = relationship("WellGeology", back_populates="well", cascade="all, delete-orphan")
    formations = relationship("WellFormation", back_populates="well", cascade="all, delete-orphan")
    events = relationship("HistoricalEvent", back_populates="well", cascade="all, delete-orphan")
    daily_parameters = relationship("DailyDrillingParameter", back_populates="well", cascade="all, delete-orphan")
    mud_logs = relationship("MudLogging", back_populates="well", cascade="all, delete-orphan")
    wcr_completions = relationship("WellCompletionWCR", back_populates="well", cascade="all, delete-orphan")
    risks = relationship("RiskRecommendation", back_populates="well", cascade="all, delete-orphan")
    telemetry = relationship("TelemetryRecord", back_populates="well", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="well", cascade="all, delete-orphan")


# ============================================================
# 3. GEOLOGY & STRATIGRAPHY
# ============================================================
class WellGeology(Base):
    __tablename__ = "well_geology"

    id = Column(Integer, primary_key=True, autoincrement=True)
    well_id = Column(String(32), ForeignKey("wells.well_id", ondelete="CASCADE"), nullable=False, index=True)
    formation_name = Column(String(128), nullable=True, index=True)
    lithology = Column(String(128), nullable=True)
    depth_from = Column(Float, nullable=True)
    depth_to = Column(Float, nullable=True)
    thickness = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    source = Column(String(64), default="REGIONAL_SURVEY")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    well = relationship("Well", back_populates="geology")

    __table_args__ = (
        Index("idx_geology_well_depth", "well_id", "depth_from", "depth_to"),
    )


class WellFormation(Base):
    __tablename__ = "well_formations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    well_id = Column(String(32), ForeignKey("wells.well_id", ondelete="CASCADE"), nullable=False, index=True)
    formation_name = Column(String(128), nullable=False, index=True)
    top_depth_md = Column(Float, nullable=True)
    bottom_depth_md = Column(Float, nullable=True)
    age_era = Column(String(64), nullable=True)
    permeability_class = Column(String(64), nullable=True)
    source = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    well = relationship("Well", back_populates="formations")

    __table_args__ = (
        Index("idx_formations_top_depth", "well_id", "top_depth_md"),
    )


# ============================================================
# 4. HISTORICAL DRILLING EVENTS
# ============================================================
class HistoricalEvent(Base):
    __tablename__ = "historical_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), unique=True, nullable=True, index=True)
    well_id = Column(String(32), ForeignKey("wells.well_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    event_subtype = Column(String(64), nullable=True)
    depth_md = Column(Float, nullable=True, index=True)
    depth_from = Column(Float, nullable=True)
    depth_to = Column(Float, nullable=True)
    severity = Column(String(32), nullable=True, index=True)
    description = Column(Text, nullable=True)
    source_document_id = Column(String(64), nullable=True)
    event_date = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    well = relationship("Well", back_populates="events")


# ============================================================
# 5. DAILY DRILLING PARAMETERS
# ============================================================
class DailyDrillingParameter(Base):
    __tablename__ = "daily_drilling_parameters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    well_id = Column(String(32), ForeignKey("wells.well_id", ondelete="CASCADE"), nullable=False, index=True)
    recorded_date = Column(String(32), nullable=True, index=True)
    depth_md = Column(Float, nullable=True)
    progress_m = Column(Float, nullable=True)
    wob_klbf = Column(Float, nullable=True)
    rpm = Column(Float, nullable=True)
    rop_m_hr = Column(Float, nullable=True)
    torque_kftlb = Column(Float, nullable=True)
    standpipe_pressure_psi = Column(Float, nullable=True)
    flow_rate_gpm = Column(Float, nullable=True)
    mud_weight_ppg = Column(Float, nullable=True)
    operation_summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    well = relationship("Well", back_populates="daily_parameters")

    __table_args__ = (
        Index("idx_daily_well_depth", "well_id", "depth_md"),
    )


# ============================================================
# 6. MUD LOGGING (HIGH FREQUENCY)
# ============================================================
class MudLogging(Base):
    __tablename__ = "mud_logging"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    well_id = Column(String(32), ForeignKey("wells.well_id", ondelete="CASCADE"), nullable=False, index=True)
    depth_md = Column(Float, nullable=False)
    recorded_at = Column(String(32), nullable=True)
    total_gas_units = Column(Float, nullable=True)
    c1_methane_ppm = Column(Float, nullable=True)
    c2_ethane_ppm = Column(Float, nullable=True)
    c3_propane_ppm = Column(Float, nullable=True)
    ic4_isobutane_ppm = Column(Float, nullable=True)
    nc4_normalbutane_ppm = Column(Float, nullable=True)
    c5_pentane_ppm = Column(Float, nullable=True)
    flow_show_pct = Column(Float, nullable=True)
    pit_volume_m3 = Column(Float, nullable=True)
    lithology_observed = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    well = relationship("Well", back_populates="mud_logs")

    __table_args__ = (
        Index("idx_mudlog_well_depth", "well_id", "depth_md"),
        Index("idx_mudlog_well_rec", "well_id", "recorded_at"),
    )


# ============================================================
# 7. WCR & COMPLETION DATA
# ============================================================
class WellCompletionWCR(Base):
    __tablename__ = "well_completion_wcr"

    id = Column(Integer, primary_key=True, autoincrement=True)
    well_id = Column(String(32), ForeignKey("wells.well_id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(64), nullable=True, index=True)
    casing_size_inch = Column(Float, nullable=True)
    casing_depth_m = Column(Float, nullable=True)
    tubing_size_inch = Column(Float, nullable=True)
    perforation_interval_top_m = Column(Float, nullable=True)
    perforation_interval_bottom_m = Column(Float, nullable=True)
    reservoir_name = Column(String(128), nullable=True)
    initial_production_oil_bopd = Column(Float, nullable=True)
    initial_production_gas_mscfd = Column(Float, nullable=True)
    initial_reservoir_pressure_psi = Column(Float, nullable=True)
    completion_type = Column(String(64), nullable=True)
    approval_status = Column(String(32), default="REVIEW_REQUIRED")
    raw_payload_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    well = relationship("Well", back_populates="wcr_completions")


# ============================================================
# 8. DOCUMENTS & CHUNKS
# ============================================================
class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String(64), unique=True, nullable=False, index=True)
    filename = Column(String(256), nullable=False)
    sha256 = Column(String(64), nullable=False)
    well_id = Column(String(32), nullable=True, index=True)
    document_type = Column(String(64), nullable=True)
    approval_status = Column(String(32), nullable=False, default="REVIEW_REQUIRED", index=True)
    page_count = Column(Integer, default=1)
    file_size_bytes = Column(BigInteger, nullable=True)
    uploaded_by = Column(String(64), nullable=True)
    approved_by = Column(String(64), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chunk_id = Column(String(64), unique=True, nullable=False, index=True)
    document_id = Column(String(64), ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False, index=True)
    well_id = Column(String(32), nullable=True, index=True)
    page_number = Column(Integer, nullable=True)
    section_name = Column(String(128), nullable=True)
    chunk_text = Column(Text, nullable=False)
    formation = Column(String(128), nullable=True)
    depth_from = Column(Float, nullable=True)
    depth_to = Column(Float, nullable=True)
    event_type = Column(String(64), nullable=True)
    approval_status = Column(String(32), nullable=False, default="REVIEW_REQUIRED", index=True)
    embedding_vector = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    document = relationship("Document", back_populates="chunks")


# ============================================================
# 9. RISK RECOMMENDATIONS
# ============================================================
class RiskRecommendation(Base):
    __tablename__ = "risk_recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    risk_id = Column(String(64), unique=True, nullable=True, index=True)
    well_id = Column(String(32), ForeignKey("wells.well_id", ondelete="CASCADE"), nullable=False, index=True)
    hazard_type = Column(String(64), nullable=False, index=True)
    risk_score = Column(Float, nullable=False)
    risk_level = Column(String(32), nullable=False)
    predicted_event = Column(String(128), nullable=True)
    confidence = Column(Float, nullable=True)
    recommended_action = Column(Text, nullable=True)
    supporting_event_id = Column(String(64), nullable=True)
    model_version = Column(String(32), default="nwis-v1.0")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    well = relationship("Well", back_populates="risks")


# ============================================================
# 10. REALTIME TELEMETRY & LIVE STATE
# ============================================================
class TelemetryRecord(Base):
    __tablename__ = "telemetry_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    well_id = Column(String(32), ForeignKey("wells.well_id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    depth_md = Column(Float, nullable=False)
    rop = Column(Float, nullable=True)
    wob = Column(Float, nullable=True)
    rpm = Column(Float, nullable=True)
    torque = Column(Float, nullable=True)
    spp = Column(Float, nullable=True)
    mud_flow_in = Column(Float, nullable=True)
    mud_flow_out = Column(Float, nullable=True)
    gas = Column(Float, nullable=True)
    pump_pressure = Column(Float, nullable=True)
    hookload = Column(Float, nullable=True)
    source = Column(String(64), default="eRTMAC")
    quality_status = Column(String(32), default="GOOD")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    well = relationship("Well", back_populates="telemetry")

    __table_args__ = (
        Index("idx_telem_well_time", "well_id", "timestamp"),
        Index("idx_telem_well_depth", "well_id", "depth_md"),
    )


class WellLiveState(Base):
    __tablename__ = "well_live_state"

    well_id = Column(String(32), ForeignKey("wells.well_id", ondelete="CASCADE"), primary_key=True)
    latest_depth_md = Column(Float, nullable=True)
    connection_status = Column(String(32), nullable=False, default="DISCONNECTED")
    provider = Column(String(64), default="DEMO_REPLAY")
    data_quality = Column(String(32), default="NORMAL")
    last_seen_timestamp = Column(DateTime(timezone=True), nullable=True)
    latest_telemetry_json = Column(JSON, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


# ============================================================
# 11. ALERTS
# ============================================================
class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(String(64), unique=True, nullable=False, index=True)
    well_id = Column(String(32), ForeignKey("wells.well_id", ondelete="CASCADE"), nullable=False, index=True)
    depth_md = Column(Float, nullable=False)
    alert_type = Column(String(64), nullable=False)
    severity = Column(String(32), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="ACTIVE", index=True)
    signal_source = Column(String(64), nullable=True)
    model_source = Column(String(64), nullable=True)
    message = Column(Text, nullable=False)
    detected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    evaluated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    activated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(String(64), nullable=True)
    closed_by = Column(String(64), nullable=True)
    acknowledgement_note = Column(Text, nullable=True)
    closure_note = Column(Text, nullable=True)
    evidence_ids = Column(JSON, default=list)
    live_ids = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    well = relationship("Well", back_populates="alerts")


# ============================================================
# 12. AUDIT TRAIL
# ============================================================
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    user_id = Column(String(64), nullable=True)
    username = Column(String(64), nullable=False, index=True)
    role = Column(String(32), nullable=False)
    action = Column(String(64), nullable=False, index=True)
    resource_type = Column(String(64), nullable=False)
    resource_id = Column(String(64), nullable=True)
    well_id = Column(String(32), nullable=True, index=True)
    depth_md = Column(Float, nullable=True)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    reason = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    request_id = Column(String(64), nullable=True)
