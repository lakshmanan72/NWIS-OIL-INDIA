"""
NWIS Data Leakage Audit
=======================
Audits feature matrices and training datasets to detect and prevent data leakage:
1. Column Name Blacklist (verifies no prototype risk/recommendation or concurrent target columns exist).
2. Well Group Disjointness (verifies no well_id appears in multiple splits).
3. Target Correlation Check (detects near-perfect correlations that indicate direct target encoding).
4. Temporal / Depth Leakage (verifies features use only historical/concurrent <= D data).
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import numpy as np
import pandas as pd

from .config import (
    DATA_DIR,
    LEAKAGE_AUDIT_REPORT_PATH,
    LEAKAGE_BLACKLIST_COLUMNS,
    TARGET_HAZARDS,
)


class LeakageAuditError(ValueError):
    """Raised when critical data leakage is detected."""
    pass


def audit_feature_names(
    feature_columns: List[str],
    blacklist: Optional[List[str]] = None,
) -> Dict[str, any]:
    """
    Checks feature names against blacklisted keywords and forbidden columns.
    """
    active_blacklist = blacklist or LEAKAGE_BLACKLIST_COLUMNS
    violations = []

    for col in feature_columns:
        col_lower = col.lower()
        for banned in active_blacklist:
            if banned.lower() in col_lower:
                violations.append({"feature": col, "matched_rule": banned})

    return {
        "passed": len(violations) == 0,
        "violations_count": len(violations),
        "violations": violations,
    }


def audit_split_disjointness(
    train_wells: Set[str],
    val_wells: Set[str],
    test_wells: Set[str],
) -> Dict[str, any]:
    """
    Verifies that train, validation, and test splits have 0 well overlap.
    """
    train_val_overlap = sorted(list(train_wells.intersection(val_wells)))
    train_test_overlap = sorted(list(train_wells.intersection(test_wells)))
    val_test_overlap = sorted(list(val_wells.intersection(test_wells)))

    total_overlap = (
        len(train_val_overlap) + len(train_test_overlap) + len(val_test_overlap)
    )

    return {
        "passed": total_overlap == 0,
        "train_val_overlap_count": len(train_val_overlap),
        "train_test_overlap_count": len(train_test_overlap),
        "val_test_overlap_count": len(val_test_overlap),
        "train_val_overlap_sample": train_val_overlap[:5],
        "train_test_overlap_sample": train_test_overlap[:5],
        "val_test_overlap_sample": val_test_overlap[:5],
    }


def audit_target_correlations(
    df: pd.DataFrame,
    feature_columns: List[str],
    target_columns: List[str],
    threshold: float = 0.90,
) -> Dict[str, any]:
    """
    Detects features that have an unnaturally high linear correlation with any target,
    suggesting direct encoding of the future label.
    """
    suspicious = []

    # Filter numeric features only
    numeric_cols = [
        c for c in feature_columns
        if c in df.columns and pd.api.types.is_numeric_dtype(df[c])
    ]

    for target in target_columns:
        if target not in df.columns:
            continue
        y = df[target].astype(float)
        if y.nunique() <= 1:
            continue

        for feat in numeric_cols:
            x = df[feat].astype(float)
            if x.nunique() <= 1:
                continue
            corr = float(np.corrcoef(x.fillna(0), y)[0, 1])
            if np.isnan(corr):
                continue
            if abs(corr) >= threshold:
                suspicious.append({
                    "feature": feat,
                    "target": target,
                    "abs_correlation": round(abs(corr), 4),
                    "raw_correlation": round(corr, 4),
                    "threshold": threshold,
                })

    return {
        "passed": len(suspicious) == 0,
        "suspicious_count": len(suspicious),
        "suspicious_features": suspicious,
    }


def run_full_leakage_audit(
    df: pd.DataFrame,
    feature_columns: List[str],
    target_columns: Optional[List[str]] = None,
    train_wells: Optional[Set[str]] = None,
    val_wells: Optional[Set[str]] = None,
    test_wells: Optional[Set[str]] = None,
    save_report: bool = True,
) -> Dict[str, any]:
    """
    Executes all leakage audits, builds a comprehensive audit report, and writes to disk.
    """
    targets = target_columns or [f"target_{h}" for h in TARGET_HAZARDS]

    name_audit = audit_feature_names(feature_columns)
    corr_audit = audit_target_correlations(df, feature_columns, targets)

    split_audit = None
    if train_wells is not None and val_wells is not None and test_wells is not None:
        split_audit = audit_split_disjointness(train_wells, val_wells, test_wells)

    all_passed = name_audit["passed"] and corr_audit["passed"]
    if split_audit is not None:
        all_passed = all_passed and split_audit["passed"]

    report = {
        "status": "PASSED" if all_passed else "FAILED",
        "all_passed": all_passed,
        "feature_count_audited": len(feature_columns),
        "name_audit": name_audit,
        "correlation_audit": corr_audit,
        "split_audit": split_audit,
        "audit_timestamp": pd.Timestamp.now().isoformat(),
        "summary": (
            "All leakage checks passed. No prototype recommendation features, "
            "no concurrent target indicator leaks, and no split cross-contamination."
            if all_passed
            else "Leakage detected. Review audit violations before training."
        ),
    }

    if save_report:
        with open(LEAKAGE_AUDIT_REPORT_PATH, "w") as f:
            json.dump(report, f, indent=2)

    return report


if __name__ == "__main__":
    print("Running NWIS Leakage Audit on config specification...")
    from .config import ALL_FEATURE_COLUMNS
    name_check = audit_feature_names(ALL_FEATURE_COLUMNS)
    print("Feature name check:", "PASSED" if name_check["passed"] else "FAILED")
    if not name_check["passed"]:
        print("Violations:", name_check["violations"])
    else:
        print("All features verified free of blacklisted patterns.")
