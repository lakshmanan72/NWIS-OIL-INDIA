"""
NWIS Model Evaluation Utilities
===============================
Computes rigorous validation and test metrics for imbalanced hazard classification:
- Precision, Recall, F1
- ROC-AUC
- PR-AUC (Average Precision)
- Confusion Matrix (False Positives, False Negatives, True Positives, True Negatives)
"""

from typing import Dict, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def compute_metrics(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    threshold: float = 0.50,
) -> Dict[str, any]:
    """
    Computes all standard and operational drilling risk metrics.
    """
    y_true = np.asarray(y_true).astype(int)
    y_pred_proba = np.asarray(y_pred_proba).astype(float)
    y_pred = (y_pred_proba >= threshold).astype(int)

    # In case of constant targets in a tiny slice
    has_both_classes = len(np.unique(y_true)) > 1

    if has_both_classes:
        try:
            roc_auc = float(roc_auc_score(y_true, y_pred_proba))
        except Exception:
            roc_auc = 0.5
        try:
            pr_auc = float(average_precision_score(y_true, y_pred_proba))
        except Exception:
            pr_auc = float(np.mean(y_true))
    else:
        roc_auc = 0.5
        pr_auc = float(np.mean(y_true))

    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))

    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()

    return {
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "roc_auc": round(roc_auc, 4),
        "pr_auc": round(pr_auc, 4),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_positives": int(tp),
        "true_negatives": int(tn),
        "threshold": round(threshold, 4),
        "total_samples": int(len(y_true)),
        "positive_samples": int(np.sum(y_true)),
    }


def find_optimal_threshold(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    min_threshold: float = 0.15,
    max_threshold: float = 0.85,
    steps: int = 30,
) -> float:
    """
    Searches for threshold that optimizes F1-score on validation set.
    """
    best_thresh = 0.50
    best_f1 = -1.0

    thresholds = np.linspace(min_threshold, max_threshold, steps)
    for t in thresholds:
        y_pred = (y_pred_proba >= t).astype(int)
        f1 = f1_score(y_true, y_pred, zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_thresh = float(t)

    return best_thresh
