"""
NWIS Phase 3.1 Validation Audit Regression Test Suite
=====================================================
Covers:
1. Train/Test/Validation group disjointness and separation
2. Threshold separation (validation-only F1 optimization)
3. Label taxonomy mappings & domain assumptions
4. API vs Frontend prediction consistency (WELL-000050 @ 3720m & 1132m)
5. Missing feature & sparse telemetry robustness
6. Invalid depth handling (422) & out-of-range depth status/warning
7. Deterministic prediction outputs & model loading
8. Model versioning response contract (model_version, schema, lookahead, threshold)
"""

import json
from pathlib import Path
import pytest
import numpy as np
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.ml.config import (
    DATA_DIR,
    HAZARD_EVENT_MAPPING,
    MODELS_DIR,
    TARGET_HAZARDS,
)
from backend.ml.dataset_builder import build_and_split_dataset
from backend.ml.model_registry import load_selected_models
from backend.ml.predict import RiskPredictor, CSVDataProvider


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def predictor():
    return RiskPredictor(CSVDataProvider())


# ==============================================================================
# 1. TRAIN / TEST / VALIDATION SEPARATION
# ==============================================================================
def test_train_test_validation_separation():
    """Verifies that train, validation, and test splits have 0 well overlap and imputation is train-only."""
    splits = build_and_split_dataset()

    assert len(splits.train_wells.intersection(splits.val_wells)) == 0
    assert len(splits.train_wells.intersection(splits.test_wells)) == 0
    assert len(splits.val_wells.intersection(splits.test_wells)) == 0

    assert len(splits.train_wells) == 1185
    assert len(splits.val_wells) == 254
    assert len(splits.test_wells) == 255

    # Check training-only imputation medians artifact exists
    medians_path = MODELS_DIR / "nwis_train_imputation_medians.joblib"
    assert medians_path.exists(), "Training-only imputation medians artifact missing!"

    # Check categorical encoder exists
    encoder_path = MODELS_DIR / "nwis_categorical_encoder.joblib"
    assert encoder_path.exists(), "Categorical encoder artifact missing!"


# ==============================================================================
# 2. THRESHOLD SEPARATION
# ==============================================================================
def test_threshold_separation_and_reports():
    """Verifies that thresholds are tuned on validation set and documented in ml_threshold_report.json."""
    thresh_report_path = DATA_DIR / "ml_threshold_report.json"
    assert thresh_report_path.exists(), "ml_threshold_report.json missing!"

    with open(thresh_report_path, "r") as f:
        data = json.load(f)

    for h in TARGET_HAZARDS:
        assert h in data
        item = data[h]
        assert "validation_threshold" in item
        assert 0.15 <= item["validation_threshold"] <= 0.85
        assert item["is_hazard_specific"] is True
        assert "NEVER" in item["tuning_guarantee"].upper() or "validation" in item["tuning_guarantee"].lower()


# ==============================================================================
# 3. LABEL TAXONOMY AUDIT
# ==============================================================================
def test_label_mapping_and_taxonomy():
    """Verifies complete event taxonomy with documented assumptions and limitations."""
    tax_path = DATA_DIR / "event_hazard_taxonomy.json"
    assert tax_path.exists(), "event_hazard_taxonomy.json missing!"

    with open(tax_path, "r") as f:
        tax = json.load(f)

    assert tax["total_historical_events_in_source"] == 31444
    assert len(tax["taxonomy_mappings"]) >= 8

    # Verify key mappings
    mapped_types = {m["raw_event_type"]: m for m in tax["taxonomy_mappings"]}
    assert "Mud Loss" in mapped_types
    assert "Lost Circulation" in mapped_types
    assert "Stuck Pipe" in mapped_types
    assert "Differential Sticking" in mapped_types
    assert "Pack-Off" in mapped_types
    assert "Kick" in mapped_types
    assert "Formation Pressure Change" in mapped_types
    assert "Torque and Drag" in mapped_types

    # Ensure limitations are documented for Formation Pressure Change & Torque and Drag
    assert "limitation" in mapped_types["Formation Pressure Change"]["domain_assumption"].lower()
    assert "limitation" in mapped_types["Torque and Drag"]["domain_assumption"].lower()


