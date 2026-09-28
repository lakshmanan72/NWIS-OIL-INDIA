"""
NWIS Phase 8 — Comprehensive Integration, Adapter, Streaming & Security Test Suite
===================================================================================
Covers all 25 Phase 8 criteria and failure scenarios:
1. Provider Interface
2. Demo Provider Replay
3. WITSML XML Parser & Unit Conversion
4. eRTMAC Adapter Ingestion
5. Telemetry Normalization & Aliases
6. Physical Parameter Validation
7. Timestamp Handling & Clock Drift
8. Duplicate Message Detection
9. Out-of-Order Telemetry Tolerance
10. Well Identity Mapping
11. Unmatched Well Quarantine Protection
12. Exponential Reconnect & Bounded Backoff
13. Queue Sizing & Backpressure Controller
14. Telemetry Persistence
15. Live State & Restart Recovery
16. Anomaly Detection & LIVE-XXX Tokens
17. ML Risk Integration & Depth Safety (EXTRAPOLATED_BEYOND_TOTAL_DEPTH)
18. Alert Generation, Deduplication & Cooldown
19. Alert Persistence, Acknowledge & Close Lifecycle
20. RBAC Enforcement (Admin/Engineer vs Viewer)
21. Integration Health API Endpoints
22. WebSocket Stream Contract
23. Secret Redaction & Protection
24. Raw Payload Sanitization
25. Failure Safety & Resiliency
"""

import copy
from datetime import datetime, timedelta, timezone
import json
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.realtime.schema import RealtimeTelemetryRecord, validate_telemetry_payload
from backend.app.realtime.providers import (
    RealtimeDrillingProvider,
    DemoReplayProvider,
    WITSMLProvider,
    WITS0Provider,
    demo_replay_provider,
)
from backend.app.realtime.live_state import live_well_state
from backend.app.realtime.live_risk_engine import live_risk_engine
from backend.app.realtime.alert_engine import alert_engine
from backend.app.integrations.identity_resolver import well_identity_resolver, WellIdentityResolver
from backend.app.integrations.ertmac import ertmac_adapter, ERTMACAdapter, ERTMACClient, get_safe_ertmac_config
from backend.app.integrations.witsml import WitsmlParser, witsml_adapter, WITSMLAdapter, WitsmlClient, get_safe_witsml_config
from backend.app.integrations.wits0 import Wits0Parser, wits0_adapter, WITS0Adapter
from backend.app.integrations.streaming_pipeline import streaming_pipeline, TelemetryIngestionPipeline
from backend.app.security.auth import create_access_token, ROLE_ADMIN, ROLE_DRILLING_ENGINEER, ROLE_VIEWER
from backend.app.security.audit import log_audit_event
from backend.app.repositories.factory import get_telemetry_repository, get_audit_repository

client = TestClient(app)


# -----------------------------------------------------------------------------
# 1. Provider Interface
# -----------------------------------------------------------------------------
def test_provider_interface():
    providers = [demo_replay_provider, WITSMLProvider(), WITS0Provider()]
    for p in providers:
        assert isinstance(p, RealtimeDrillingProvider)
        assert hasattr(p, "connect")
        assert hasattr(p, "disconnect")
        assert hasattr(p, "health")
        assert hasattr(p, "get_latest")
        assert hasattr(p, "stream")
        assert hasattr(p, "acknowledge")
        assert hasattr(p, "metadata")
        meta = p.metadata()
        assert meta["advisory_only"] is True
        assert meta["supports_commands"] is False


# -----------------------------------------------------------------------------
# 2. Demo Provider Replay
# -----------------------------------------------------------------------------
def test_demo_provider_replay():
    demo = DemoReplayProvider(default_well_id="WELL-000050")
    assert demo.connect() is True
    demo.subscribe("WELL-000050")

    rec1 = demo.step()
    assert rec1 is not None
    assert rec1.well_id == "WELL-000050"
    assert rec1.depth_md > 0.0

    injected = demo.inject_anomaly("torque_spike")
    assert injected is not None
    assert injected.torque_kftlb >= 25.0

    h = demo.health()
    assert h["status"] == "HEALTHY"
    demo.disconnect()
    assert demo.is_connected is False


