"""
Tests for NWIS Phase 6 Real-Time Ingestion:
- Telemetry payload validation (numeric checks, range checks, invalid / warnings)
- LiveWellState tracking and freshness transitions
- DemoReplayProvider streaming
"""

import time
from datetime import datetime, timezone
import pytest
from backend.app.realtime.schema import validate_telemetry_payload, RealtimeTelemetryRecord
from backend.app.realtime.live_state import LiveWellState
from backend.app.realtime.providers import DemoReplayProvider


def test_validate_telemetry_payload_valid():
    """Verify that an authentic, well-formed telemetry payload passes validation."""
    now_ts = datetime.now(timezone.utc).isoformat()
    payload = {
        "timestamp": now_ts,
        "well_id": "WELL-000050",
        "depth_md": 3185.5,
        "rop_m_hr": 14.5,
        "wob_klbf": 25.0,
        "rpm": 120.0,
        "torque_kftlb": 16.5,
        "standpipe_pressure_psi": 1950.0,
        "flow_rate_lpm": 1300.0,
        "mud_flow_in_lpm": 1300.0,
        "mud_flow_out_lpm": 1290.0,
        "mud_weight_ppg": 10.5,
        "gas_units": 18.0,
    }
    is_valid, status, warnings, record = validate_telemetry_payload(payload)
    assert is_valid is True
    assert status == "VALID"
    assert len(warnings) == 0
    assert isinstance(record, RealtimeTelemetryRecord)
    assert record.well_id == "WELL-000050"
    assert record.depth_md == 3185.5
    assert record.rop_m_hr == 14.5


def test_validate_telemetry_payload_missing_required():
    """Missing well_id or timestamp must result in validation failure."""
    is_valid, status, warnings, record = validate_telemetry_payload({"depth_md": 2500.0})
    assert is_valid is False
    assert status == "INVALID"
    assert record is None
    assert any("missing required field" in w.lower() for w in warnings)


def test_validate_telemetry_payload_negative_depth():
    """Physical impossibility: negative depth must fail validation."""
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "well_id": "WELL-000050",
        "depth_md": -100.0,
    }
    is_valid, status, warnings, record = validate_telemetry_payload(payload)
    assert is_valid is False
    assert status == "INVALID"
    assert record is None
    assert any("negative" in w.lower() for w in warnings)


def test_validate_telemetry_payload_warnings_for_extreme_values():
    """Extreme / suspicious sensor readings must pass with warnings without crashing the pipeline."""
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "well_id": "WELL-000050",
        "depth_md": 2500.0,
        "rpm": 550.0,  # Extreme RPM > 350
        "mud_weight_ppg": 25.0,  # Extreme mud weight > 22
    }
    is_valid, status, warnings, record = validate_telemetry_payload(payload)
    assert is_valid is True
    assert status in ["VALID_WITH_WARNINGS", "SUSPECT"]
    assert record is not None
    assert len(warnings) >= 2


def test_live_well_state_freshness_transitions():
    """Verify state transitions: LIVE -> DELAYED -> STALE -> DISCONNECTED."""
    state = LiveWellState(well_id="WELL-000050")
    assert state.get_freshness_status() == "DISCONNECTED"

    record = RealtimeTelemetryRecord(
        timestamp=datetime.now(timezone.utc).isoformat(),
        well_id="WELL-000050",
        depth_md=3200.0,
        rop_m_hr=12.0,
    )

    state.update_telemetry(record, provider_mode="LIVE FIELD DATA", warnings=[])
    assert state.get_freshness_status() == "LIVE"
    quality = state.get_data_quality()
    assert quality["quality"] in ["GOOD", "DEGRADED"]
    assert state.current_depth == 3200.0

    # Simulate elapsed time < 5s -> LIVE
    state.last_update_epoch = time.time() - 2.0
    assert state.get_freshness_status() == "LIVE"

    # Simulate elapsed time 35s (delayed threshold is 30s) -> DELAYED
    state.last_update_epoch = time.time() - 35.0
    assert state.get_freshness_status() == "DELAYED"

    # Simulate elapsed time 70s (stale threshold is 60s) -> STALE
    state.last_update_epoch = time.time() - 70.0
    assert state.get_freshness_status() == "STALE"

    # Replay mode produces REPLAY
    state.update_telemetry(record, provider_mode="DEMO REPLAY", warnings=[])
    state.last_update_epoch = time.time() - 1.0
    assert state.get_freshness_status() == "REPLAY"


def test_demo_replay_provider_loading_and_step():
    """DemoReplayProvider must load historical telemetry from raw data and step through samples."""
    provider = DemoReplayProvider(default_well_id="WELL-000050")
    provider.subscribe("WELL-000050")
    assert provider.active_well_id == "WELL-000050"
    assert len(provider.records_cache["WELL-000050"]) > 0

    success = provider.connect()
    assert success is True
    assert provider.is_connected is True

    # Advance step
    record = provider.step()
    assert record is not None
    assert record.well_id == "WELL-000050"
    assert record.depth_md > 0

    provider.disconnect()
    assert provider.is_connected is False
