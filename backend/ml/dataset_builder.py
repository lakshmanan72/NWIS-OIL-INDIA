"""
NWIS Dataset Builder & Grouped Well Splitter
============================================
Builds the complete modeling dataset by combining:
1. Engineered Features (Drilling, Mud, Geology, Offsets)
2. Verified Ground-Truth Hazard Labels (100m Lookahead Window)
3. Grouped Train/Validation/Test Split by well_id (70% / 15% / 15%)
4. Categorical Preprocessing & Pipeline Encoders
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import OrdinalEncoder

from .config import (
    ALL_FEATURE_COLUMNS,
    CATEGORICAL_FEATURES,
    DATA_DIR,
    DATASET_PATHS,
    LOOKAHEAD_METERS,
    MODELS_DIR,
    RANDOM_SEED,
    TARGET_HAZARDS,
    TEST_RATIO,
    TRAIN_RATIO,
    VAL_RATIO,
)
from .feature_engineering import build_full_feature_matrix
from .label_generation import generate_hazard_targets
from .leakage_audit import run_full_leakage_audit


class DatasetSplits:
    """Container for train, validation, and test splits."""
    def __init__(
        self,
        X_train: pd.DataFrame,
        y_train: Dict[str, pd.Series],
        X_val: pd.DataFrame,
        y_val: Dict[str, pd.Series],
        X_test: pd.DataFrame,
        y_test: Dict[str, pd.Series],
        train_wells: Set[str],
        val_wells: Set[str],
        test_wells: Set[str],
        encoder: OrdinalEncoder,
        feature_columns: List[str],
    ):
        self.X_train = X_train
        self.y_train = y_train
        self.X_val = X_val
        self.y_val = y_val
        self.X_test = X_test
        self.y_test = y_test
        self.train_wells = train_wells
        self.val_wells = val_wells
        self.test_wells = test_wells
        self.encoder = encoder
        self.feature_columns = feature_columns


def build_and_split_dataset(
    lookahead_meters: float = LOOKAHEAD_METERS,
    save_preprocessed: bool = True,
) -> DatasetSplits:
    """
    Constructs the end-to-end dataset with features, labels, and grouped splits.
    """
    print(f"Building NWIS ML Dataset with lookahead window: {lookahead_meters}m...")
    daily = pd.read_csv(DATASET_PATHS["daily_drilling"])

    # 1. Feature Engineering
    features_df = build_full_feature_matrix(daily)

    # 2. Label Generation
    labeled_df, label_summary = generate_hazard_targets(
        features_df,
        lookahead_meters=lookahead_meters,
    )

    # 3. Grouped Well Split (70% Train, 15% Val, 15% Test)
    unique_wells = np.array(sorted(labeled_df["well_id"].unique()))
    rng = np.random.RandomState(RANDOM_SEED)
    shuffled_wells = rng.permutation(unique_wells)

    n_total = len(shuffled_wells)
    n_train = int(TRAIN_RATIO * n_total)
    n_val = int(VAL_RATIO * n_total)

    train_wells = set(shuffled_wells[:n_train])
    val_wells = set(shuffled_wells[n_train : n_train + n_val])
    test_wells = set(shuffled_wells[n_train + n_val :])

    # Disjointness checks
    assert len(train_wells.intersection(val_wells)) == 0, "Train and Val wells overlap!"
    assert len(train_wells.intersection(test_wells)) == 0, "Train and Test wells overlap!"
    assert len(val_wells.intersection(test_wells)) == 0, "Val and Test wells overlap!"

    print(
        f"Grouped Well Split: {len(train_wells)} Train wells | "
        f"{len(val_wells)} Val wells | {len(test_wells)} Test wells"
    )

    # 4. Leakage Audit
    audit_report = run_full_leakage_audit(
        labeled_df,
        feature_columns=ALL_FEATURE_COLUMNS,
        train_wells=train_wells,
        val_wells=val_wells,
        test_wells=test_wells,
        save_report=True,
    )
    if not audit_report["all_passed"]:
        raise ValueError(f"Leakage audit failed: {audit_report}")
    print("Leakage Audit: PASSED (Zero data leakage confirmed).")

    # 5. Categorical Encoding Pipeline
    train_mask = labeled_df["well_id"].isin(train_wells)
    val_mask = labeled_df["well_id"].isin(val_wells)
    test_mask = labeled_df["well_id"].isin(test_wells)

    # Fit encoder strictly on TRAIN split to prevent categorical leakage
    encoder = OrdinalEncoder(
        handle_unknown="use_encoded_value",
        unknown_value=-1,
    )
    encoder.fit(labeled_df.loc[train_mask, CATEGORICAL_FEATURES].astype(str))

    # Save encoder artifact
    joblib.dump(encoder, MODELS_DIR / "nwis_categorical_encoder.joblib")

    # Transform categoricals into float arrays
    train_cat_enc = encoder.transform(labeled_df.loc[train_mask, CATEGORICAL_FEATURES].astype(str))
    val_cat_enc = encoder.transform(labeled_df.loc[val_mask, CATEGORICAL_FEATURES].astype(str))
    test_cat_enc = encoder.transform(labeled_df.loc[test_mask, CATEGORICAL_FEATURES].astype(str))

    # Construct numeric feature frames with strict train-only imputation
    non_cat_features = [c for c in ALL_FEATURE_COLUMNS if c not in CATEGORICAL_FEATURES]

    # Compute training medians strictly on train_mask to eliminate preprocessing leakage
    train_numeric_sub = labeled_df.loc[train_mask, non_cat_features].apply(pd.to_numeric, errors="coerce")
    train_medians = train_numeric_sub.median().fillna(0.0).to_dict()
    joblib.dump(train_medians, MODELS_DIR / "nwis_train_imputation_medians.joblib")

    def build_feature_split(mask: pd.Series, cat_array: np.ndarray) -> pd.DataFrame:
        sub_df = labeled_df.loc[mask, non_cat_features].copy()
        for col in non_cat_features:
            fill_v = float(train_medians.get(col, 0.0))
            sub_df[col] = pd.to_numeric(sub_df[col], errors="coerce").fillna(fill_v)
        cat_df = pd.DataFrame(cat_array, index=sub_df.index, columns=CATEGORICAL_FEATURES, dtype=float)
        full_df = pd.concat([sub_df, cat_df], axis=1)[ALL_FEATURE_COLUMNS]
        return full_df

    X_train = build_feature_split(train_mask, train_cat_enc)
    X_val = build_feature_split(val_mask, val_cat_enc)
    X_test = build_feature_split(test_mask, test_cat_enc)

    y_train = {h: labeled_df.loc[train_mask, f"target_{h}"].astype(int) for h in TARGET_HAZARDS}
    y_val = {h: labeled_df.loc[val_mask, f"target_{h}"].astype(int) for h in TARGET_HAZARDS}
    y_test = {h: labeled_df.loc[test_mask, f"target_{h}"].astype(int) for h in TARGET_HAZARDS}

    print(
        f"Prepared Splits: Train {X_train.shape[0]} rows | "
        f"Val {X_val.shape[0]} rows | Test {X_test.shape[0]} rows"
    )

    splits = DatasetSplits(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        X_test=X_test,
        y_test=y_test,
        train_wells=train_wells,
        val_wells=val_wells,
        test_wells=test_wells,
        encoder=encoder,
        feature_columns=ALL_FEATURE_COLUMNS,
    )

    return splits


if __name__ == "__main__":
    splits = build_and_split_dataset()
    print("Splits successfully constructed.")
    for h in TARGET_HAZARDS:
        print(f"Hazard: {h} | Train positives: {splits.y_train[h].sum()} | Test positives: {splits.y_test[h].sum()}")