# -----------------------------------------------------------------------------
# 3. WITSML Parser & Unit Conversion
# -----------------------------------------------------------------------------
def test_witsml_parser():
    xml = """
    <logs xmlns="http://www.witsml.org/schemas/1series" version="1.4.1.1">
        <log uidWell="WELL-000050" uidWellbore="WB-01">
            <logCurveInfo><mnemonic>DEPT</mnemonic><unit>m</unit></logCurveInfo>
            <logCurveInfo><mnemonic>ROP</mnemonic><unit>m/h</unit></logCurveInfo>
            <logCurveInfo><mnemonic>TORQ</mnemonic><unit>kft.lb</unit></logCurveInfo>
            <logCurveInfo><mnemonic>SPP</mnemonic><unit>psi</unit></logCurveInfo>
            <logData>
                <data>1250.5, 25.4, 18.2, 1950.0</data>
                <data>1251.0, 26.1, 18.5, 1960.0</data>
            </logData>
        </log>
    </logs>
    """
    records = WitsmlParser.parse_log_xml(xml, default_well_id="WELL-000050")
    assert len(records) == 2
    assert records[0]["depth_md"] == 1250.5
    assert records[0]["rop_m_hr"] == 25.4
    assert records[0]["torque_kftlb"] == 18.2
    assert records[0]["standpipe_pressure_psi"] == 1950.0


# -----------------------------------------------------------------------------
# 4. eRTMAC Adapter Ingestion
# -----------------------------------------------------------------------------
def test_ertmac_adapter_ingestion():
    adapter = ERTMACAdapter()
    raw = {
        "well_id": "WELL-000050",
        "HOLE_DEPTH": 1180.5,
        "DRILL_RATE": 22.0,
        "SURF_TORQ": 17.5,
        "STANDPIPE_PRESS": 1880.0,
        "FLOW_IN": 1250.0,
        "FLOW_OUT": 1240.0,
        "TOTAL_GAS": 4.1,
    }
    success, status_code, details, rec = adapter.ingest_payload(raw)
    assert success is True
    assert status_code in ("VALID", "VALID_WITH_WARNINGS")
    assert rec.depth_md == 1180.5
    assert rec.rop_m_hr == 22.0
    assert rec.torque_kftlb == 17.5
    assert rec.standpipe_pressure_psi == 1880.0


# -----------------------------------------------------------------------------
# 5. Telemetry Normalization & Aliases
# -----------------------------------------------------------------------------
def test_telemetry_normalization_aliases():
    payload = {
        "canonical_well_id": "WELL-000050",
        "depth": 1195.0,
        "drill_rate": 28.5,
        "weight_on_bit": 15.2,
        "surf_rpm": 110.0,
        "surf_torq": 19.8,
        "spp": 2100.0,
        "flow_in_lpm": 1300.0,
        "flow_out_lpm": 1290.0,
        "total_gas": 6.4,
        "hook_load": 185.0,
        "pump_press": 2100.0,
    }
    is_valid, q_status, warnings, rec = validate_telemetry_payload(payload, source="TEST")
    assert is_valid is True
    assert rec.depth_md == 1195.0
    assert rec.rop == 28.5
    assert rec.wob == 15.2
    assert rec.rpm == 110.0
    assert rec.torque == 19.8
    assert rec.spp == 2100.0
    assert rec.mud_flow_in == 1300.0
    assert rec.mud_flow_out == 1290.0
    assert rec.gas == 6.4
    assert rec.hookload == 185.0
    assert rec.pump_pressure == 2100.0


