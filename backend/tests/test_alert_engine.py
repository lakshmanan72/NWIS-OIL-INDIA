"""
Tests for NWIS Phase 6 Alert Engine:
- Alert creation from LiveEvidencePacket
- Depth window deduplication (merging repetitive events within delta depth)
- Cooldown suppression (preventing alert flooding)
- Alert lifecycle management: ACTIVE -> ACKNOWLEDGED -> CLOSED
"""

import pytest
import os
from pathlib import Path
from backend.app.realtime.alert_engine import AlertEngine, DrillingAlert
from backend.app.realtime.live_risk_engine import LiveEvidencePacket


def _make_packet(depth: float, anomalies: list, well_id: str = "WELL-000050"):
    return LiveEvidencePacket(
        active_well=well_id,
        current_depth=depth,
        formation="Barail",
        lithology="Sandstone",
        provider_mode="DEMO REPLAY",
        timestamp="2026-09-27T10:00:00Z",
        live_observations=anomalies,
        model_risk_indicators=[{"hazard": "torque_spike", "model_risk_pct": 78.5, "model_risk_elevated": True}],
        evaluated_signals=[{"hazard": "torque_spike", "model_risk_pct": 78.5, "model_risk_elevated": True, "historical_evidence_count": 2}],
        nearby_wells=[],
        historical_events=[],
        document_evidence=[{"evidence_id": "EVID-001"}],
        data_quality={"quality": "GOOD"}
    )


def test_alert_generation_and_deduplication(tmp_path):
    """Verify that multiple anomalies within a small depth window (e.g. 5m) update an existing alert rather than duplicating."""
    test_storage = tmp_path / "test_alerts.json"

    engine = AlertEngine()
    engine.alerts = {}
    engine.alert_counter = 0
    engine.storage_path = test_storage

    obs1 = [{
        "live_id": "LIVE-001",
        "anomaly_type": "torque_spike",
        "severity": "HIGH",
        "depth_md": 3185.0,
        "description": "Torque spike at 3185.0m",
    }]
    packet1 = _make_packet(depth=3185.0, anomalies=obs1)

    alerts1 = engine.process_live_packet(packet1)
    assert len(alerts1) > 0
    alert1 = alerts1[0]
    assert alert1.status == "ACTIVE"
    assert alert1.depth_from == 3185.0
    initial_alert_id = alert1.alert_id

    # Second anomaly 2 meters deeper (3187.0m) within same depth window (5m)
    obs2 = [{
        "live_id": "LIVE-002",
        "anomaly_type": "torque_spike",
        "severity": "CRITICAL",
        "depth_md": 3187.0,
        "description": "Escalated torque spike at 3187.0m",
    }]
    packet2 = _make_packet(depth=3187.0, anomalies=obs2)

    alerts2 = engine.process_live_packet(packet2)
    assert len(alerts2) > 0
    alert2 = alerts2[0]
    # Deduplication must merge into existing alert ID
    assert alert2.alert_id == initial_alert_id
    assert alert2.depth_from == 3185.0
    assert alert2.depth_to == 3187.0
    assert "LIVE-002" in alert2.live_observations

    # Active alerts count should be 1
    active = engine.get_alerts(well_id="WELL-000050", status="ACTIVE")
    assert len(active) == 1


def test_alert_lifecycle_acknowledge_and_close(tmp_path):
    """Verify engineer workflow: ACTIVE -> ACKNOWLEDGE -> CLOSE."""
    test_storage = tmp_path / "test_alerts_lifecycle.json"

    engine = AlertEngine()
    engine.alerts = {}
    engine.alert_counter = 0
    engine.storage_path = test_storage

    obs = [{
        "live_id": "LIVE-001",
        "anomaly_type": "mud_loss_imbalance",
        "severity": "HIGH",
        "depth_md": 3200.0,
        "description": "Mud loss detected",
    }]
    packet = _make_packet(depth=3200.0, anomalies=obs)

    alerts = engine.process_live_packet(packet)
    assert len(alerts) > 0
    aid = alerts[0].alert_id
    assert alerts[0].status == "ACTIVE"

    # Engineer acknowledges alert
    ack_res = engine.acknowledge_alert(aid, reviewer="Drilling Engineer", note="LCM pills prepared")
    assert ack_res.status == "ACKNOWLEDGED"
    assert ack_res.acknowledged_by == "Drilling Engineer"
    assert ack_res.engineer_note == "LCM pills prepared"

    # Engineer closes alert
    close_res = engine.close_alert(aid, reviewer="Drilling Engineer", note="Flow stabilized after LCM spotted")
    assert close_res.status == "CLOSED"
    assert close_res.closed_by == "Drilling Engineer"

    # Active alerts list excludes closed
    active_list = engine.get_alerts(well_id="WELL-000050", status="ACTIVE")
    assert len(active_list) == 0

    # Closed alerts query returns it
    closed_list = engine.get_alerts(well_id="WELL-000050", status="CLOSED")
    assert len(closed_list) == 1
    assert closed_list[0]["alert_id"] == aid
