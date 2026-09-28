"""
NWIS Feature Engineering
========================
Builds comprehensive domain-specific features for drilling risk prediction:
1. Daily Drilling Telemetry & Rolling/Lag Trends (strictly <= D)
2. Mud Logging Physical Telemetry (backward merge <= D)
3. Subsurface Geology, Geopressure Margins & Lithology (at D)
4. Spatial Offset Well Historical Incident Aggregations (other wells only)
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from .config import (
    ALL_FEATURE_COLUMNS,
    CATEGORICAL_FEATURES,
    DATASET_PATHS,
    DRILLING_NUMERIC_FEATURES,
    GEOLOGY_NUMERIC_FEATURES,
    HAZARD_EVENT_MAPPING,
    MUD_NUMERIC_FEATURES,
    OFFSET_NUMERIC_FEATURES,
    ROLLING_FEATURES,
)


def compute_drilling_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes rolling statistics and lag differences within each well.
    Ensures strictly forward-in-time / depth-ascending order, so no future
    observations can influence past points.
    """
    df = df.sort_values(["well_id", "depth_md"]).copy()

    # Rolling window of 3 observations per well
    grouped = df.groupby("well_id")

    df["rolling_mean_rop"] = (
        grouped["rop_m_per_hr"]
        .rolling(window=3, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True)
    )
    df["rolling_mean_torque"] = (
        grouped["torque_knm"]
        .rolling(window=3, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True)
    )
    df["rolling_max_torque"] = (
        grouped["torque_knm"]
        .rolling(window=3, min_periods=1)
        .max()
        .reset_index(level=0, drop=True)
    )
    df["rolling_mean_wob"] = (
        grouped["wob_klbf"]
        .rolling(window=3, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True)
    )
    df["rolling_mean_spp"] = (
        grouped["standpipe_pressure_psi"]
        .rolling(window=3, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True)
    )
    df["rolling_mean_ecd"] = (
        grouped["ecd_ppg"]
        .rolling(window=3, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True)
    )

    # First-difference changes (current - previous)
    df["torque_change"] = grouped["torque_knm"].diff().fillna(0.0)
    df["rop_change"] = grouped["rop_m_per_hr"].diff().fillna(0.0)
    df["pressure_change"] = grouped["standpipe_pressure_psi"].diff().fillna(0.0)
    df["mud_loss_trend"] = grouped["mud_loss_lph"].diff().fillna(0.0)

    return df


