"""
NWIS Multi-Model Training & Benchmark Runner
===========================================
Trains and benchmarks 4 machine learning algorithms across all 5 drilling hazards:
1. Random Forest
2. XGBoost
3. LightGBM
4. CatBoost

Strict Evaluation Protocol:
---------------------------
- Models trained strictly on Grouped Train Wells (70%).
- Hyperparameters and decision thresholds tuned on Grouped Validation Wells (15%).
- Out-of-sample performance measured strictly on Grouped Held-Out Test Wells (15%).
- Zero cross-well data leakage.
- Comparison metrics saved to data/ml_model_comparison.csv.
- Objective model selection saved to data/model_selection_report.json.
"""

import time
from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier

# Optional / safe imports for LightGBM and CatBoost
try:
    from lightgbm import LGBMClassifier
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False

try:
    from catboost import CatBoostClassifier
    HAS_CATBOOST = True
except ImportError:
    HAS_CATBOOST = False

from .config import (
    COMPARISON_CSV_PATH,
    PRIMARY_METRIC,
    SECONDARY_METRIC,
    TARGET_HAZARDS,
)
from .dataset_builder import DatasetSplits, build_and_split_dataset
from .evaluate import compute_metrics, find_optimal_threshold
from .model_registry import select_best_models


def create_model_candidates(
    pos_count: int,
    neg_count: int,
    random_seed: int = 42,
) -> Dict[str, Any]:
    """
    Creates instances of the 4 benchmark algorithms with class-imbalance compensations.
    """
    scale_pos = max(1.0, float(neg_count) / max(1.0, float(pos_count)))

    models = {}

    # 1. Random Forest
    models["Random Forest"] = RandomForestClassifier(
        n_estimators=100,
        max_depth=8,
        min_samples_split=5,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=random_seed,
        n_jobs=-1,
    )

    # 2. XGBoost
    models["XGBoost"] = XGBClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos,
        eval_metric="logloss",
        random_state=random_seed,
        n_jobs=-1,
    )

    # 3. LightGBM
    if HAS_LIGHTGBM:
        models["LightGBM"] = LGBMClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=scale_pos,
            verbose=-1,
            random_state=random_seed,
            n_jobs=-1,
        )

    # 4. CatBoost
    if HAS_CATBOOST:
        models["CatBoost"] = CatBoostClassifier(
            iterations=100,
            depth=5,
            learning_rate=0.05,
            auto_class_weights="Balanced",
            verbose=0,
            random_seed=random_seed,
        )

    return models


def train_and_benchmark(
    splits: DatasetSplits,
) -> Tuple[pd.DataFrame, Dict[str, Dict[str, Any]]]:
    """
    Trains and validates all algorithms across all 5 hazards.
    """
    comparison_records = []
    trained_artifacts = {}

    print("\n" + "=" * 65)
    print("BEGINNING NWIS MULTI-MODEL BENCHMARK (RF, XGBoost, LightGBM, CatBoost)")
    print("=" * 65)

    for hazard in TARGET_HAZARDS:
        print(f"\n>>> Training Models for Hazard: [{hazard.upper()}] <<<")
        y_train_h = splits.y_train[hazard]
        y_val_h = splits.y_val[hazard]
        y_test_h = splits.y_test[hazard]

        pos_train = int(y_train_h.sum())
        neg_train = int(len(y_train_h) - pos_train)
        pos_test = int(y_test_h.sum())
        print(f"  Train: {pos_train} pos / {neg_train} neg | Test: {pos_test} pos")

        # Check sufficiency failure condition
        if pos_train < 10:
            print(f"  [WARNING] Insufficient validated labels for hazard: {hazard}")
            for alg in ["Random Forest", "XGBoost", "LightGBM", "CatBoost"]:
                comparison_records.append({
                    "hazard": hazard,
                    "algorithm": alg,
                    "precision": 0.0,
                    "recall": 0.0,
                    "f1": 0.0,
                    "roc_auc": 0.5,
                    "pr_auc": 0.0,
                    "false_positives": 0,
                    "false_negatives": int(pos_test),
                })
            continue

        model_candidates = create_model_candidates(pos_train, neg_train)
        trained_artifacts[hazard] = {}

        for alg_name, model in model_candidates.items():
            t0 = time.time()
            # Fit on training set
            model.fit(splits.X_train, y_train_h)

            # Predict validation probabilities
            val_probs = model.predict_proba(splits.X_val)[:, 1]
            optimal_thresh = find_optimal_threshold(y_val_h.values, val_probs)

            # Evaluate metrics STRICTLY on validation set for model selection
            val_metrics = compute_metrics(y_val_h.values, val_probs, threshold=optimal_thresh)
            elapsed = time.time() - t0

            print(
                f"  - {alg_name:13s} (took {elapsed:.1f}s): "
                f"Val PR-AUC={val_metrics['pr_auc']:.3f} | Val ROC-AUC={val_metrics['roc_auc']:.3f} | "
                f"Val Rec={val_metrics['recall']:.3f} | Val Prec={val_metrics['precision']:.3f} | Val F1={val_metrics['f1']:.3f} | "
                f"Val FP={val_metrics['false_positives']:3d} | Val FN={val_metrics['false_negatives']:2d} | "
                f"Thresh={optimal_thresh:.2f}"
            )

            record = {
                "hazard": hazard,
                "algorithm": alg_name,
                "precision": val_metrics["precision"],
                "recall": val_metrics["recall"],
                "f1": val_metrics["f1"],
                "roc_auc": val_metrics["roc_auc"],
                "pr_auc": val_metrics["pr_auc"],
                "false_positives": val_metrics["false_positives"],
                "false_negatives": val_metrics["false_negatives"],
                "threshold": optimal_thresh,
            }
            comparison_records.append(record)

            trained_artifacts[hazard][alg_name] = {
                "model": model,
                "threshold": optimal_thresh,
                "val_metrics": val_metrics,
                "feature_columns": splits.feature_columns,
            }

    comparison_df = pd.DataFrame(comparison_records)
    comparison_df.to_csv(COMPARISON_CSV_PATH, index=False)
    print(f"\nSaved benchmark validation comparison table to: {COMPARISON_CSV_PATH}")

    return comparison_df, trained_artifacts


def run_pipeline() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    End-to-end execution:
    Dataset build -> Multi-model benchmark on Validation -> Objective selection -> Held-out test evaluation -> Model artifact save.
    """
    splits = build_and_split_dataset()
    comparison_df, trained_artifacts = train_and_benchmark(splits)

    print("\n" + "=" * 65)
    print("OBJECTIVE MODEL SELECTION & ARTIFACT REGISTRATION (VALIDATION-ONLY)")
    print("=" * 65)
    selection_report = select_best_models(
        comparison_df=comparison_df,
        trained_models=trained_artifacts,
        splits=splits,
        primary_metric=PRIMARY_METRIC,
        secondary_metric=SECONDARY_METRIC,
    )

    print("\nSelected Winning Models per Hazard (Tuned on Validation, Evaluated on Held-out Test):")
    for haz, info in selection_report["selected_models"].items():
        print(
            f"  * {haz:14s}: {info['selected_algorithm']:13s} -> "
            f"Val PR-AUC: {info['validation_primary_metric_score']:.4f}, "
            f"Val Rec: {info['validation_secondary_metric_score']:.4f} | "
            f"Test PR-AUC: {info['test_pr_auc']:.4f}, Test ROC-AUC: {info['test_roc_auc']:.4f}"
        )

    return comparison_df, selection_report


if __name__ == "__main__":
    run_pipeline()
