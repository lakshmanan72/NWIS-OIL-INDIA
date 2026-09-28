"""
Tests for NWIS Phase 6 Real-Time Feature Engine & Streaming Anomaly Detector:
- Rolling window statistics and Rate of Change (ROC)
- Flow in/out delta and imbalance percentage
- Deterministic anomaly detection rules (Torque spike, SPP surge, Mud loss imbalance, ROP drop)
"""

import pytest
from backend.app.realtime.schema import RealtimeTelemetryRecord
from backend.app.realtime.feature_engine import RealtimeFeatureEngine
from backend.app.realtime.anomaly_detector import StreamingAnomalyDetector


def _make_record(depth: float, torque: float = 15.0, spp: float = 1900.0, flow_in: float = 1300.0, flow_out: float = 1290.0, rop: float = 15.0):
    return RealtimeTelemetryRecord(
        timestamp="2026-09-27T10:00:00Z",
        well_id="WELL-000050",
        depth_md=depth,
        rop_m_hr=rop,
        wob_klbf=25.0,
        rpm=120.0,
        torque_kftlb=torque,
        standpipe_pressure_psi=spp,
        flow_rate_lpm=flow_in,
        mud_flow_in_lpm=flow_in,
        mud_flow_out_lpm=flow_out,
        mud_weight_ppg=10.5,
        gas_units=15.0,
    )


def test_feature_engine_rolling_calculations():
    """Verify that RealtimeFeatureEngine computes rolling means, maxes, and ROC without fabricating data."""
    engine = RealtimeFeatureEngine(default_window=10)

    # Ingest 5 baseline records
    history = []
    for i in range(5):
        rec = _make_record(depth=3000.0 + i, torque=14.0 + (i * 0.2))
        history.append(rec)

    features = engine.compute_features(history)

    assert "torque_rolling_mean" in features
    t_mean = features["torque_rolling_mean"]["value"]
    assert 14.0 <= t_mean <= 15.0
    assert "torque_roc" in features
    assert "rop_rolling_mean" in features


def test_flow_imbalance_computation():
    """Verify that flow differential and imbalance percentage are accurately computed."""
    engine = RealtimeFeatureEngine(default_window=10)

    # 1300 LPM in, 1000 LPM out
    history = [_make_record(depth=3100.0, flow_in=1300.0, flow_out=1000.0)]
    features = engine.compute_features(history)

    assert "flow_in_out_diff" in features
    diff = features["flow_in_out_diff"]["value"]
    assert diff == 300.0
    assert "flow_imbalance_pct" in features
    pct = features["flow_imbalance_pct"]["value"]
    assert pytest.approx(pct, rel=0.05) == 23.08


def test_torque_spike_anomaly_detection():
    """A sudden torque jump > 22 kft-lb must trigger torque_spike anomaly."""
    detector = StreamingAnomalyDetector()
    engine = RealtimeFeatureEngine()

    history = [_make_record(depth=3180.0 + i, torque=14.0) for i in range(5)]
    computed = engine.compute_features(history)

    # Spike record: 25.0 kft-lb
    spike_rec = _make_record(depth=3186.0, torque=25.0)
    anomalies = detector.detect_anomalies(spike_rec, computed)

    types = [a.anomaly_type for a in anomalies]
    assert "torque_spike" in types
    torque_anomaly = next(a for a in anomalies if a.anomaly_type == "torque_spike")
    assert torque_anomaly.severity in ["MEDIUM", "HIGH", "CRITICAL"]
    assert torque_anomaly.depth_md == 3186.0


def test_flow_loss_anomaly_detection():
    """Significant flow loss (flow_out << flow_in) must trigger mud_loss_imbalance anomaly."""
    detector = StreamingAnomalyDetector()
    engine = RealtimeFeatureEngine()

    history = [_make_record(depth=3190.0 + i, flow_in=1400.0, flow_out=1390.0) for i in range(5)]
    computed = engine.compute_features(history)

    # Loss record: 1400 in, 800 out (42.8% imbalance)
    loss_rec = _make_record(depth=3196.0, flow_in=1400.0, flow_out=800.0)
    anomalies = detector.detect_anomalies(loss_rec, computed)

    types = [a.anomaly_type for a in anomalies]
    assert "mud_loss_imbalance" in types
    loss_anomaly = next(a for a in anomalies if a.anomaly_type == "mud_loss_imbalance")
    assert loss_anomaly.severity in ["MEDIUM", "HIGH", "CRITICAL"]


def test_spp_surge_anomaly_detection():
    """A sudden standpipe pressure surge must trigger pressure_surge anomaly."""
    detector = StreamingAnomalyDetector()
    engine = RealtimeFeatureEngine()

    history = [_make_record(depth=3200.0 + i, spp=1800.0) for i in range(5)]
    computed = engine.compute_features(history)

    # Surge record: 2400 psi
    surge_rec = _make_record(depth=3206.0, spp=2400.0)
    anomalies = detector.detect_anomalies(surge_rec, computed)

    types = [a.anomaly_type for a in anomalies]
    assert "pressure_surge" in types
