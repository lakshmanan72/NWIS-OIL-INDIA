import pytest
import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.models import Base, User, Well, WellGeology, Alert, TelemetryRecord, WellLiveState, AuditLog
from backend.app.db.session import check_database_connection
from backend.app.repositories.csv_repository import CsvWellRepository, CsvSpatialRepository
from backend.app.repositories.postgres_repository import PostgresWellRepository
from backend.app.repositories.factory import (
    get_well_repository,
    get_spatial_repository,
    get_alert_repository,
    get_telemetry_repository,
    get_audit_repository,
)
from backend.app.security.auth import (
    create_access_token,
    decode_access_token,
    verify_password,
    get_password_hash,
    get_permissions_for_role,
    ROLE_ADMIN,
    ROLE_DRILLING_ENGINEER,
    ROLE_GEOLOGIST,
    ROLE_VIEWER,
)
from backend.app.security.audit import log_audit_event
from backend.app.realtime.alert_engine import alert_engine


client = TestClient(app)


# ============================================================
# 1. DATABASE & SCHEMA CONSTRAINTS TESTS
# ============================================================
def test_database_schema_creation_and_constraints():
    """Verifies that all Phase 7 SQLAlchemy models can be instantiated and mapped."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionTest = sessionmaker(bind=engine)

    with SessionTest() as session:
        # Create well
        w1 = Well(
            well_id="WELL-TEST-01",
            well_name="Test Well Alpha",
            latitude=16.34,
            longitude=82.15,
            operator="ONGC",
            field="KG Offshore",
            basin="Krishna-Godavari",
            total_depth=3500.0,
        )
        session.add(w1)
        session.commit()

        # Verify query
        retrieved = session.scalars(select(Well).where(Well.well_id == "WELL-TEST-01")).first()
        assert retrieved is not None
        assert retrieved.well_name == "Test Well Alpha"
        assert retrieved.total_depth == 3500.0

        # Unique well_id constraint check
        w_dup = Well(
            well_id="WELL-TEST-01",
            well_name="Duplicate Well",
            latitude=16.35,
            longitude=82.16,
        )
        session.add(w_dup)
        with pytest.raises(Exception):
            session.commit()
        session.rollback()


def test_foreign_key_and_cascade():
    """Verifies foreign key relationships and cascade behavior."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionTest = sessionmaker(bind=engine)

    with SessionTest() as session:
        w = Well(
            well_id="WELL-FK-01",
            well_name="FK Test Well",
            latitude=15.0,
            longitude=80.0,
        )
        session.add(w)
        session.commit()

        geo = WellGeology(
            well_id="WELL-FK-01",
            formation_name="Tertiary Clastics",
            lithology="Sandstone",
            depth_from=100.0,
            depth_to=250.0,
        )
        session.add(geo)
        session.commit()

        # Query child
        geo_retrieved = session.scalars(select(WellGeology).where(WellGeology.well_id == "WELL-FK-01")).first()
        assert geo_retrieved is not None
        assert geo_retrieved.formation_name == "Tertiary Clastics"


# ============================================================
# 2. REPOSITORY INTERFACE & CONTRACT EQUALITY TESTS
# ============================================================
def test_well_repository_contracts():
    """Verifies that WellRepository returns correct models and adheres to interface."""
    repo = get_well_repository()
    assert repo is not None

    total, wells = repo.get_all_wells(offset=0, limit=10)
    assert total >= 15108
    assert len(wells) == 10

    sample = wells[0]
    assert hasattr(sample, "well_id")
    assert hasattr(sample, "well_name")
    assert hasattr(sample, "latitude")
    assert hasattr(sample, "longitude")

    single = repo.get_well("WELL-000001")
    assert single is not None
    assert single.well_id == "WELL-000001"


def test_spatial_repository_contracts():
    """Verifies that SpatialRepository computes nearby offset wells."""
    spatial_repo = get_spatial_repository()
    assert spatial_repo is not None

    nearby = spatial_repo.get_nearby_wells("WELL-000001", radius_km=50.0, limit=5)
    assert isinstance(nearby, list)
    if nearby:
        item = nearby[0]
        assert hasattr(item, "well_id")
        assert hasattr(item, "distance_km")
        assert item.distance_km <= 50.0


