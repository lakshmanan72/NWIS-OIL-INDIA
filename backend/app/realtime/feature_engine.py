"""
NWIS Phase 6 — Streaming Feature Engine
=======================================
Computes real-time rolling statistical features over sliding telemetry windows:
- Rolling means, rolling maximums, rate of change (ROC)
- Flow in/out differentials and fluid imbalance percentages
- ROP variations and SPP pressure gradients
Enforces data quality tracking and skips features with missing source channels.
"""

from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Sequence

from .config import REALTIME_CONFIG
from .schema import RealtimeTelemetryRecord


class RealtimeFeatureEngine:
    """
    Streaming feature calculation engine for real-time drilling telemetry.
    """

    def __init__(self, default_window: int = 15):
        self.default_window = default_window
        self.min_samples = REALTIME_CONFIG["features"]["min_samples_for_baseline"]

    def compute_features(
        self,
        history: Sequence[RealtimeTelemetryRecord],
        current_record: Optional[RealtimeTelemetryRecord] = None,
    ) -> Dict[str, Any]:
        """
        Calculates streaming engineering features across the history window.
        Returns a dictionary mapping feature names to their values, window size,
        source fields, and quality metadata.
        """
        if not history and not current_record:
            return {}

        records = list(history)
        if current_record and (not records or records[-1] != current_record):
            records.append(current_record)

        window_records = records[-self.default_window:]
        n_samples = len(window_records)

        computed: Dict[str, Dict[str, Any]] = {}

        # -------------------------------------------------------------
        # Helper: Extract valid numeric series
        # -------------------------------------------------------------
        def _get_series(attr: str) -> List[float]:
            vals: List[float] = []
            for r in window_records:
                v = getattr(r, attr, None)
                if v is not None and not math.isnan(v):
                    vals.append(float(v))
            return vals

        # -------------------------------------------------------------
        # 1. Torque Features
        # -------------------------------------------------------------
        torque_series = _get_series("torque_kftlb")
        if len(torque_series) >= self.min_samples:
            t_mean = round(sum(torque_series) / len(torque_series), 2)
            t_max = round(max(torque_series), 2)
            t_variance = sum((x - t_mean) ** 2 for x in torque_series) / len(torque_series)
            t_std = round(math.sqrt(t_variance), 2)
            t_roc = round(torque_series[-1] - torque_series[0], 2)

            computed["torque_rolling_mean"] = {
                "value": t_mean,
                "window": len(torque_series),
                "unit": "kft-lb",
                "source_fields": ["torque_kftlb"],
                "data_quality": "RELIABLE" if len(torque_series) >= 5 else "INSUFFICIENT_HISTORY",
            }
            computed["torque_rolling_max"] = {
                "value": t_max,
                "window": len(torque_series),
                "unit": "kft-lb",
                "source_fields": ["torque_kftlb"],
                "data_quality": "RELIABLE",
            }
            computed["torque_std"] = {
                "value": t_std,
                "window": len(torque_series),
                "unit": "kft-lb",
                "source_fields": ["torque_kftlb"],
                "data_quality": "RELIABLE",
            }
            computed["torque_roc"] = {
                "value": t_roc,
                "window": len(torque_series),
                "unit": "kft-lb/window",
                "source_fields": ["torque_kftlb"],
                "data_quality": "RELIABLE",
            }

        # -------------------------------------------------------------
        # 2. ROP (Rate of Penetration) Features
        # -------------------------------------------------------------
        rop_series = _get_series("rop_m_hr")
        if len(rop_series) >= self.min_samples:
            rop_mean = round(sum(rop_series) / len(rop_series), 2)
            cur_rop = rop_series[-1]
            rop_roc = round(cur_rop - rop_series[0], 2)
            rop_pct_change = round(((cur_rop - rop_mean) / rop_mean) * 100.0, 1) if rop_mean > 0 else 0.0

            computed["rop_rolling_mean"] = {
                "value": rop_mean,
                "window": len(rop_series),
                "unit": "m/hr",
                "source_fields": ["rop_m_hr"],
                "data_quality": "RELIABLE",
            }
            computed["rop_pct_change_from_mean"] = {
                "value": rop_pct_change,
                "window": len(rop_series),
                "unit": "%",
                "source_fields": ["rop_m_hr"],
                "data_quality": "RELIABLE",
            }
            computed["rop_roc"] = {
                "value": rop_roc,
                "window": len(rop_series),
                "unit": "m/hr/window",
                "source_fields": ["rop_m_hr"],
                "data_quality": "RELIABLE",
            }

        # -------------------------------------------------------------
        # 3. SPP (Standpipe Pressure) Features
        # -------------------------------------------------------------
        spp_series = _get_series("standpipe_pressure_psi")
        if len(spp_series) >= self.min_samples:
            spp_mean = round(sum(spp_series) / len(spp_series), 1)
            cur_spp = spp_series[-1]
            spp_delta = round(cur_spp - spp_mean, 1)
            spp_roc = round(cur_spp - spp_series[0], 1)

            computed["spp_rolling_mean"] = {
                "value": spp_mean,
                "window": len(spp_series),
                "unit": "psi",
                "source_fields": ["standpipe_pressure_psi"],
                "data_quality": "RELIABLE",
            }
            computed["spp_delta_from_mean"] = {
                "value": spp_delta,
                "window": len(spp_series),
                "unit": "psi",
                "source_fields": ["standpipe_pressure_psi"],
                "data_quality": "RELIABLE",
            }
            computed["spp_roc"] = {
                "value": spp_roc,
                "window": len(spp_series),
                "unit": "psi/window",
                "source_fields": ["standpipe_pressure_psi"],
                "data_quality": "RELIABLE",
            }

        # -------------------------------------------------------------
        # 4. Flow In / Out Imbalance Features
        # -------------------------------------------------------------
        latest = window_records[-1]
        flow_in = latest.mud_flow_in_lpm or latest.flow_rate_lpm
        flow_out = latest.mud_flow_out_lpm
        if flow_in is not None and flow_out is not None and flow_in > 0:
            flow_diff = round(flow_in - flow_out, 1)
            flow_imbalance_pct = round(((flow_in - flow_out) / flow_in) * 100.0, 1)

            computed["flow_in_out_diff"] = {
                "value": flow_diff,
                "window": 1,
                "unit": "LPM",
                "source_fields": ["mud_flow_in_lpm", "mud_flow_out_lpm"],
                "data_quality": "RELIABLE",
            }
            computed["flow_imbalance_pct"] = {
                "value": flow_imbalance_pct,
                "window": 1,
                "unit": "%",
                "source_fields": ["mud_flow_in_lpm", "mud_flow_out_lpm"],
                "data_quality": "RELIABLE",
            }

        # -------------------------------------------------------------
        # 5. WOB & RPM Features
        # -------------------------------------------------------------
        wob_series = _get_series("wob_klbf")
        if len(wob_series) >= self.min_samples:
            w_mean = round(sum(wob_series) / len(wob_series), 2)
            computed["wob_rolling_mean"] = {
                "value": w_mean,
                "window": len(wob_series),
                "unit": "klbf",
                "source_fields": ["wob_klbf"],
                "data_quality": "RELIABLE",
            }

        rpm_series = _get_series("rpm")
        if len(rpm_series) >= self.min_samples:
            r_mean = round(sum(rpm_series) / len(rpm_series), 1)
            computed["rpm_rolling_mean"] = {
                "value": r_mean,
                "window": len(rpm_series),
                "unit": "RPM",
                "source_fields": ["rpm"],
                "data_quality": "RELIABLE",
            }

        # -------------------------------------------------------------
        # 6. Gas Units Trend
        # -------------------------------------------------------------
        gas_series = _get_series("gas_units")
        if len(gas_series) >= self.min_samples:
            gas_mean = round(sum(gas_series) / len(gas_series), 2)
            gas_roc = round(gas_series[-1] - gas_series[0], 2)
            computed["gas_rolling_mean"] = {
                "value": gas_mean,
                "window": len(gas_series),
                "unit": "units",
                "source_fields": ["gas_units"],
                "data_quality": "RELIABLE",
            }
            computed["gas_roc"] = {
                "value": gas_roc,
                "window": len(gas_series),
                "unit": "units/window",
                "source_fields": ["gas_units"],
                "data_quality": "RELIABLE",
            }

        return computed


# Global singleton streaming feature engine
realtime_feature_engine = RealtimeFeatureEngine()
