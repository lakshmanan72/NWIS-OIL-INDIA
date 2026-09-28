"""
NWIS Label Generation
=====================
Constructs future-looking binary hazard target labels from verified historical
drilling events for each depth observation:

Target Logic:
-------------
For an observation at depth D on well W:
Future Lookahead Window: [D, D + LOOKAHEAD_METERS]

Target definition for hazard H:
  Y_H = 1  if there exists an event E in historical_drilling_events such that:
           E.well_id == W AND
           E.event_type in HAZARD_EVENT_MAPPING[H] AND
           D <= E.depth_md <= D + LOOKAHEAD_METERS
  Y_H = 0  otherwise.

CRITICAL: Targets are constructed STRICTLY from nwis_historical_drilling_events_15108.csv.
The prototype nwis_risk_recommendations.csv is NEVER used as ground truth.
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

from .config import (
    DATASET_PATHS,
    HAZARD_EVENT_MAPPING,
    LOOKAHEAD_METERS,
    TARGET_HAZARDS,
)


def load_historical_events(
    events_path: Optional[str] = None,
) -> pd.DataFrame:
    """
    Loads historical drilling events and standardizes column types.
    """
    path = events_path or DATASET_PATHS["historical_events"]
    df = pd.read_csv(
        path,
        usecols=["event_id", "well_id", "depth_md", "event_type", "severity"],
    )
    df["depth_md"] = pd.to_numeric(df["depth_md"], errors="coerce")
    df = df.dropna(subset=["well_id", "depth_md", "event_type"])
    return df


def generate_hazard_targets(
    observations_df: pd.DataFrame,
    events_df: Optional[pd.DataFrame] = None,
    lookahead_meters: float = LOOKAHEAD_METERS,
    depth_col: str = "depth_md",
    well_col: str = "well_id",
) -> Tuple[pd.DataFrame, Dict[str, Dict[str, any]]]:
    """
    Generates binary target columns for each hazard in TARGET_HAZARDS.
    
    Parameters:
    -----------
    observations_df: DataFrame containing at least [well_col, depth_col]
    events_df: DataFrame containing historical drilling events (if None, loaded from disk)
    lookahead_meters: Future interval depth window (default 100m)
    depth_col: Column name representing current measured depth
    well_col: Column name representing well identifier

    Returns:
    --------
    Tuple of:
      - Augmented DataFrame with target_<hazard> columns (0 or 1)
      - Summary dictionary of class counts, ratios, and sufficiency status
    """
    if events_df is None:
        events_df = load_historical_events()

    out_df = observations_df.copy()
    summary = {}

    # Initialize all targets to 0
    for hazard in TARGET_HAZARDS:
        out_df[f"target_{hazard}"] = 0

    # Ensure depths are numeric
    out_df[depth_col] = pd.to_numeric(out_df[depth_col], errors="coerce")

    # Group events by hazard
    for hazard, valid_types in HAZARD_EVENT_MAPPING.items():
        sub_events = events_df[events_df["event_type"].isin(valid_types)].copy()
        target_col = f"target_{hazard}"

        if sub_events.empty:
            summary[hazard] = {
                "positive_count": 0,
                "negative_count": len(out_df),
                "positive_rate": 0.0,
                "sufficient_labels": False,
                "status": "Insufficient validated labels for this hazard.",
            }
            continue

        # Merge observations with events of this hazard on well_id
        merged = pd.merge(
            out_df[[well_col, depth_col]].reset_index(),
            sub_events[[well_col, "depth_md"]].rename(columns={"depth_md": "event_depth"}),
            on=well_col,
            how="inner",
        )

        # Vectorized check: D <= event_depth <= D + lookahead_meters
        in_window = (
            (merged["event_depth"] >= merged[depth_col]) &
            (merged["event_depth"] <= merged[depth_col] + lookahead_meters)
        )

        positive_indices = merged.loc[in_window, "index"].unique()
        out_df.loc[out_df.index.isin(positive_indices), target_col] = 1

        pos_count = int((out_df[target_col] == 1).sum())
        neg_count = int((out_df[target_col] == 0).sum())
        total = len(out_df)
        pos_rate = float(pos_count / total) if total > 0 else 0.0

        # Sufficiency threshold: at least 15 verified positive events across the dataset
        sufficient = pos_count >= 15

        summary[hazard] = {
            "positive_count": pos_count,
            "negative_count": neg_count,
            "positive_rate": round(pos_rate, 4),
            "sufficient_labels": sufficient,
            "lookahead_meters": lookahead_meters,
            "mapped_event_types": valid_types,
            "status": "OK" if sufficient else "Insufficient validated labels for this hazard.",
        }

    return out_df, summary


if __name__ == "__main__":
    from .config import DATASET_PATHS
    print("Testing label generation on daily drilling parameters...")
    daily = pd.read_csv(DATASET_PATHS["daily_drilling"])
    labeled_df, summ = generate_hazard_targets(daily)
    print("\n--- Label Generation Summary (100m lookahead) ---")
    for h, s in summ.items():
        print(f"{h:14s}: {s['positive_count']:4d} pos / {s['negative_count']:5d} neg ({s['positive_rate']*100:.2f}%) - {s['status']}")