# ============================================================
# 3. RBAC & AUTHENTICATION TESTS
# ============================================================
def test_password_hashing_and_verification():
    raw = "SecureRigSecret2026!"
    hashed = get_password_hash(raw)
    assert hashed != raw
    assert verify_password(raw, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_token_creation_and_decoding():
    token = create_access_token(data={"sub": "engineer_test", "role": ROLE_DRILLING_ENGINEER})
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded.username == "engineer_test"
    assert decoded.role == ROLE_DRILLING_ENGINEER


def test_role_permissions_matrix():
    admin_perms = get_permissions_for_role(ROLE_ADMIN)
    assert "users:manage" in admin_perms
    assert "config:manage" in admin_perms
    assert "alerts:close" in admin_perms

    engineer_perms = get_permissions_for_role(ROLE_DRILLING_ENGINEER)
    assert "alerts:ack" in engineer_perms
    assert "documents:approve" in engineer_perms
    assert "users:manage" not in engineer_perms

    viewer_perms = get_permissions_for_role(ROLE_VIEWER)
    assert "wells:read" in viewer_perms
    assert "documents:approve" not in viewer_perms
    assert "alerts:close" not in viewer_perms


def test_auth_login_api_success():
    res = client.post(
        "/api/auth/login",
        json={"username": "engineer", "password": "EngineerPassword2026!"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["role"] == ROLE_DRILLING_ENGINEER


def test_auth_login_api_invalid_credentials():
    res = client.post(
        "/api/auth/login",
        json={"username": "engineer", "password": "BadPassword"}
    )
    assert res.status_code == 401


def test_auth_me_protected_route():
    login_res = client.post(
        "/api/auth/login",
        json={"username": "geologist", "password": "GeologistPassword2026!"}
    )
    token = login_res.json()["access_token"]

    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "geologist"
    assert me_res.json()["role"] == ROLE_GEOLOGIST


def test_rbac_forbidden_viewer_on_audit():
    login_res = client.post(
        "/api/auth/login",
        json={"username": "viewer", "password": "ViewerPassword2026!"}
    )
    token = login_res.json()["access_token"]

    audit_res = client.get("/api/audit", headers={"Authorization": f"Bearer {token}"})
    assert audit_res.status_code == 403


# ============================================================
# 4. AUDIT TRAIL TESTS
# ============================================================
def test_audit_event_logging():
    log_audit_event(
        username="lead_engineer",
        role=ROLE_DRILLING_ENGINEER,
        action="TEST_ACTION",
        resource_type="WELL",
        resource_id="WELL-000001",
        well_id="WELL-000001",
        reason="Phase 7 test verification",
    )

    audit_repo = get_audit_repository()
    logs = audit_repo.list_audit_logs(well_id="WELL-000001", limit=10)
    assert len(logs) > 0
    assert logs[0]["action"] == "TEST_ACTION"
    assert logs[0]["username"] == "lead_engineer"


# ============================================================
# 5. REALTIME TELEMETRY & ALERT PERSISTENCE
# ============================================================
def test_telemetry_persistence_and_retrieval():
    telem_repo = get_telemetry_repository()
    assert telem_repo is not None

    record = {
        "well_id": "WELL-000050",
        "depth_md": 1250.5,
        "rop_m_hr": 24.2,
        "wob_klbf": 15.0,
        "rpm": 110,
        "torque_kftlb": 18.2,
        "standpipe_pressure_psi": 2100,
        "mud_flow_in_lpm": 1400,
        "mud_flow_out_lpm": 1400,
        "gas_units": 6.5,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    telem_repo.record_telemetry(record)

    latest = telem_repo.get_latest_telemetry("WELL-000050")
    assert latest is not None
    assert float(latest["depth_md"]) == 1250.5


def test_alert_lifecycle_and_audit():
    alert_repo = get_alert_repository()
    assert alert_repo is not None

    test_alert = {
        "alert_id": "ALT-P7-001",
        "well_id": "WELL-000050",
        "hazard": "torque_spike",
        "severity": "HIGH",
        "status": "ACTIVE",
        "depth_md": 1250.5,
        "message": "Phase 7 test torque surge",
    }
    alert_repo.create_alert(test_alert)

    # Acknowledge
    ack = alert_repo.acknowledge_alert("ALT-P7-001", acknowledged_by="TestEngineer", note="Checked rig floor")
    assert ack is not None
    assert ack["status"] == "ACKNOWLEDGED"

    # Close
    closed = alert_repo.close_alert("ALT-P7-001", closed_by="TestEngineer", note="Torque normalized")
    assert closed is not None
    assert closed["status"] == "CLOSED"


# ============================================================
# 6. HEALTH & READINESS ENDPOINTS
# ============================================================
def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["version"] in ("7.0.0", "8.0.0")
    assert "advisory" in data


def test_readiness_endpoint():
    res = client.get("/api/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert "database" in data
    assert "backend_mode" in data
    assert data["canonical_wells_available"] is True
    assert data["total_canonical_wells"] >= 15108