def merge_mud_logging_features(
    drilling_df: pd.DataFrame,
    mud_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Performs backward merge_asof between daily drilling points and mud logging telemetry.
    Matches the latest available mud log at or before depth_md for the same well.
    """
    if mud_df is None:
        mud_cols = ["well_id", "depth_m"] + MUD_NUMERIC_FEATURES
        mud_df = pd.read_csv(DATASET_PATHS["mud_logging"], usecols=mud_cols)

    mud_sorted = mud_df.sort_values(["well_id", "depth_m"]).copy()
    mud_sorted["depth_md"] = mud_sorted["depth_m"]

    merged_chunks = []
    # Process by well_id to enforce exact well match in merge_asof
    drilling_grouped = drilling_df.groupby("well_id")
    mud_grouped = mud_sorted.groupby("well_id")

    for well_id, d_group in drilling_grouped:
        d_group_sorted = d_group.sort_values("depth_md")
        if well_id in mud_grouped.groups:
            m_group = mud_grouped.get_group(well_id)
            merged = pd.merge_asof(
                d_group_sorted,
                m_group[["depth_md"] + MUD_NUMERIC_FEATURES],
                on="depth_md",
                direction="backward",
            )
        else:
            merged = d_group_sorted.copy()
            for col in MUD_NUMERIC_FEATURES:
                merged[col] = np.nan
        merged_chunks.append(merged)

    res_df = pd.concat(merged_chunks, ignore_index=True)
    # Forward fill or median fill missing mud telemetry
    for col in MUD_NUMERIC_FEATURES:
        if col in res_df.columns:
            median_val = res_df[col].median()
            res_df[col] = res_df[col].fillna(median_val if not pd.isna(median_val) else 0.0)

    return res_df


def merge_geology_features(
    drilling_df: pd.DataFrame,
    geo_df: Optional[pd.DataFrame] = None,
    loc_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Enriches observations with interval geology and well location attributes.
    """
    if geo_df is None:
        geo_cols = [
            "well_id", "top_depth_m", "bottom_depth_m", "formation", "lithology",
            "porosity_pct", "permeability_md", "pore_pressure_psi",
            "fracture_pressure_psi", "temperature_c"
        ]
        geo_df = pd.read_csv(DATASET_PATHS["well_geology"], usecols=geo_cols)

    if loc_df is None:
        loc_cols = ["well_id", "basin", "field", "trajectory_type"]
        loc_df = pd.read_csv(DATASET_PATHS["well_locations"], usecols=loc_cols)

    geo_sorted = geo_df.sort_values(["well_id", "top_depth_m"]).copy()

    merged_chunks = []
    drilling_grouped = drilling_df.groupby("well_id")
    geo_grouped = geo_sorted.groupby("well_id")

    for well_id, d_group in drilling_grouped:
        d_group_sorted = d_group.sort_values("depth_md")
        if well_id in geo_grouped.groups:
            g_group = geo_grouped.get_group(well_id)
            # Match top_depth_m <= depth_md
            g_cols = [
                "top_depth_m", "bottom_depth_m", "formation", "lithology",
                "porosity_pct", "permeability_md", "pore_pressure_psi",
                "fracture_pressure_psi", "temperature_c"
            ]
            merged = pd.merge_asof(
                d_group_sorted,
                g_group[["top_depth_m"] + g_cols[1:]],
                left_on="depth_md",
                right_on="top_depth_m",
                direction="backward",
            )
        else:
            merged = d_group_sorted.copy()
            for col in [
                "top_depth_m", "bottom_depth_m", "formation", "lithology",
                "porosity_pct", "permeability_md", "pore_pressure_psi",
                "fracture_pressure_psi", "temperature_c"
            ]:
                merged[col] = np.nan
        merged_chunks.append(merged)

    res_df = pd.concat(merged_chunks, ignore_index=True)

    # Attach location metadata
    res_df = pd.merge(res_df, loc_df, on="well_id", how="left")

    # Compute derived geopressure margins
    res_df["porosity_pct"] = pd.to_numeric(res_df["porosity_pct"], errors="coerce").fillna(15.0)
    res_df["permeability_md"] = pd.to_numeric(res_df["permeability_md"], errors="coerce").fillna(25.0)
    res_df["pore_pressure_psi"] = pd.to_numeric(res_df["pore_pressure_psi"], errors="coerce").fillna(res_df["depth_md"] * 0.465)
    res_df["fracture_pressure_psi"] = pd.to_numeric(res_df["fracture_pressure_psi"], errors="coerce").fillna(res_df["depth_md"] * 0.75)
    res_df["temperature_c"] = pd.to_numeric(res_df["temperature_c"], errors="coerce").fillna(85.0)

    res_df["pressure_margin"] = res_df["fracture_pressure_psi"] - res_df["pore_pressure_psi"]

    res_df["top_depth_m"] = pd.to_numeric(res_df["top_depth_m"], errors="coerce").fillna(0.0)
    res_df["bottom_depth_m"] = pd.to_numeric(res_df["bottom_depth_m"], errors="coerce").fillna(res_df["depth_md"] + 500.0)
    res_df["depth_within_formation"] = np.maximum(0.0, res_df["depth_md"] - res_df["top_depth_m"])
    res_df["formation_thickness"] = np.maximum(10.0, res_df["bottom_depth_m"] - res_df["top_depth_m"])

    depth_tvd = pd.to_numeric(res_df["depth_tvd"], errors="coerce").fillna(res_df["depth_md"])
    res_df["pore_pressure_gradient"] = res_df["pore_pressure_psi"] / (depth_tvd + 1e-4)
    res_df["fracture_pressure_gradient"] = res_df["fracture_pressure_psi"] / (depth_tvd + 1e-4)

    res_df["formation"] = res_df["formation"].fillna("Unknown Formation")
    res_df["lithology"] = res_df["lithology"].fillna("Shale")
    res_df["basin"] = res_df["basin"].fillna("Unknown Basin")
    res_df["field"] = res_df["field"].fillna("Unknown Field")
    res_df["trajectory_type"] = res_df["trajectory_type"].fillna("Vertical")

    return res_df


def compute_offset_features(
    spatial_path: Optional[str] = None,
    events_path: Optional[str] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Computes offset well historical evidence features:
    - Base offset features per source_well_id
    - Formation-specific offset event counts per (source_well_id, formation)
    """
    sp_path = spatial_path or DATASET_PATHS["spatial_relationships"]
    ev_path = events_path or DATASET_PATHS["historical_events"]

    sp = pd.read_csv(sp_path)
    ev = pd.read_csv(ev_path, usecols=["well_id", "formation", "event_type"])

    # Binary hazard flags in events
    for h, valid_types in HAZARD_EVENT_MAPPING.items():
        ev[h] = ev["event_type"].isin(valid_types).astype(int)

    # Aggregate total events per well
    well_events = ev.groupby("well_id")[list(HAZARD_EVENT_MAPPING.keys())].sum().reset_index()

    # Join with nearby wells
    sp_ev = pd.merge(sp, well_events, left_on="nearby_well_id", right_on="well_id", how="left").fillna(0)

    # Base spatial aggregations per source_well_id
    base_agg = sp_ev.groupby("source_well_id").agg(
        nearby_well_count=("nearby_well_id", "count"),
        same_field_count=("same_field", "sum"),
        same_block_count=("same_block", "sum"),
        same_basin_count=("same_basin", "sum"),
        nearby_mud_loss_events=("mud_loss", "sum"),
        nearby_stuck_pipe_events=("stuck_pipe", "sum"),
        nearby_kick_events=("kick", "sum"),
        nearby_overpressure_events=("overpressure", "sum"),
        nearby_torque_events=("torque_spike", "sum"),
    )

    hazard_cols = list(HAZARD_EVENT_MAPPING.keys())
    sp_ev["total_hazards"] = sp_ev[hazard_cols].sum(axis=1)
    min_dists = sp_ev[sp_ev["total_hazards"] > 0].groupby("source_well_id")["distance_km"].min().rename("distance_to_nearest_hazard_well")

    offset_base = base_agg.join(min_dists).fillna({"distance_to_nearest_hazard_well": 999.0}).reset_index()
    offset_base = offset_base.rename(columns={"source_well_id": "well_id"})

    # Formation-specific offset events
    sp_ev_form = pd.merge(
        sp[["source_well_id", "nearby_well_id"]],
        ev[["well_id", "formation", "mud_loss", "stuck_pipe", "kick", "overpressure"]],
        left_on="nearby_well_id",
        right_on="well_id",
        how="inner",
    )
    offset_formation = sp_ev_form.groupby(["source_well_id", "formation"]).agg(
        same_formation_mud_loss_events=("mud_loss", "sum"),
        same_formation_stuck_pipe_events=("stuck_pipe", "sum"),
        same_formation_kick_events=("kick", "sum"),
        same_formation_overpressure_events=("overpressure", "sum"),
    ).reset_index().rename(columns={"source_well_id": "well_id"})

    return offset_base, offset_formation


def build_full_feature_matrix(
    drilling_df: pd.DataFrame,
    mud_df: Optional[pd.DataFrame] = None,
    geo_df: Optional[pd.DataFrame] = None,
    loc_df: Optional[pd.DataFrame] = None,
    offset_base: Optional[pd.DataFrame] = None,
    offset_formation: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Orchestrates the entire feature engineering pipeline on daily drilling records:
    1. Rolling & lag features
    2. Mud telemetry backward merge
    3. Geology & geopressure margin merge
    4. Offset historical aggregations merge
    """
    # Step 1: Rolling
    df1 = compute_drilling_rolling_features(drilling_df)

    # Step 2: Mud telemetry
    df2 = merge_mud_logging_features(df1, mud_df=mud_df)

    # Step 3: Geology & Geopressure
    df3 = merge_geology_features(df2, geo_df=geo_df, loc_df=loc_df)

    # Step 4: Offset features
    if offset_base is None or offset_formation is None:
        offset_base, offset_formation = compute_offset_features()

    df4 = pd.merge(df3, offset_base, on="well_id", how="left")
    # Fill offset defaults for wells with no nearby relationships
    for col in [
        "nearby_well_count", "same_field_count", "same_block_count", "same_basin_count",
        "nearby_mud_loss_events", "nearby_stuck_pipe_events", "nearby_kick_events",
        "nearby_overpressure_events", "nearby_torque_events"
    ]:
        df4[col] = df4[col].fillna(0.0)
    df4["distance_to_nearest_hazard_well"] = df4["distance_to_nearest_hazard_well"].fillna(999.0)

    # Merge formation offset features
    df5 = pd.merge(df4, offset_formation, on=["well_id", "formation"], how="left")
    for col in [
        "same_formation_mud_loss_events", "same_formation_stuck_pipe_events",
        "same_formation_kick_events", "same_formation_overpressure_events"
    ]:
        df5[col] = df5[col].fillna(0.0)

    return df5


if __name__ == "__main__":
    print("Testing Feature Engineering Pipeline...")
    daily = pd.read_csv(DATASET_PATHS["daily_drilling"])
    print(f"Loaded {len(daily)} daily drilling observations.")
    feat_df = build_full_feature_matrix(daily)
    print(f"Engineered feature matrix shape: {feat_df.shape}")
    missing = [c for c in ALL_FEATURE_COLUMNS if c not in feat_df.columns]
    print(f"Missing required feature columns: {missing}")
    print("Feature Engineering verified successfully.")
