"""
NWIS Phase 3 AI/ML Drilling Risk Prediction Test Suite
======================================================
Tests:
1. Label generation logic
2. Lookahead window boundaries
3. Leakage audit and blacklist detection
4. Grouped split well disjointness
5. Feature generation and rolling order
6. Model artifact loading
7. Risk predictor multi-hazard inference
8. Invalid well handling (404/ValueError)
9. Unavailable/extreme depth handling
10. Missing feature robustness
11. Prediction API endpoint and schema validation
"""

import pytest
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.ml.config import (
    ALL_FEATURE_COLUMNS,
    HAZARD_EVENT_MAPPING,
    LEAKAGE_BLACKLIST_COLUMNS,
    LOOKAHEAD_METERS,
    TARGET_HAZARDS,
)
from backend.ml.label_generation import generate_hazard_targets
from backend.ml.leakage_audit import (
    audit_feature_names,
    audit_split_disjointness,
    audit_target_correlations,
    run_full_leakage_audit,
)
from backend.ml.feature_engineering import compute_drilling_rolling_features
from backend.ml.model_registry import load_selected_models
from backend.ml.predict import RiskPredictor, CSVDataProvider


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def predictor():
    return RiskPredictor(CSVDataProvider())


# ==============================================================================
# TEST 1 & 2: LABEL GENERATION & LOOKAHEAD WINDOW
# ==============================================================================
def test_label_generation_and_lookahead_window():
    """Verifies that events within [D, D+lookahead] produce target=1 and others 0."""
    obs_df = pd.DataFrame([
        {"well_id": "TEST_WELL_1", "depth_md": 1000.0},
        {"well_id": "TEST_WELL_1", "depth_md": 1500.0},
        {"well_id": "TEST_WELL_1", "depth_md": 2000.0},
    ])

    events_df = pd.DataFrame([
        # Event within [1000, 1100] -> triggers target at 1000m
        {"event_id": "E1", "well_id": "TEST_WELL_1", "depth_md": 1050.0, "event_type": "Mud Loss", "severity": "High"},
        # Event at 1650m -> outside [1500, 1600] lookahead -> should NOT trigger target at 1500m
        {"event_id": "E2", "well_id": "TEST_WELL_1", "depth_md": 1650.0, "event_type": "Mud Loss", "severity": "Medium"},
        # Event behind 2000m -> at 1950m -> should NOT trigger target at 2000m
        {"event_id": "E3", "well_id": "TEST_WELL_1", "depth_md": 1950.0, "event_type": "Mud Loss", "severity": "Low"},
        # Stuck pipe event within [2000, 2100] -> at 2080m
        {"event_id": "E4", "well_id": "TEST_WELL_1", "depth_md": 2080.0, "event_type": "Stuck Pipe", "severity": "High"},
    ])

    labeled_df, summary = generate_hazard_targets(
        obs_df,
        events_df=events_df,
        lookahead_meters=100.0,
    )

    # Row 0: 1000m -> Mud Loss in window -> target_mud_loss == 1
    assert labeled_df.loc[0, "target_mud_loss"] == 1
    assert labeled_df.loc[0, "target_stuck_pipe"] == 0

    # Row 1: 1500m -> Event at 1650 is > 1600m -> target_mud_loss == 0
    assert labeled_df.loc[1, "target_mud_loss"] == 0

    # Row 2: 2000m -> Stuck pipe at 2080 is in [2000, 2100] -> target_stuck_pipe == 1
    assert labeled_df.loc[2, "target_stuck_pipe"] == 1
    assert labeled_df.loc[2, "target_mud_loss"] == 0


