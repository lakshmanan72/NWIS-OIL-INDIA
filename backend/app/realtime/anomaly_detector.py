"""
NWIS Phase 6 — Streaming Anomaly Detector
=========================================
Deterministic physical rule-based anomaly detection engine:
- Torque spike observations
- Standpipe pressure (SPP) surges or drops
- Flow-in / Flow-out fluid imbalances (seepage vs. influx)
- ROP sudden rate transitions (drilling break / deceleration)
Explicitly designated as observational telemetry evidence, NOT diagnoses.
"""

from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .config import REALTIME_CONFIG
from .schema import RealtimeTelemetryRecord


@dataclass
class StreamingAnomaly:
    anomaly_id: str
    anomaly_type: str
    severity: str  # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    depth_md: float
    observed_value: float
    baseline_value: float
    delta: float
    unit: str
    timestamp: str
    evidence: str = "streaming_telemetry"
    status: str = "DETECTED"
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class StreamingAnomalyDetector:
    """
    Deterministic rule-based anomaly detector operating on real-time features.
    """

    def __init__(self):
        self.anomaly_counter = 0

    def detect_anomalies(
        self,
        current_record: RealtimeTelemetryRecord,
        computed_features: Dict[str, Any],
    ) -> List[StreamingAnomaly]:
        """
        Evaluates current record against streaming rolling features.
        Returns a list of detected observational anomalies.
        """
        anomalies: List[StreamingAnomaly] = []
        now_iso = current_record.timestamp or datetime.now(timezone.utc).isoformat()
        depth = current_record.depth_md

        # -------------------------------------------------------------
        # 1. Torque Spike Anomaly
        # -------------------------------------------------------------
        if REALTIME_CONFIG["anomalies"]["torque"]["enabled"]:
            cur_torque = current_record.torque_kftlb
            t_mean_info = computed_features.get("torque_rolling_mean")
            t_std_info = computed_features.get("torque_std")

            if cur_torque is not None:
                t_mean = t_mean_info["value"] if t_mean_info else 15.0
                t_std = t_std_info["value"] if t_std_info else 1.0
                sigma_thresh = REALTIME_CONFIG["anomalies"]["torque"]["sigma_threshold"]
                min_delta = REALTIME_CONFIG["anomalies"]["torque"]["min_delta_kftlb"]

                delta = cur_torque - t_mean
                # Anomaly condition: delta exceeds minimum threshold OR absolute torque exceeds 22 kft-lb
                if (delta >= min_delta and delta >= (sigma_thresh * max(0.8, t_std))) or cur_torque >= 22.0:
                    self.anomaly_counter += 1
                    severity = "HIGH" if (delta >= min_delta * 1.5 or cur_torque >= 24.0) else "MEDIUM"
                    anomalies.append(
                        StreamingAnomaly(
                            anomaly_id=f"ANOM-TRQ-{self.anomaly_counter:04d}",
                            anomaly_type="torque_spike",
                            severity=severity,
                            depth_md=depth,
                            observed_value=round(cur_torque, 2),
                            baseline_value=round(t_mean, 2),
                            delta=round(delta, 2),
                            unit="kft-lb",
                            timestamp=now_iso,
                            description=f"Observed torque ({cur_torque:.1f} kft-lb) elevated by {delta:+.1f} kft-lb above rolling baseline ({t_mean:.1f} kft-lb).",
                        )
                    )

        # -------------------------------------------------------------
        # 2. Standpipe Pressure (SPP) Anomaly
        # -------------------------------------------------------------
        if REALTIME_CONFIG["anomalies"]["standpipe_pressure"]["enabled"]:
            cur_spp = current_record.standpipe_pressure_psi
            spp_mean_info = computed_features.get("spp_rolling_mean")

            if cur_spp is not None:
                spp_mean = spp_mean_info["value"] if spp_mean_info else 1850.0
                delta_psi = cur_spp - spp_mean
                psi_thresh = REALTIME_CONFIG["anomalies"]["standpipe_pressure"]["delta_psi_threshold"]

                if abs(delta_psi) >= psi_thresh:
                    self.anomaly_counter += 1
                    anom_kind = "pressure_surge" if delta_psi > 0 else "pressure_loss"
                    severity = "HIGH" if abs(delta_psi) >= psi_thresh * 1.5 else "MEDIUM"
                    anomalies.append(
                        StreamingAnomaly(
                            anomaly_id=f"ANOM-SPP-{self.anomaly_counter:04d}",
                            anomaly_type=anom_kind,
                            severity=severity,
                            depth_md=depth,
                            observed_value=round(cur_spp, 1),
                            baseline_value=round(spp_mean, 1),
                            delta=round(delta_psi, 1),
                            unit="psi",
                            timestamp=now_iso,
                            description=f"Standpipe pressure ({cur_spp:.0f} psi) deviated by {delta_psi:+.0f} psi from rolling mean ({spp_mean:.0f} psi).",
                        )
                    )

        # -------------------------------------------------------------
        # 3. Flow In / Out Imbalance Anomaly
        # -------------------------------------------------------------
        if REALTIME_CONFIG["anomalies"]["flow_imbalance"]["enabled"]:
            flow_in = current_record.mud_flow_in_lpm or current_record.flow_rate_lpm
            flow_out = current_record.mud_flow_out_lpm
            if flow_in is not None and flow_out is not None and flow_in > 0:
                diff_lpm = round(flow_in - flow_out, 1)
                imb_pct = round((diff_lpm / flow_in) * 100.0, 1)
                tol_pct = REALTIME_CONFIG["anomalies"]["flow_imbalance"]["tolerance_pct"]

                if abs(imb_pct) >= tol_pct:
                    self.anomaly_counter += 1
                    anom_kind = "mud_loss_imbalance" if diff_lpm > 0 else "flow_gain_influx"
                    severity = "HIGH" if abs(imb_pct) >= tol_pct * 1.5 else "MEDIUM"
                    anomalies.append(
                        StreamingAnomaly(
                            anomaly_id=f"ANOM-FLW-{self.anomaly_counter:04d}",
                            anomaly_type=anom_kind,
                            severity=severity,
                            depth_md=depth,
                            observed_value=round(flow_out, 1),
                            baseline_value=round(flow_in, 1),
                            delta=round(diff_lpm, 1),
                            unit="LPM",
                            timestamp=now_iso,
                            description=f"Flow imbalance detected ({imb_pct:+.1f}%); Flow-in vs Flow-out delta is {diff_lpm:+.0f} LPM.",
                        )
                    )

        # -------------------------------------------------------------
        # 4. ROP Anomaly
        # -------------------------------------------------------------
        if REALTIME_CONFIG["anomalies"]["rop"]["enabled"]:
            cur_rop = current_record.rop_m_hr
            rop_mean_info = computed_features.get("rop_rolling_mean")

            if cur_rop is not None and rop_mean_info:
                rop_mean = rop_mean_info["value"]
                drop_pct = REALTIME_CONFIG["anomalies"]["rop"]["sudden_drop_pct"]
                surge_pct = REALTIME_CONFIG["anomalies"]["rop"]["sudden_surge_pct"]

                if rop_mean > 2.0:
                    pct_diff = ((cur_rop - rop_mean) / rop_mean) * 100.0
                    if pct_diff <= -drop_pct:
                        self.anomaly_counter += 1
                        anomalies.append(
                            StreamingAnomaly(
                                anomaly_id=f"ANOM-ROP-{self.anomaly_counter:04d}",
                                anomaly_type="rop_sudden_drop",
                                severity="LOW",
                                depth_md=depth,
                                observed_value=round(cur_rop, 1),
                                baseline_value=round(rop_mean, 1),
                                delta=round(cur_rop - rop_mean, 1),
                                unit="m/hr",
                                timestamp=now_iso,
                                description=f"ROP decreased sharply by {pct_diff:.1f}% below rolling average ({rop_mean:.1f} m/hr).",
                            )
                        )
                    elif pct_diff >= surge_pct:
                        self.anomaly_counter += 1
                        anomalies.append(
                            StreamingAnomaly(
                                anomaly_id=f"ANOM-ROP-{self.anomaly_counter:04d}",
                                anomaly_type="rop_drilling_break",
                                severity="LOW",
                                depth_md=depth,
                                observed_value=round(cur_rop, 1),
                                baseline_value=round(rop_mean, 1),
                                delta=round(cur_rop - rop_mean, 1),
                                unit="m/hr",
                                timestamp=now_iso,
                                description=f"Drilling break observed: ROP increased by {pct_diff:+.1f}% above rolling average.",
                            )
                        )

        return anomalies


# Global singleton streaming anomaly detector
streaming_anomaly_detector = StreamingAnomalyDetector()