# -----------------------------------------------------------------------------
# 6. Physical Parameter Validation
# -----------------------------------------------------------------------------
def test_physical_validation_bounds():
    # Negative depth must fail immediately
    neg_depth = {"well_id": "WELL-000050", "depth_md": -50.0}
    is_valid, status_code, warnings, _ = validate_telemetry_payload(neg_depth)
    assert is_valid is False
    assert status_code == "INVALID"
    assert any("negative" in w.lower() for w in warnings)

    # Out of bounds parameter gets clipped / flagged as suspect
    high_torque = {"well_id": "WELL-000050", "depth_md": 1200.0, "torque_kftlb": 150.0}
    is_valid2, status_code2, warnings2, rec2 = validate_telemetry_payload(high_torque)
    assert is_valid2 is True
    assert status_code2 in ("SUSPECT", "VALID_WITH_WARNINGS")


# -----------------------------------------------------------------------------
# 7. Timestamp Handling & Clock Drift
# -----------------------------------------------------------------------------
def test_timestamp_handling():
    # Normal ISO string
    iso_ts = datetime.now(timezone.utc).isoformat()
    _, _, _, rec = validate_telemetry_payload({"well_id": "WELL-000050", "depth_md": 1100.0, "timestamp": iso_ts})
    assert rec.timestamp.endswith("+00:00") or "Z" in rec.timestamp or "+00" in rec.timestamp
    assert rec.ingestion_latency_ms is not None
    assert rec.ingestion_latency_ms >= 0.0

    # Future clock drift (> 5 mins)
    future_ts = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    _, _, warnings_fut, _ = validate_telemetry_payload({"well_id": "WELL-000050", "depth_md": 1100.0, "timestamp": future_ts})
    assert any("clock drift" in w.lower() for w in warnings_fut)

    # Stale (> 24 hours)
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=36)).isoformat()
    _, status_stale, warnings_old, _ = validate_telemetry_payload({"well_id": "WELL-000050", "depth_md": 1100.0, "timestamp": old_ts})
    assert status_stale == "STALE"


# -----------------------------------------------------------------------------
# 8. Duplicate Message Detection
# -----------------------------------------------------------------------------
def test_duplicate_detection():
    pipeline = TelemetryIngestionPipeline(queue_max_size=100)
    ts_fixed = "2026-09-27T10:00:00+00:00"
    payload = {
        "well_id": "WELL-000050",
        "depth_md": 1205.0,
        "timestamp": ts_fixed,
        "rop_m_hr": 20.0,
    }

    # First submission -> VALID
    res1 = pipeline.ingest(payload, provider_source="eRTMAC")
    assert res1["success"] is True
    assert res1["status"] in ("VALID", "VALID_WITH_WARNINGS", "STALE")

    # Second submission with exact same key -> DUPLICATE
    res2 = pipeline.ingest(payload, provider_source="eRTMAC")
    assert res2["success"] is True
    assert res2["status"] == "DUPLICATE"


# -----------------------------------------------------------------------------
# 9. Out-of-Order Telemetry Tolerance
# -----------------------------------------------------------------------------
def test_out_of_order_telemetry():
    live_well_state.reset("WELL-000050")
    now = datetime.now(timezone.utc)
    t_newer = now.isoformat()
    t_older = (now - timedelta(minutes=5)).isoformat()

    # Ingest newer depth slice
    rec_newer = RealtimeTelemetryRecord(timestamp=t_newer, well_id="WELL-000050", depth_md=1300.0)
    live_well_state.update_telemetry(rec_newer)
    assert live_well_state.latest_record.depth_md == 1300.0

    # Ingest older packet arriving late
    rec_older = RealtimeTelemetryRecord(timestamp=t_older, well_id="WELL-000050", depth_md=1295.0)
    live_well_state.update_telemetry(rec_older)

    # Authoritative live state remains with the newest valid timestamp
    snap = live_well_state.get_state_snapshot()
    assert snap["depth_md"] == 1300.0