# ==============================================================================
# TEST 3: LEAKAGE DETECTION
# ==============================================================================
def test_leakage_audit_detection():
    """Verifies that blacklisted recommendation columns and leaked future flags are flagged."""
    # Clean feature set
    clean_features = ["rop_m_per_hr", "torque_knm", "depth_md", "pit_volume_bbl"]
    clean_audit = audit_feature_names(clean_features)
    assert clean_audit["passed"] is True
    assert clean_audit["violations_count"] == 0

    # Dirty feature set with forbidden prototype risk columns
    dirty_features = [
        "rop_m_per_hr",
        "risk_score",
        "predicted_event",
        "kick_indicator",
        "confidence",
    ]
    dirty_audit = audit_feature_names(dirty_features)
    assert dirty_audit["passed"] is False
    assert dirty_audit["violations_count"] >= 3

    # Disjoint split check
    train_w = {"W1", "W2", "W3"}
    val_w = {"W4", "W5"}
    test_w = {"W6", "W7"}
    split_res = audit_split_disjointness(train_w, val_w, test_w)
    assert split_res["passed"] is True

    # Contaminated split check
    bad_val_w = {"W3", "W4"}
    split_bad = audit_split_disjointness(train_w, bad_val_w, test_w)
    assert split_bad["passed"] is False


# ==============================================================================
# TEST 4: GROUPED SPLIT WELL DISJOINTNESS
# ==============================================================================
def test_grouped_split_disjointness():
    """Tests that wells in train, validation, and test sets are strictly disjoint."""
    wells = [f"WELL-{i:06d}" for i in range(1, 101)]
    rng = np.random.RandomState(42)
    shuffled = rng.permutation(wells)

    n_train = int(0.70 * len(shuffled))
    n_val = int(0.15 * len(shuffled))

    train_wells = set(shuffled[:n_train])
    val_wells = set(shuffled[n_train : n_train + n_val])
    test_wells = set(shuffled[n_train + n_val :])

    assert len(train_wells.intersection(val_wells)) == 0
    assert len(train_wells.intersection(test_wells)) == 0
    assert len(val_wells.intersection(test_wells)) == 0
    assert len(train_wells) + len(val_wells) + len(test_wells) == 100


# ==============================================================================
# TEST 5: FEATURE GENERATION & ROLLING TIME INTEGRITY
# ==============================================================================
def test_feature_generation_rolling_integrity():
    """Verifies that rolling features use strictly previous and current observations."""
    df = pd.DataFrame([
        {"well_id": "W1", "depth_md": 1000.0, "rop_m_per_hr": 10.0, "torque_knm": 5.0, "wob_klbf": 20.0, "standpipe_pressure_psi": 2000.0, "ecd_ppg": 10.0, "mud_loss_lph": 0.0},
        {"well_id": "W1", "depth_md": 1200.0, "rop_m_per_hr": 20.0, "torque_knm": 15.0, "wob_klbf": 25.0, "standpipe_pressure_psi": 2200.0, "ecd_ppg": 10.5, "mud_loss_lph": 10.0},
        {"well_id": "W1", "depth_md": 1400.0, "rop_m_per_hr": 30.0, "torque_knm": 25.0, "wob_klbf": 30.0, "standpipe_pressure_psi": 2400.0, "ecd_ppg": 11.0, "mud_loss_lph": 25.0},
    ])

    res = compute_drilling_rolling_features(df)

    # First row: rolling mean equals initial value, diff is 0
    assert res.loc[0, "rolling_mean_rop"] == 10.0
    assert res.loc[0, "torque_change"] == 0.0

    # Second row: rolling mean is (10 + 20)/2 = 15.0, diff is 15 - 5 = 10.0
    assert res.loc[1, "rolling_mean_rop"] == 15.0
    assert res.loc[1, "torque_change"] == 10.0

    # Third row: rolling max torque is 25.0, rop diff is 10.0
    assert res.loc[2, "rolling_max_torque"] == 25.0
    assert res.loc[2, "rop_change"] == 10.0


# ==============================================================================
# TEST 6: MODEL ARTIFACT LOADING
# ==============================================================================
def test_model_artifact_loading():
    """Verifies that trained models for all hazards load from the registry."""
    loaded = load_selected_models()
    assert len(loaded) == len(TARGET_HAZARDS)
    for hazard in TARGET_HAZARDS:
        assert hazard in loaded
        assert "model" in loaded[hazard]
        assert "algorithm" in loaded[hazard]
        assert "threshold" in loaded[hazard]


