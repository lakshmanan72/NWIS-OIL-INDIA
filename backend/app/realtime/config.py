"""
NWIS Phase 6 — Real-Time eRTMAC & Live Risk Engine Configuration
================================================================
Prototype engineering thresholds and telemetry parameters.
NOTE: These parameters are prototype engineering thresholds, not field-certified parameters.
"""

from typing import Any, Dict


REALTIME_CONFIG: Dict[str, Any] = {
    "system": {
        "engine_version": "nwis-rt-v1.0",
        "advisory_mode_only": True,
        "autonomous_control_permitted": False,
    },
    "replay": {
        "default_well_id": "WELL-000050",
        "replay_interval_ms": 1000,
        "default_telemetry_source": "nwis_daily_drilling_parameters_15108.csv",
        "auto_loop": True,
    },
    "freshness": {
        "live_threshold_seconds": 5.0,
        "delayed_threshold_seconds": 30.0,
        "stale_threshold_seconds": 60.0,
    },
    "features": {
        "rolling_window_samples": 15,
        "min_samples_for_baseline": 3,
    },
    "anomalies": {
        "torque": {
            "enabled": True,
            "sigma_threshold": 2.2,
            "min_delta_kftlb": 4.0,
        },
        "standpipe_pressure": {
            "enabled": True,
            "delta_psi_threshold": 250.0,
        },
        "flow_imbalance": {
            "enabled": True,
            "tolerance_pct": 8.0,
            "min_flow_lpm": 200.0,
        },
        "rop": {
            "enabled": True,
            "sudden_drop_pct": 40.0,
            "sudden_surge_pct": 60.0,
        },
    },
    "alerts": {
        "persistence_samples_required": 2,
        "cooldown_seconds": 30.0,
        "depth_grouping_window_m": 12.0,
        "auto_close_enabled": False,
    },
    "ml_inference": {
        "inference_cadence_samples": 3,
        "min_elevation_threshold": 0.20,
    },
}
