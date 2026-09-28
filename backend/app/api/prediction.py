"""
NWIS AI/ML Drilling Risk Prediction API Endpoints
================================================
Exposes POST /api/prediction/risk and model inspection endpoints.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.ml.predict import RiskPredictor, CSVDataProvider
from backend.ml.config import COMPARISON_CSV_PATH, SELECTION_REPORT_PATH
import json
import pandas as pd

router = APIRouter(prefix="/api/prediction", tags=["ML Drilling Risk Prediction"])

# Global singleton predictor instance
_predictor: Optional[RiskPredictor] = None


def get_predictor() -> RiskPredictor:
    global _predictor
    if _predictor is None:
        _predictor = RiskPredictor(CSVDataProvider())
    return _predictor


class RiskPredictionRequest(BaseModel):
    well_id: str = Field(..., description="Canonical well ID (e.g. WELL-000050)", json_schema_extra={"example": "WELL-000050"})
    depth_md: float = Field(..., description="Measured depth in meters", json_schema_extra={"example": 3720.0})


class HazardPrediction(BaseModel):
    hazard: str
    probability: float
    probability_pct: Optional[float] = None
    algorithm: Optional[str] = None
    threshold: Optional[float] = None
    threshold_version: Optional[str] = "threshold-v1"


class FeatureContribution(BaseModel):
    feature: str
    contribution: float
    feature_value: Optional[float] = None
    label: str = "model feature contribution"
    hazard: Optional[str] = None


class RiskPredictionResponse(BaseModel):
    well_id: str
    depth_md: float
    formation: Optional[str] = None
    lithology: Optional[str] = None
    model_version: str = "nwis-v1.0"
    model_algorithm: Optional[Dict[str, str]] = None
    training_dataset_version: str = "nwis-dataset-v1"
    feature_schema_version: str = "features-v1"
    lookahead_m: float = 100.0
    threshold_version: str = "threshold-v1"
    depth_status: str = "verified_drilled_interval"
    depth_warning: Optional[str] = None
    predictions: List[HazardPrediction]
    top_features: List[FeatureContribution]
    historical_offset_evidence: Optional[List[str]] = None
    offset_summary: Optional[Dict[str, Any]] = None


@router.post("/risk", response_model=RiskPredictionResponse)
def predict_drilling_risk(req: RiskPredictionRequest):
    """
    Predicts upcoming drilling hazard probabilities for a given well and depth.
    Lookahead window: 100 meters ahead.
    """
    if req.depth_md <= 0 or pd.isna(req.depth_md):
        raise HTTPException(status_code=422, detail="Invalid depth_md: depth must be a positive finite number.")

    predictor = get_predictor()
    if not predictor.models_data:
        raise HTTPException(status_code=503, detail="Trained hazard risk models are unavailable.")

    try:
        result = predictor.predict_risk(req.well_id, req.depth_md)
        return result
    except ValueError as e:
        err_msg = str(e).lower()
        if "not found" in err_msg:
            raise HTTPException(status_code=404, detail=str(e))
        elif "invalid depth" in err_msg:
            raise HTTPException(status_code=422, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")


@router.get("/benchmark")
def get_benchmark_comparison():
    """
    Returns the benchmark comparison results across all evaluated algorithms and hazards.
    """
    if COMPARISON_CSV_PATH.exists():
        df = pd.read_csv(COMPARISON_CSV_PATH)
        return df.to_dict(orient="records")
    return []


@router.get("/selection-report")
def get_model_selection_report():
    """
    Returns the documented model selection report and winner ranking.
    """
    if SELECTION_REPORT_PATH.exists():
        with open(SELECTION_REPORT_PATH, "r") as f:
            return json.load(f)
    return {}
