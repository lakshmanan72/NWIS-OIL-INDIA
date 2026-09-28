"""
NWIS Model Registry & Selection Engine
======================================
Implements objective, documented model selection across evaluated algorithms:
- Random Forest
- XGBoost
- LightGBM
- CatBoost

Rules:
------
- Does NOT assume any algorithm is superior.
- Ranks models per hazard using configurable PRIMARY_METRIC (default: pr_auc)
  and SECONDARY_METRIC (default: recall).
- Serializes winning model artifacts with version tags into models/.
- Saves detailed decision justification into data/model_selection_report.json.
- Provides model loading utility for production inference.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import joblib
import pandas as pd

from .config import (
    COMPARISON_CSV_PATH,
    MODELS_DIR,
    PRIMARY_METRIC,
    SECONDARY_METRIC,
    SELECTION_REPORT_PATH,
    TARGET_HAZARDS,
)


def select_best_models(
    comparison_df: pd.DataFrame,
    trained_models: Dict[str, Dict[str, Any]],
    splits: Optional[Any] = None,
    primary_metric: str = PRIMARY_METRIC,
    secondary_metric: str = SECONDARY_METRIC,
) -> Dict[str, Dict[str, Any]]:
    """
    Objectively selects the highest-performing model per hazard using VALIDATION results strictly.
    Held-out test metrics are evaluated ONLY AFTER model selection and threshold locking.
    """
    from .evaluate import compute_metrics

    selection_report = {
        "selection_policy": {
            "primary_metric": primary_metric,
            "secondary_metric": secondary_metric,
            "rule": (
                f"Rank models descending by validation {primary_metric}; break ties using validation {secondary_metric}. "
                "Highest ranked model is automatically locked and deployed. "
                "Held-out test metrics are computed strictly after selection is finalized."
            ),
            "selection_split": "validation_wells (15%)",
            "evaluation_split": "held_out_test_wells (15%)",
        },
        "selected_models": {},
        "all_rankings": {},
    }

    for hazard in TARGET_HAZARDS:
        haz_df = comparison_df[comparison_df["hazard"] == hazard].copy()
        if haz_df.empty:
            continue

        # Sort by primary then secondary metric descending on VALIDATION metrics
        haz_df = haz_df.sort_values(
            by=[primary_metric, secondary_metric],
            ascending=[False, False],
        ).reset_index(drop=True)

        winner_row = haz_df.iloc[0]
        winner_alg = winner_row["algorithm"]
        winner_model_data = trained_models[hazard][winner_alg]
        winner_model = winner_model_data["model"]
        winner_thresh = float(winner_model_data["threshold"])

        # Compute held-out test metrics strictly AFTER model selection and threshold locking
        if splits is not None:
            test_probs = winner_model.predict_proba(splits.X_test)[:, 1]
            test_metrics = compute_metrics(
                splits.y_test[hazard].values,
                test_probs,
                threshold=winner_thresh,
            )
        else:
            test_metrics = winner_row.to_dict()

        # Versioned artifact name
        model_filename = f"nwis_{hazard}_{winner_alg.lower().replace(' ', '_')}_v1.joblib"
        model_path = MODELS_DIR / model_filename

        # Save winning model artifact with locked threshold and test metrics
        joblib.dump(
            {
                "hazard": hazard,
                "algorithm": winner_alg,
                "model": winner_model,
                "threshold": winner_thresh,
                "validation_metrics": winner_row.to_dict(),
                "metrics": test_metrics,
                "feature_columns": winner_model_data["feature_columns"],
                "version": "1.0.0",
                "model_version": "nwis-v1.0",
                "threshold_version": "threshold-v1",
                "selection_split": "validation",
            },
            model_path,
        )

        # Also save a canonical link/copy: nwis_<hazard>_selected_v1.joblib
        canonical_path = MODELS_DIR / f"nwis_{hazard}_selected_v1.joblib"
        joblib.dump(
            {
                "hazard": hazard,
                "algorithm": winner_alg,
                "model": winner_model,
                "threshold": winner_thresh,
                "validation_metrics": winner_row.to_dict(),
                "metrics": test_metrics,
                "feature_columns": winner_model_data["feature_columns"],
                "version": "1.0.0",
                "model_version": "nwis-v1.0",
                "threshold_version": "threshold-v1",
                "selection_split": "validation",
            },
            canonical_path,
        )

        selection_report["selected_models"][hazard] = {
            "selected_algorithm": winner_alg,
            "artifact_path": str(model_path.name),
            "canonical_artifact": str(canonical_path.name),
            "primary_metric_name": primary_metric,
            "validation_primary_metric_score": float(winner_row[primary_metric]),
            "secondary_metric_name": secondary_metric,
            "validation_secondary_metric_score": float(winner_row[secondary_metric]),
            "validation_roc_auc": float(winner_row["roc_auc"]),
            "validation_f1": float(winner_row["f1"]),
            "threshold": winner_thresh,
            "test_pr_auc": float(test_metrics["pr_auc"]),
            "test_roc_auc": float(test_metrics["roc_auc"]),
            "test_precision": float(test_metrics["precision"]),
            "test_recall": float(test_metrics["recall"]),
            "test_f1": float(test_metrics["f1"]),
            "false_positives": int(test_metrics["false_positives"]),
            "false_negatives": int(test_metrics["false_negatives"]),
        }

        selection_report["all_rankings"][hazard] = haz_df.to_dict(orient="records")

    with open(SELECTION_REPORT_PATH, "w") as f:
        json.dump(selection_report, f, indent=2)

    return selection_report


def load_selected_models() -> Dict[str, Dict[str, Any]]:
    """
    Loads all active winning hazard models from models/ directory.
    """
    loaded = {}
    for hazard in TARGET_HAZARDS:
        canonical_path = MODELS_DIR / f"nwis_{hazard}_selected_v1.joblib"
        if canonical_path.exists():
            data = joblib.load(canonical_path)
            loaded[hazard] = data
    return loaded