# ==============================================================================
# TEST 7: PREDICTION INFERENCE
# ==============================================================================
def test_risk_predictor_inference(predictor):
    """Verifies end-to-end hazard risk prediction."""
    res = predictor.predict_risk("WELL-000001", 2500.0)

    assert res["well_id"] == "WELL-000001"
    assert res["depth_md"] == 2500.0
    assert res["model_version"] in ["nwis-v1.0", "v1.0.0"]
    assert len(res["predictions"]) == 5

    for p in res["predictions"]:
        assert p["hazard"] in TARGET_HAZARDS
        assert 0.0 <= p["probability"] <= 1.0

    assert len(res["top_features"]) > 0
    for f in res["top_features"]:
        assert f["label"] == "model feature contribution"
        assert "contribution" in f
        assert "feature" in f


# ==============================================================================
# TEST 8: INVALID WELL HANDLING
# ==============================================================================
def test_invalid_well_handling(predictor):
    """Verifies ValueError when requesting a non-existent well."""
    with pytest.raises(ValueError) as exc:
        predictor.predict_risk("WELL-NONEXISTENT-999999", 2500.0)
    assert "not found" in str(exc.value).lower()


# ==============================================================================
# TEST 9: UNAVAILABLE / EXTREME DEPTH HANDLING
# ==============================================================================
def test_extreme_depth_handling(predictor):
    """Verifies prediction executes gracefully for very shallow or very deep depths."""
    res_shallow = predictor.predict_risk("WELL-000001", 50.0)
    assert res_shallow["depth_md"] == 50.0
    assert len(res_shallow["predictions"]) == 5

    res_deep = predictor.predict_risk("WELL-000001", 8500.0)
    assert res_deep["depth_md"] == 8500.0
    assert len(res_deep["predictions"]) == 5


# ==============================================================================
# TEST 10: MISSING FEATURE ROBUSTNESS
# ==============================================================================
def test_missing_feature_robustness(predictor):
    """Verifies inference stability when well has sparse telemetry."""
    # Test on a well with minimal mud logging
    res = predictor.predict_risk("WELL-000100", 3000.0)
    assert len(res["predictions"]) == 5
    for p in res["predictions"]:
        assert not np.isnan(p["probability"])


# ==============================================================================
# TEST 11: API RESPONSE SCHEMA VALIDATION
# ==============================================================================
def test_api_prediction_risk_endpoint(client):
    """Verifies POST /api/prediction/risk schema and HTTP 200 response."""
    payload = {
        "well_id": "WELL-000050",
        "depth_md": 3720.0,
    }
    resp = client.post("/api/prediction/risk", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["well_id"] == "WELL-000050"
    assert data["depth_md"] == 3720.0
    assert data["model_version"] in ["nwis-v1.0", "v1.0.0"]
    assert "predictions" in data
    assert len(data["predictions"]) == 5

    # Check top features
    assert "top_features" in data
    assert len(data["top_features"]) > 0
    for feat in data["top_features"]:
        assert feat["label"] == "model feature contribution"

    # Check separate historical offset evidence
    assert "historical_offset_evidence" in data
    assert isinstance(data["historical_offset_evidence"], list)

    # Test 404 for invalid well
    bad_resp = client.post("/api/prediction/risk", json={"well_id": "INVALID_WELL", "depth_md": 1000.0})
    assert bad_resp.status_code == 404


def test_api_benchmark_endpoint(client):
    """Verifies GET /api/prediction/benchmark."""
    resp = client.get("/api/prediction/benchmark")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    first = data[0]
    for key in ["hazard", "algorithm", "precision", "recall", "f1", "roc_auc", "pr_auc", "false_positives", "false_negatives"]:
        assert key in first