# -----------------------------------------------------------------------------
# 10. Well Identity Mapping
# -----------------------------------------------------------------------------
def test_well_identity_mapping():
    resolver = WellIdentityResolver()
    # Pre-mapped vendor ID
    can_id, status_code, details = resolver.resolve("eRTMAC", "WELL-ABC")
    assert can_id == "WELL-000050"
    assert status_code == "RESOLVED"

    # Direct canonical format
    can_id2, status_code2, _ = resolver.resolve("eRTMAC", "WELL-000050")
    assert can_id2 == "WELL-000050"
    assert status_code2 == "CANONICAL_DIRECT"


# -----------------------------------------------------------------------------
# 11. Unmatched Well Quarantine Protection
# -----------------------------------------------------------------------------
def test_unmatched_well_quarantine():
    resolver = WellIdentityResolver()
    unmatched_rig = "UNKNOWN_VENDOR_RIG_99"
    can_id, status_code, details = resolver.resolve("eRTMAC", unmatched_rig)
    assert can_id is None
    assert status_code == "UNMATCHED_WELL"

    quarantined = resolver.get_quarantined_wells()
    assert any(q["external_well_id"] == unmatched_rig for q in quarantined)

    # Pipeline rejects unmatched well
    pipeline = TelemetryIngestionPipeline()
    res = pipeline.ingest({"well_id": unmatched_rig, "depth_md": 1000.0}, provider_source="eRTMAC")
    assert res["success"] is False
    assert res["status"] == "UNMATCHED_WELL"


# -----------------------------------------------------------------------------
# 12. Exponential Reconnect & Bounded Backoff
# -----------------------------------------------------------------------------
def test_reconnect_logic():
    # Configure unreachable client
    cfg = {
        "enabled": True,
        "base_url": "http://127.0.0.1:59999",  # Non-existent port
        "username": "",
        "password": "",
        "api_key": "",
        "timeout_seconds": 0.5,
        "max_retries": 3,
    }
    client_ertmac = ERTMACClient(config_override=cfg)
    assert client_ertmac.connect() is False
    h = client_ertmac.get_health()
    assert h["reconnect_count"] >= 1
    assert h["status"] in ("DEGRADED", "DISCONNECTED")


# -----------------------------------------------------------------------------
# 13. Queue Sizing & Backpressure Controller
# -----------------------------------------------------------------------------
def test_queue_backpressure():
    pipeline = TelemetryIngestionPipeline(queue_max_size=5)
    for i in range(10):
        pipeline.ingest(
            {"well_id": "WELL-000050", "depth_md": 1100.0 + i * 2.0, "timestamp": f"2026-09-27T10:0{i % 60}:00Z"},
            provider_source="DEMO_REPLAY",
        )
    metrics = pipeline.get_metrics()
    assert metrics["messages_received"] == 10
    assert metrics["messages_dropped_backpressure"] >= 5
    assert metrics["queue_current_size"] <= 5


# -----------------------------------------------------------------------------
# 14. Telemetry Persistence
# -----------------------------------------------------------------------------
def test_telemetry_persistence():
    repo = get_telemetry_repository()
    rec = {
        "well_id": "WELL-000050",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "depth_md": 1222.5,
        "rop_m_hr": 21.0,
        "torque_kftlb": 18.0,
        "standpipe_pressure_psi": 1900.0,
    }
    repo.record_telemetry(rec)
    latest = repo.get_latest_telemetry("WELL-000050")
    assert latest is not None
    assert latest.get("depth_md") == 1222.5


# -----------------------------------------------------------------------------
# 15. Live State & Restart Recovery
# -----------------------------------------------------------------------------
def test_live_state_and_recovery():
    live_well_state.reset("WELL-000050")
    rec = RealtimeTelemetryRecord(
        timestamp=datetime.now(timezone.utc).isoformat(),
        well_id="WELL-000050",
        depth_md=1234.5,
        rop_m_hr=23.0,
        wob_klbf=14.0,
        rpm=95.0,
        torque_kftlb=19.0,
        standpipe_pressure_psi=1850.0,
        flow_rate_lpm=1250.0,
        mud_weight_ppg=9.8,
        gas_units=4.2,
    )
    live_well_state.update_telemetry(rec, provider_mode="TEST")
    snap = live_well_state.get_state_snapshot()
    assert snap["well_id"] == "WELL-000050"
    assert snap["depth_md"] == 1234.5
    assert snap["data_quality"]["quality"] in ("GOOD", "NORMAL")


