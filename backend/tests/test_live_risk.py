"""
Tests for NWIS Phase 6 Live Risk Engine:
- Phase 3.1 ML risk model inference driven by real-time telemetry
- Context builder integration with depth and formation correlations
- Strict source separation: LIVE-XXX for real-time telemetry vs EVID-XXX for approved documents
- Unified LiveEvidencePacket serialization
"""

import pytest
from backend.app.realtime.schema import RealtimeTelemetryRecord
from backend.app.realtime.anomaly_detector import StreamingAnomaly
from backend.app.realtime.live_risk_engine import LiveRiskEngine, LiveEvidencePacket


def test_live_risk_engine_inference_and_source_separation():
    """Verify that LiveRiskEngine predicts risks using Phase 3.1 models and formats live observations as LIVE-XXX."""
    engine = LiveRiskEngine()

    record = RealtimeTelemetryRecord(
        timestamp="2026-09-27T10:00:00Z",
        well_id="WELL-000050",
        depth_md=3185.0,
        rop_m_hr=8.5,
        wob_klbf=25.0,
        rpm=95.0,
        torque_kftlb=28.5,
        standpipe_pressure_psi=2200.0,
        flow_rate_lpm=1300.0,
        mud_flow_in_lpm=1300.0,
        mud_flow_out_lpm=1100.0,
        mud_weight_ppg=10.5,
        gas_units=22.0,
    )

    anomalies = [
        StreamingAnomaly(
            anomaly_id="ANOM-TRQ-0001",
            anomaly_type="torque_spike",
            severity="HIGH",
            depth_md=3185.0,
            observed_value=28.5,
            baseline_value=15.0,
            delta=13.5,
            unit="kft-lb",
            timestamp="2026-09-27T10:00:00Z",
            description="Elevated torque spike",
        )
    ]

    packet = engine.evaluate_live_risk(
        record=record,
        anomalies=anomalies,
        provider_mode="DEMO REPLAY",
        data_quality={"quality": "GOOD"}
    )

    assert isinstance(packet, LiveEvidencePacket)
    assert packet.active_well == "WELL-000050"
    assert packet.current_depth == 3185.0
    assert packet.formation is not None

    # Verify model risk indicators
    assert len(packet.model_risk_indicators) > 0

    # Verify LIVE observations are strictly prefixed with LIVE-
    assert len(packet.live_observations) > 0
    for obs in packet.live_observations:
        assert obs["live_id"].startswith("LIVE-")

    # Verify document evidence items (if present) are strictly prefixed with EVID-
    if packet.document_evidence:
        for doc in packet.document_evidence:
            if "evidence_id" in doc:
                assert doc["evidence_id"].startswith("EVID-")

    # Verify serialized dict
    packet_dict = packet.to_dict()
    assert packet_dict["active_well"] == "WELL-000050"
    assert "live_observations" in packet_dict
    assert "model_risk_indicators" in packet_dict
    assert "document_evidence" in packet_dict
