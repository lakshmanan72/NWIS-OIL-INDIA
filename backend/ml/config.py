"""
NWIS ML Configuration
=====================
Defines constants, paths, hazard mappings, feature sets, split ratios,
and metric configuration for the Phase 3 ML pipeline.
"""

from pathlib import Path
from typing import Dict, List

# Workspace Root & Data Paths
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = WORKSPACE_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
MODELS_DIR = WORKSPACE_ROOT / "models"
DOCS_DIR = WORKSPACE_ROOT / "docs"

# Ensure target directories exist
MODELS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Raw Datasets
DATASET_PATHS = {
    "daily_drilling": RAW_DATA_DIR / "nwis_daily_drilling_parameters_15108.csv",
    "mud_logging": RAW_DATA_DIR / "nwis_mud_logging_15108_wells.csv",
    "historical_events": RAW_DATA_DIR / "nwis_historical_drilling_events_15108.csv",
    "well_geology": RAW_DATA_DIR / "nwis_well_geology_15108.csv",
    "formation_lithology": RAW_DATA_DIR / "nwis_formation_lithology_15108.csv",
    "spatial_relationships": RAW_DATA_DIR / "nwis_spatial_well_relationships_15108.csv",
    "well_locations": RAW_DATA_DIR / "nwis_well_locations_15108_new.csv",
    "risk_recommendations": RAW_DATA_DIR / "nwis_risk_recommendations.csv",
}

# Artifact Outputs
COMPARISON_CSV_PATH = DATA_DIR / "ml_model_comparison.csv"
SELECTION_REPORT_PATH = DATA_DIR / "model_selection_report.json"
LEAKAGE_AUDIT_REPORT_PATH = DATA_DIR / "leakage_audit_report.json"
MODEL_CARD_PATH = DOCS_DIR / "model_card.md"

# Hazard Target Definitions
TARGET_HAZARDS: List[str] = [
    "mud_loss",
    "stuck_pipe",
    "kick",
    "overpressure",
    "torque_spike",
]

HAZARD_EVENT_MAPPING: Dict[str, List[str]] = {
    "mud_loss": ["Mud Loss", "Lost Circulation"],
    "stuck_pipe": ["Stuck Pipe", "Differential Sticking", "Pack-Off"],
    "kick": ["Kick"],
    "overpressure": ["Formation Pressure Change"],
    "torque_spike": ["Torque and Drag"],
}

# Configurable Lookahead Window
LOOKAHEAD_METERS: float = 100.0

# Grouped Split Ratios (by well_id)
TRAIN_RATIO: float = 0.70
VAL_RATIO: float = 0.15
TEST_RATIO: float = 0.15
RANDOM_SEED: int = 42

# Selection Criteria
PRIMARY_METRIC: str = "pr_auc"
SECONDARY_METRIC: str = "recall"

# Forbidden / Leakage Blacklist
LEAKAGE_BLACKLIST_COLUMNS: List[str] = [
    "risk_score",
    "risk_level",
    "predicted_event",
    "confidence",
    "recommended_action",
    "prediction_id",
    "similar_historical_wells",
    "supporting_event_id",
    "drilling_event",
    "kick_indicator",
    "loss_indicator",
    "overpressure_indicator",
    "mud_loss_severity",
    "event_id",
]

# Raw Continuous Drilling Features (at depth D)
DRILLING_NUMERIC_FEATURES: List[str] = [
    "depth_md",
    "depth_tvd",
    "rop_m_per_hr",
    "wob_klbf",
    "rpm",
    "torque_knm",
    "flow_rate_lpm",
    "pump_pressure_psi",
    "standpipe_pressure_psi",
    "mud_weight_ppg",
    "mud_viscosity_cp",
    "mud_loss_lph",
    "ecd_ppg",
    "hook_load_klbf",
]

# Rolling & Lag Features (strictly from observations <= D)
ROLLING_FEATURES: List[str] = [
    "rolling_mean_rop",
    "rolling_mean_torque",
    "rolling_max_torque",
    "rolling_mean_wob",
    "rolling_mean_spp",
    "rolling_mean_ecd",
    "torque_change",
    "rop_change",
    "pressure_change",
    "mud_loss_trend",
]

# Mud Logging Features (as of latest depth <= D)
MUD_NUMERIC_FEATURES: List[str] = [
    "mud_temperature_c",
    "mud_flow_rate_lpm",
    "pit_volume_bbl",
    "pit_gain_loss_bbl",
    "flow_out_pct",
    "gas_total_units",
    "methane_units",
    "ethane_units",
    "propane_units",
    "connection_gas_units",
    "trip_gas_units",
    "formation_pressure_estimate_psi",
]

# Geology & Subsurface Features (at depth D)
GEOLOGY_NUMERIC_FEATURES: List[str] = [
    "porosity_pct",
    "permeability_md",
    "pore_pressure_psi",
    "fracture_pressure_psi",
    "temperature_c",
    "pressure_margin",
    "depth_within_formation",
    "formation_thickness",
    "pore_pressure_gradient",
    "fracture_pressure_gradient",
]

# Offset Well Historical Evidence Features
OFFSET_NUMERIC_FEATURES: List[str] = [
    "nearby_well_count",
    "same_field_count",
    "same_block_count",
    "same_basin_count",
    "nearby_mud_loss_events",
    "nearby_stuck_pipe_events",
    "nearby_kick_events",
    "nearby_overpressure_events",
    "nearby_torque_events",
    "same_formation_mud_loss_events",
    "same_formation_stuck_pipe_events",
    "same_formation_kick_events",
    "same_formation_overpressure_events",
    "distance_to_nearest_hazard_well",
]

# Categorical Features
CATEGORICAL_FEATURES: List[str] = [
    "formation",
    "lithology",
    "basin",
    "field",
    "trajectory_type",
]

# Combined Final Feature Columns for Tabular Learning
ALL_FEATURE_COLUMNS: List[str] = (
    DRILLING_NUMERIC_FEATURES
    + ROLLING_FEATURES
    + MUD_NUMERIC_FEATURES
    + GEOLOGY_NUMERIC_FEATURES
    + OFFSET_NUMERIC_FEATURES
    + CATEGORICAL_FEATURES
)
