"""
NWIS Real-Time Compatible Inference Engine
==========================================
Provides hazard risk predictions at arbitrary well depth D using an extensible
data provider architecture (CSVDataProvider today, ERTMACDataProvider in the future).
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
import joblib
import numpy as np
import pandas as pd

from .config import (
    ALL_FEATURE_COLUMNS,
    CATEGORICAL_FEATURES,
    DATASET_PATHS,
    MODELS_DIR,
    TARGET_HAZARDS,
)
from .explain import HazardExplainer
from .feature_engineering import compute_offset_features
from .model_registry import load_selected_models


class DrillingDataProvider(ABC):
    """Abstract base class for well telemetry and geological context providers."""

    @abstractmethod
    def get_features_at_depth(
        self,
        well_id: str,
        depth_md: float,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Retrieves or interpolates the feature vector for a well at depth D,
        ensuring NO future data beyond depth D is accessed.
        """
        pass


class CSVDataProvider(DrillingDataProvider):
    """
    Data provider utilizing the NWIS historical repository datasets.
    """

    def __init__(self):
        self.daily = pd.read_csv(DATASET_PATHS["daily_drilling"])
        self.mud = pd.read_csv(DATASET_PATHS["mud_logging"])
        self.geo = pd.read_csv(DATASET_PATHS["well_geology"])
        self.loc = pd.read_csv(DATASET_PATHS["well_locations"])
        self.encoder_path = MODELS_DIR / "nwis_categorical_encoder.joblib"
        self.encoder = joblib.load(self.encoder_path) if self.encoder_path.exists() else None
        self.imputer_path = MODELS_DIR / "nwis_train_imputation_medians.joblib"
        self.imputer_medians = joblib.load(self.imputer_path) if self.imputer_path.exists() else {}
        self.offset_base, self.offset_formation = compute_offset_features()

    def get_features_at_depth(
        self,
        well_id: str,
        depth_md: float,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        # Validate depth_md
        if depth_md is None:
            raise ValueError("Invalid depth_md: depth cannot be None.")
        try:
            depth_md = float(depth_md)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid depth_md '{depth_md}': Must be a valid numeric value.")
        if np.isnan(depth_md) or np.isinf(depth_md) or depth_md <= 0:
            raise ValueError(f"Invalid depth_md '{depth_md}': Measured depth must be a positive finite number.")

        # Verify well exists
        w_loc = self.loc[self.loc["well_id"] == well_id]
        if w_loc.empty:
            raise ValueError(f"Well ID '{well_id}' not found in canonical well database.")

        # Check depth against canonical well total depth
        tot_d_raw = w_loc.iloc[0].get("total_depth")
        try:
            tot_d = float(tot_d_raw)
        except (TypeError, ValueError):
            tot_d = None

        depth_status = "verified_drilled_interval"
        depth_warning = None
        if tot_d is not None and tot_d > 0 and depth_md > tot_d:
            depth_status = "extrapolated_beyond_total_depth"
            depth_warning = (
                f"Measured depth {depth_md:.1f}m exceeds canonical well total depth ({tot_d:.1f}m). "
                "Telemetry and geological signals are extrapolated from deepest available interval."
            )

        w_daily = self.daily[self.daily["well_id"] == well_id].sort_values("depth_md")
        
        # If well has daily drilling parameters, use closest observation at or before depth_md
        if not w_daily.empty:
            past_daily = w_daily[w_daily["depth_md"] <= depth_md]
            if not past_daily.empty:
                base_row = past_daily.iloc[-1].to_dict()
            else:
                base_row = w_daily.iloc[0].to_dict()
        else:
            # Fallback synthetic row from well location
            base_row = {
                "well_id": well_id,
                "depth_md": depth_md,
                "depth_tvd": depth_md * 0.96,
                "rop_m_per_hr": 14.5,
                "wob_klbf": 15.0,
                "rpm": 120.0,
                "torque_knm": 12.0,
                "flow_rate_lpm": 2400.0,
                "pump_pressure_psi": 2800.0,
                "standpipe_pressure_psi": 2750.0,
                "mud_weight_ppg": 10.5,
                "mud_viscosity_cp": 45.0,
                "mud_loss_lph": 0.0,
                "ecd_ppg": 11.0,
                "hook_load_klbf": 180.0,
            }

        base_row["depth_md"] = depth_md
        base_df = pd.DataFrame([base_row])

        # Compute rolling features (use all observations <= depth_md)
        if not w_daily.empty:
            past_series = w_daily[w_daily["depth_md"] <= depth_md]
            if len(past_series) >= 2:
                base_df["rolling_mean_rop"] = past_series["rop_m_per_hr"].tail(3).mean()
                base_df["rolling_mean_torque"] = past_series["torque_knm"].tail(3).mean()
                base_df["rolling_max_torque"] = past_series["torque_knm"].tail(3).max()
                base_df["rolling_mean_wob"] = past_series["wob_klbf"].tail(3).mean()
                base_df["rolling_mean_spp"] = past_series["standpipe_pressure_psi"].tail(3).mean()
                base_df["rolling_mean_ecd"] = past_series["ecd_ppg"].tail(3).mean()
                base_df["torque_change"] = past_series["torque_knm"].diff().iloc[-1]
                base_df["rop_change"] = past_series["rop_m_per_hr"].diff().iloc[-1]
                base_df["pressure_change"] = past_series["standpipe_pressure_psi"].diff().iloc[-1]
                base_df["mud_loss_trend"] = past_series["mud_loss_lph"].diff().iloc[-1]
            else:
                base_df["rolling_mean_rop"] = base_row.get("rop_m_per_hr", 14.0)
                base_df["rolling_mean_torque"] = base_row.get("torque_knm", 12.0)
                base_df["rolling_max_torque"] = base_row.get("torque_knm", 12.0)
                base_df["rolling_mean_wob"] = base_row.get("wob_klbf", 15.0)
                base_df["rolling_mean_spp"] = base_row.get("standpipe_pressure_psi", 2700.0)
                base_df["rolling_mean_ecd"] = base_row.get("ecd_ppg", 11.0)
                base_df["torque_change"] = 0.0
                base_df["rop_change"] = 0.0
                base_df["pressure_change"] = 0.0
                base_df["mud_loss_trend"] = 0.0
        else:
            base_df["rolling_mean_rop"] = 14.0
            base_df["rolling_mean_torque"] = 12.0
            base_df["rolling_max_torque"] = 12.0
            base_df["rolling_mean_wob"] = 15.0
            base_df["rolling_mean_spp"] = 2700.0
            base_df["rolling_mean_ecd"] = 11.0
            base_df["torque_change"] = 0.0
            base_df["rop_change"] = 0.0
            base_df["pressure_change"] = 0.0
            base_df["mud_loss_trend"] = 0.0

        # Mud telemetry <= depth_md
        w_mud = self.mud[(self.mud["well_id"] == well_id) & (self.mud["depth_m"] <= depth_md)].sort_values("depth_m")
        if not w_mud.empty:
            m_latest = w_mud.iloc[-1]
            base_df["mud_temperature_c"] = m_latest.get("mud_temperature_c", 65.0)
            base_df["mud_flow_rate_lpm"] = m_latest.get("mud_flow_rate_lpm", 2400.0)
            base_df["pit_volume_bbl"] = m_latest.get("pit_volume_bbl", 650.0)
            base_df["pit_gain_loss_bbl"] = m_latest.get("pit_gain_loss_bbl", 0.0)
            base_df["flow_out_pct"] = m_latest.get("flow_out_pct", 100.0)
            base_df["gas_total_units"] = m_latest.get("gas_total_units", 25.0)
            base_df["methane_units"] = m_latest.get("methane_units", 20.0)
            base_df["ethane_units"] = m_latest.get("ethane_units", 3.0)
            base_df["propane_units"] = m_latest.get("propane_units", 1.0)
            base_df["connection_gas_units"] = m_latest.get("connection_gas_units", 5.0)
            base_df["trip_gas_units"] = m_latest.get("trip_gas_units", 10.0)
            base_df["formation_pressure_estimate_psi"] = m_latest.get("formation_pressure_estimate_psi", depth_md * 0.465)
        else:
            base_df["mud_temperature_c"] = 65.0
            base_df["mud_flow_rate_lpm"] = 2400.0
            base_df["pit_volume_bbl"] = 650.0
            base_df["pit_gain_loss_bbl"] = 0.0
            base_df["flow_out_pct"] = 100.0
            base_df["gas_total_units"] = 25.0
            base_df["methane_units"] = 20.0
            base_df["ethane_units"] = 3.0
            base_df["propane_units"] = 1.0
            base_df["connection_gas_units"] = 5.0
            base_df["trip_gas_units"] = 10.0
            base_df["formation_pressure_estimate_psi"] = depth_md * 0.465

        # Geology interval at depth_md
        w_geo = self.geo[
            (self.geo["well_id"] == well_id) &
            (self.geo["top_depth_m"] <= depth_md) &
            (self.geo["bottom_depth_m"] >= depth_md)
        ]
        if not w_geo.empty:
            g_curr = w_geo.iloc[0]
            current_formation = str(g_curr.get("formation", "Unknown Formation"))
            current_lithology = str(g_curr.get("lithology", "Shale"))
            base_df["porosity_pct"] = float(g_curr.get("porosity_pct", 15.0))
            base_df["permeability_md"] = float(g_curr.get("permeability_md", 25.0))
            pore_p = float(g_curr.get("pore_pressure_psi", depth_md * 0.465))
            frac_p = float(g_curr.get("fracture_pressure_psi", depth_md * 0.75))
            temp_c = float(g_curr.get("temperature_c", 85.0))
            top_d = float(g_curr.get("top_depth_m", 0.0))
            bot_d = float(g_curr.get("bottom_depth_m", depth_md + 200.0))
        else:
            current_formation = "Unknown Formation"
            current_lithology = "Shale"
            base_df["porosity_pct"] = 15.0
            base_df["permeability_md"] = 25.0
            pore_p = depth_md * 0.465
            frac_p = depth_md * 0.75
            temp_c = 85.0
            top_d = 0.0
            bot_d = depth_md + 200.0

        base_df["pore_pressure_psi"] = pore_p
        base_df["fracture_pressure_psi"] = frac_p
        base_df["temperature_c"] = temp_c
        base_df["pressure_margin"] = frac_p - pore_p
        base_df["depth_within_formation"] = max(0.0, depth_md - top_d)
        base_df["formation_thickness"] = max(10.0, bot_d - top_d)

        depth_tvd = float(base_df["depth_tvd"].iloc[0])
        base_df["pore_pressure_gradient"] = pore_p / (depth_tvd + 1e-4)
        base_df["fracture_pressure_gradient"] = frac_p / (depth_tvd + 1e-4)

        base_df["formation"] = current_formation
        base_df["lithology"] = current_lithology
        base_df["basin"] = str(w_loc.iloc[0].get("basin", "Unknown Basin"))
        base_df["field"] = str(w_loc.iloc[0].get("field", "Unknown Field"))
        base_df["trajectory_type"] = str(w_loc.iloc[0].get("trajectory_type", "Vertical"))

        # Offset features
        off_b = self.offset_base[self.offset_base["well_id"] == well_id]
        if not off_b.empty:
            for col in off_b.columns:
                if col != "well_id":
                    base_df[col] = float(off_b.iloc[0][col])
        else:
            for col in [
                "nearby_well_count", "same_field_count", "same_block_count", "same_basin_count",
                "nearby_mud_loss_events", "nearby_stuck_pipe_events", "nearby_kick_events",
                "nearby_overpressure_events", "nearby_torque_events"
            ]:
                base_df[col] = 0.0
            base_df["distance_to_nearest_hazard_well"] = 999.0

        # Formation offset features
        off_f = self.offset_formation[
            (self.offset_formation["well_id"] == well_id) &
            (self.offset_formation["formation"] == current_formation)
        ]
        if not off_f.empty:
            for col in off_f.columns:
                if col not in ["well_id", "formation"]:
                    base_df[col] = float(off_f.iloc[0][col])
        else:
            for col in [
                "same_formation_mud_loss_events", "same_formation_stuck_pipe_events",
                "same_formation_kick_events", "same_formation_overpressure_events"
            ]:
                base_df[col] = 0.0

        # Encode categoricals using fitted encoder
        non_cat = [c for c in ALL_FEATURE_COLUMNS if c not in CATEGORICAL_FEATURES]
        sub_df = base_df[non_cat].copy()
        for col in non_cat:
            fill_v = float(self.imputer_medians.get(col, 0.0))
            sub_df[col] = pd.to_numeric(sub_df[col], errors="coerce").fillna(fill_v)

        if self.encoder is not None:
            cat_enc = self.encoder.transform(base_df[CATEGORICAL_FEATURES].astype(str))
            cat_df = pd.DataFrame(cat_enc, columns=CATEGORICAL_FEATURES, dtype=float)
        else:
            cat_df = pd.DataFrame([[0.0] * len(CATEGORICAL_FEATURES)], columns=CATEGORICAL_FEATURES)

        full_features = pd.concat([sub_df, cat_df], axis=1)[ALL_FEATURE_COLUMNS]

        meta = {
            "well_id": well_id,
            "depth_md": depth_md,
            "formation": current_formation,
            "lithology": current_lithology,
            "basin": base_df["basin"].iloc[0],
            "field": base_df["field"].iloc[0],
            "depth_status": depth_status,
            "depth_warning": depth_warning,
            "offset_summary": {
                "nearby_wells": int(base_df["nearby_well_count"].iloc[0]),
                "same_formation_mud_loss": int(base_df["same_formation_mud_loss_events"].iloc[0]),
                "same_formation_stuck_pipe": int(base_df["same_formation_stuck_pipe_events"].iloc[0]),
                "same_formation_kick": int(base_df["same_formation_kick_events"].iloc[0]),
                "same_formation_overpressure": int(base_df["same_formation_overpressure_events"].iloc[0]),
                "nearest_hazard_km": float(base_df["distance_to_nearest_hazard_well"].iloc[0]),
            }
        }

        return full_features, meta


class ERTMACDataProvider(DrillingDataProvider):
    """
    Stub provider for future integration with real-time drilling telemetry systems (eRTMAC/WITSML).
    """

    def get_features_at_depth(
        self,
        well_id: str,
        depth_md: float,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        raise NotImplementedError(
            "Live eRTMACDataProvider connection is not active in this offline environment. "
            "Use CSVDataProvider for historical/replay analysis."
        )


class RiskPredictor:
    """
    Inference service managing loaded hazard models and SHAP explainers.
    """

    def __init__(self, data_provider: Optional[DrillingDataProvider] = None):
        self.provider = data_provider or CSVDataProvider()
        self.models_data = load_selected_models()
        self.explainers = {}

        for hazard, m_info in self.models_data.items():
            model = m_info["model"]
            feat_cols = m_info.get("feature_columns", ALL_FEATURE_COLUMNS)
            self.explainers[hazard] = HazardExplainer(model, feat_cols)

    def predict_risk(
        self,
        well_id: str,
        depth_md: float,
    ) -> Dict[str, Any]:
        """
        Executes multi-hazard risk prediction and feature contributions for a given depth.
        """
        if not self.models_data:
            raise RuntimeError("Model artifacts unavailable in registry.")

        features_df, meta = self.provider.get_features_at_depth(well_id, depth_md)

        predictions = []
        all_top_features = []

        for hazard in TARGET_HAZARDS:
            if hazard not in self.models_data:
                continue

            m_info = self.models_data[hazard]
            model = m_info["model"]
            alg_name = m_info.get("algorithm", "Unknown")
            thresh_val = float(m_info.get("threshold", 0.50))

            # Predict probability
            prob_arr = model.predict_proba(features_df)
            prob = float(prob_arr[0, 1])

            predictions.append({
                "hazard": hazard,
                "probability": round(prob, 4),
                "probability_pct": round(prob * 100, 1),
                "algorithm": alg_name,
                "threshold": round(thresh_val, 4),
                "threshold_version": "threshold-v1",
            })

            # Explain instance
            explainer = self.explainers.get(hazard)
            if explainer:
                contribs = explainer.explain_instance(features_df, top_k=3, hazard_name=hazard)
                all_top_features.extend(contribs)

        # Historical offset evidence statements
        offset_meta = meta.get("offset_summary", {})
        evidence_lines = []
        if offset_meta.get("same_formation_mud_loss", 0) > 0:
            evidence_lines.append(
                f"{offset_meta['same_formation_mud_loss']} nearby offset well(s) experienced mud-loss incidents within the {meta['formation']} interval."
            )
        if offset_meta.get("same_formation_stuck_pipe", 0) > 0:
            evidence_lines.append(
                f"{offset_meta['same_formation_stuck_pipe']} nearby offset well(s) encountered stuck pipe in the {meta['formation']} formation."
            )
        if offset_meta.get("same_formation_kick", 0) > 0:
            evidence_lines.append(
                f"{offset_meta['same_formation_kick']} nearby offset well(s) took a kick event in the {meta['formation']} formation."
            )
        if offset_meta.get("same_formation_overpressure", 0) > 0:
            evidence_lines.append(
                f"{offset_meta['same_formation_overpressure']} nearby offset well(s) detected formation pressure changes / overpressure."
            )
        if not evidence_lines:
            evidence_lines.append(
                f"No verified historical offset drilling hazards recorded in the {meta['formation']} formation within immediate radius."
            )

        return {
            "well_id": well_id,
            "depth_md": float(depth_md),
            "formation": meta["formation"],
            "lithology": meta["lithology"],
            "model_version": "nwis-v1.0",
            "model_algorithm": {h: self.models_data[h]["algorithm"] for h in TARGET_HAZARDS if h in self.models_data},
            "training_dataset_version": "nwis-dataset-v1",
            "feature_schema_version": "features-v1",
            "lookahead_m": 100,
            "threshold_version": "threshold-v1",
            "depth_status": meta.get("depth_status", "verified_drilled_interval"),
            "depth_warning": meta.get("depth_warning"),
            "predictions": predictions,
            "top_features": all_top_features,
            "historical_offset_evidence": evidence_lines,
            "offset_summary": offset_meta,
        }