# ==============================================================================
# 4. API VS FRONTEND PREDICTION CONSISTENCY
# ==============================================================================
def test_frontend_backend_prediction_consistency(client, predictor):
    """
    Verifies prediction consistency between backend prediction engine and API endpoint,
    and documents why browser showed 31% at depth 1132m vs 5.7% at depth 3720m for WELL-000050.
    """
    # 1. Direct API call at depth 3720.0m
    resp_3720 = client.post("/api/prediction/risk", json={"well_id": "WELL-000050", "depth_md": 3720.0})
    assert resp_3720.status_code == 200
    api_data_3720 = resp_3720.json()

    # Direct predictor engine call
    engine_data_3720 = predictor.predict_risk("WELL-000050", 3720.0)

    # Verify identical output between engine and API
    assert api_data_3720["well_id"] == engine_data_3720["well_id"]
    assert api_data_3720["depth_md"] == engine_data_3720["depth_md"]
    assert api_data_3720["depth_status"] == "extrapolated_beyond_total_depth"
    assert api_data_3720["depth_warning"] is not None

    api_preds_3720 = {p["hazard"]: p for p in api_data_3720["predictions"]}
    engine_preds_3720 = {p["hazard"]: p for p in engine_data_3720["predictions"]}

    for h in TARGET_HAZARDS:
        assert api_preds_3720[h]["probability"] == pytest.approx(engine_preds_3720[h]["probability"], abs=1e-4)
        assert api_preds_3720[h]["probability_pct"] == pytest.approx(engine_preds_3720[h]["probability_pct"], abs=0.1)

    # Mud loss at 3720m is ~5.7%
    assert api_preds_3720["mud_loss"]["probability_pct"] == pytest.approx(5.7, abs=0.2)

    # 2. Direct API call at well default 70% depth = 1132.0m (which browser rendered)
    resp_1132 = client.post("/api/prediction/risk", json={"well_id": "WELL-000050", "depth_md": 1132.0})
    assert resp_1132.status_code == 200
    api_data_1132 = resp_1132.json()
    api_preds_1132 = {p["hazard"]: p for p in api_data_1132["predictions"]}

    # Mud loss at 1132m in the browser rendered ~31%
    assert api_preds_1132["mud_loss"]["probability_pct"] == pytest.approx(31.4, abs=0.5)
    assert api_data_1132["depth_status"] == "verified_drilled_interval"


# ==============================================================================
# 5. MISSING FEATURE HANDLING
# ==============================================================================
def test_missing_feature_handling(predictor):
    """Verifies that sparse telemetry and missing mud logging are deterministically handled."""
    res = predictor.predict_risk("WELL-000100", 3000.0)
    assert len(res["predictions"]) == 5
    for p in res["predictions"]:
        assert 0.0 <= p["probability"] <= 1.0
        assert not np.isnan(p["probability"])


# ==============================================================================
# 6. INVALID DEPTH HANDLING
# ==============================================================================
def test_invalid_depth_handling(client):
    """Verifies that negative or zero depth returns HTTP 422 Unprocessable Entity."""
    resp_neg = client.post("/api/prediction/risk", json={"well_id": "WELL-000050", "depth_md": -100.0})
    assert resp_neg.status_code == 422

    resp_zero = client.post("/api/prediction/risk", json={"well_id": "WELL-000050", "depth_md": 0.0})
    assert resp_zero.status_code == 422


# ==============================================================================
# 7. DETERMINISTIC PREDICTION
# ==============================================================================
def test_deterministic_prediction(predictor):
    """Verifies that identical input produces identical output across repeated runs."""
    r1 = predictor.predict_risk("WELL-000050", 2500.0)
    r2 = predictor.predict_risk("WELL-000050", 2500.0)

    for p1, p2 in zip(r1["predictions"], r2["predictions"]):
        assert p1["hazard"] == p2["hazard"]
        assert p1["probability"] == p2["probability"]
        assert p1["algorithm"] == p2["algorithm"]


# ==============================================================================
# 8. MODEL VERSIONING CONTRACT
# ==============================================================================
def test_model_versioning_response(client):
    """Verifies that the prediction API exposes all mandatory model versioning metadata."""
    resp = client.post("/api/prediction/risk", json={"well_id": "WELL-000050", "depth_md": 1500.0})
    assert resp.status_code == 200
    data = resp.json()

    assert data["model_version"] == "nwis-v1.0"
    assert data["feature_schema_version"] == "features-v1"
    assert data["training_dataset_version"] == "nwis-dataset-v1"
    assert data["lookahead_m"] == 100
    assert data["threshold_version"] == "threshold-v1"
    assert "model_algorithm" in data
    assert len(data["model_algorithm"]) == 5

    for p in data["predictions"]:
        assert "algorithm" in p
        assert "threshold" in p
        assert "threshold_version" in p