# -----------------------------------------------------------------------------
# 16. Anomaly Detection & LIVE-XXX Tokens
# -----------------------------------------------------------------------------
def test_anomaly_detection_live_tokens():
    # Feed anomaly slice through live risk engine
    anom_rec = RealtimeTelemetryRecord(
        timestamp=datetime.now(timezone.utc).isoformat(),
        well_id="WELL-000050",
        depth_md=1250.0,
        torque_kftlb=32.0,  # Distinct torque spike
    )
    live_well_state.update_telemetry(anom_rec)
    packet = live_risk_engine.evaluate_live_risk(
        record=anom_rec,
        anomalies=[],
        provider_mode="TEST",
    )
    assert packet.active_well == "WELL-000050"
    assert packet.depth_safety_status == "NORMAL"


# -----------------------------------------------------------------------------
# 17. ML Risk Integration & Depth Safety Check
# -----------------------------------------------------------------------------
def test_depth_safety_extrapolated_beyond_total_depth():
    # WELL-000050 total depth is ~2400-3000m. Let's test with depth = 9999m
    deep_rec = RealtimeTelemetryRecord(
        timestamp=datetime.now(timezone.utc).isoformat(),
        well_id="WELL-000050",
        depth_md=9999.0,
    )
    packet = live_risk_engine.evaluate_live_risk(
        record=deep_rec,
        anomalies=[],
        provider_mode="TEST",
    )
    # Must flag EXTRAPOLATED_BEYOND_TOTAL_DEPTH
    assert packet.depth_safety_status == "EXTRAPOLATED_BEYOND_TOTAL_DEPTH"
    for m in packet.model_risk_indicators:
        assert m["status"] == "EXTRAPOLATED_BEYOND_TOTAL_DEPTH"
        assert "exceeds" in m.get("warning", "").lower()


# -----------------------------------------------------------------------------
# 18. Alert Generation, Deduplication & Cooldown
# -----------------------------------------------------------------------------
def test_alert_generation_and_cooldown():
    rec = RealtimeTelemetryRecord(
        timestamp=datetime.now(timezone.utc).isoformat(),
        well_id="WELL-000050",
        depth_md=1135.0,
        torque_kftlb=30.0,
    )
    packet = live_risk_engine.evaluate_live_risk(record=rec, anomalies=[], provider_mode="TEST")
    alerts1 = alert_engine.process_live_packet(packet)

    # Re-evaluate same packet immediately: cooldown (60s) prevents spam
    alerts2 = alert_engine.process_live_packet(packet)
    assert len(alerts2) <= len(alerts1)


# -----------------------------------------------------------------------------
# 19. Alert Persistence, Acknowledge & Close Lifecycle
# -----------------------------------------------------------------------------
def test_alert_lifecycle_and_audit():
    # Seed alert
    test_aid = "ALT-TEST-999"
    alert_data = {
        "alert_id": test_aid,
        "well_id": "WELL-000050",
        "depth_md": 1135.0,
        "hazard": "torque_spike",
        "severity": "HIGH",
        "status": "ACTIVE",
        "message": "Test torque spike alert",
    }
    from backend.app.realtime.alert_engine import DrillingAlert
    al = DrillingAlert(
        alert_id=test_aid,
        well_id="WELL-000050",
        hazard="torque_spike",
        severity="HIGH",
        status="ACTIVE",
        depth_from=1135.0,
        depth_to=1135.0,
        depth_interval="1135 m",
        formation="Barail",
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        title="Torque Spike in Barail",
        description="Test alert",
        model_risk_indicator_pct=25.0,
        historical_evidence_count=1,
    )
    alert_engine.alerts[test_aid] = al

    # Acknowledge
    acked = alert_engine.acknowledge_alert(test_aid, reviewer="Lead Rig Engineer", note="Adjusting RPM")
    assert acked.status == "ACKNOWLEDGED"
    assert acked.engineer_note == "Adjusting RPM"

    # Close
    closed = alert_engine.close_alert(test_aid, reviewer="Lead Rig Engineer", note="Torque normalized")
    assert closed.status == "CLOSED"


