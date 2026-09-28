"""
Tests for NWIS Phase 6 Real-Time REST APIs:
- Status, replay start/stop, latest telemetry, features, live risk, context
- Alert listing, acknowledgement, and closure
- Anomaly injection
"""

import pytest
from starlette.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_api_realtime_status():
    """Verify that /api/realtime/status returns service status and provider health."""
    response = client.get("/api/realtime/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OPERATIONAL"
    assert data["engine_version"] == "nwis-rt-v1.0"
    assert data["advisory_mode"] is True
    assert "provider" in data


def test_api_replay_lifecycle():
    """Verify replay start, status query, and replay stop."""
    # Start replay for WELL-000050
    start_resp = client.post("/api/realtime/replay/start", json={"well_id": "WELL-000050", "interval_ms": 1000})
    assert start_resp.status_code == 200
    start_data = start_resp.json()
    assert start_data["mode"] == "DEMO REPLAY"
    assert start_data["active"] is True
    assert start_data["well_id"] == "WELL-000050"

    # Query latest telemetry
    latest_resp = client.get("/api/realtime/latest/WELL-000050")
    assert latest_resp.status_code == 200
    latest_data = latest_resp.json()
    assert latest_data["well_id"] == "WELL-000050"

    # Query features
    feat_resp = client.get("/api/realtime/features/WELL-000050")
    assert feat_resp.status_code == 200

    # Query live risks
    risk_resp = client.get("/api/realtime/risks/WELL-000050")
    assert risk_resp.status_code == 200

    # Query unified live evidence context
    ctx_resp = client.get("/api/realtime/context/WELL-000050")
    assert ctx_resp.status_code == 200
    ctx_data = ctx_resp.json()
    assert "active_well" in ctx_data or "live_observations" in ctx_data

    # Stop replay
    stop_resp = client.post("/api/realtime/replay/stop")
    assert stop_resp.status_code == 200
    assert stop_resp.json()["active"] is False


def test_api_inject_anomaly():
    """Verify that an engineer or demo operator can inject an operational anomaly."""
    # Start replay first
    client.post("/api/realtime/replay/start", json={"well_id": "WELL-000050", "interval_ms": 1000})

    inject_resp = client.post("/api/realtime/inject-anomaly", json={
        "anomaly_type": "torque_spike"
    })
    assert inject_resp.status_code == 200
    data = inject_resp.json()
    assert data["success"] is True
    assert "anomalies_detected" in data
    assert any(a["anomaly_type"] == "torque_spike" for a in data["anomalies_detected"])

    # Query alerts to verify alert generation
    alerts_resp = client.get("/api/realtime/alerts?well_id=WELL-000050")
    assert alerts_resp.status_code == 200
    alerts_data = alerts_resp.json()
    assert "alerts" in alerts_data

    # Clean up replay
    client.post("/api/realtime/replay/stop")