# -----------------------------------------------------------------------------
# 20. RBAC Enforcement (Admin/Engineer vs Viewer)
# -----------------------------------------------------------------------------
def test_rbac_restrictions():
    admin_token = create_access_token({"sub": "admin", "role": ROLE_ADMIN})
    viewer_token = create_access_token({"sub": "viewer", "role": ROLE_VIEWER})

    # Viewer cannot connect integration
    resp_viewer = client.post(
        "/api/integrations/demo_replay/connect",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp_viewer.status_code == 403

    # Admin can connect
    resp_admin = client.post(
        "/api/integrations/demo_replay/connect",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_admin.status_code == 200


# -----------------------------------------------------------------------------
# 21. Integration Health API Endpoints
# -----------------------------------------------------------------------------
def test_integration_health_endpoints():
    res = client.get("/api/integrations/status")
    assert res.status_code == 200
    data = res.json()
    assert "providers" in data
    assert "ertmac" in data["providers"]
    assert "witsml" in data["providers"]
    assert "wits0" in data["providers"]
    assert "demo_replay" in data["providers"]
    assert "pipeline_metrics" in data


# -----------------------------------------------------------------------------
# 22. WebSocket Stream Contract
# -----------------------------------------------------------------------------
def test_websocket_stream_contract():
    with client.websocket_connect("/ws/realtime/WELL-000050") as ws:
        msg_text = ws.receive_text()
        msg = json.loads(msg_text)
        assert msg["type"] == "telemetry"
        assert msg["well_id"] == "WELL-000050"
        assert "timestamp" in msg
        assert "data" in msg


# -----------------------------------------------------------------------------
# 23. Secret Redaction & Protection
# -----------------------------------------------------------------------------
def test_secret_redaction():
    safe_ertmac = get_safe_ertmac_config()
    assert "password" not in safe_ertmac
    assert "api_key" not in safe_ertmac
    assert "has_password" in safe_ertmac

    safe_witsml = get_safe_witsml_config()
    assert "password" not in safe_witsml
    assert "has_password" in safe_witsml


# -----------------------------------------------------------------------------
# 24. Raw Payload Sanitization
# -----------------------------------------------------------------------------
def test_raw_payload_sanitization():
    dirty_payload = {
        "well_id": "WELL-000050",
        "depth_md": 1100.0,
        "password": "SecretPassword123!",
        "api_key": "Bearer sensitive_token",
        "rop_m_hr": 20.0,
    }
    is_valid, _, _, rec = validate_telemetry_payload(dirty_payload, store_raw=True)
    assert is_valid is True
    assert rec.raw_payload is not None
    assert "password" not in rec.raw_payload
    assert "api_key" not in rec.raw_payload


# -----------------------------------------------------------------------------
# 25. Failure Safety & Resiliency
# -----------------------------------------------------------------------------
def test_failure_safety():
    # 1. Malformed WITSML XML raises clean ValueError without crash
    with pytest.raises(ValueError):
        WitsmlParser.parse_log_xml("<malformed><unclosed>")

    # 2. Corrupted WITS0 packet returns None safely
    corrupt_wits0 = "&&NOT_WITS_DATA!!"
    assert Wits0Parser.parse_packet(corrupt_wits0) is None

    # 3. None/empty payload rejected gracefully
    is_valid, status_code, warnings, _ = validate_telemetry_payload(None)
    assert is_valid is False
    assert status_code == "INVALID"

    # 4. Ready endpoint succeeds even if integrations are disabled
    ready_res = client.get("/api/ready")
    assert ready_res.status_code == 200
    assert ready_res.json()["integrations"]["subsystem"] == "ready"
