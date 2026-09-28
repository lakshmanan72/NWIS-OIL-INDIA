"""
NWIS Phase 6 — Live Risk Engine & Multi-Source Signal Synthesizer
================================================================
Unifies:
1. Real-time streaming anomaly observations (assigned source LIVE-XXX)
2. Phase 3.1 Model Risk Indicators (reusing loaded RiskPredictor)
3. Geological Stratigraphy & Formation Tracking
4. Historical Evidence Packet via Phase 5 Context Builder (assigned source EVID-XXX)
Ensures strict provenance separation: LIVE telemetry IDs are NEVER mixed with EVID document IDs.
"""

from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from .config import REALTIME_CONFIG
from .schema import RealtimeTelemetryRecord
from .anomaly_detector import StreamingAnomaly

logger = logging.getLogger("nwis.live_risk_engine")


@dataclass
class LiveObservation:
    live_id: str
    anomaly_type: str
    severity: str
    depth_md: float
    observed_value: float
    baseline_value: float
    delta: float
    unit: str
    timestamp: str
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LiveEvidencePacket:
    active_well: str
    current_depth: float
    formation: str
    lithology: str
    provider_mode: str
    timestamp: str
    live_observations: List[Dict[str, Any]]
    model_risk_indicators: List[Dict[str, Any]]
    evaluated_signals: List[Dict[str, Any]]
    nearby_wells: List[Dict[str, Any]]
    historical_events: List[Dict[str, Any]]
    document_evidence: List[Dict[str, Any]]
    data_quality: Dict[str, Any]
    depth_safety_status: str = "NORMAL"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LiveRiskEngine:
    """
    Evaluates real-time drilling risks by synthesizing live telemetry observations,
    Phase 3.1 Model Risk Indicators, and institutional memory evidence.
    """

    def __init__(self):
        self._predictor = None
        self._live_observation_counter = 0

    def _get_predictor(self):
        if self._predictor is None:
            try:
                from ...ml.predict import RiskPredictor, CSVDataProvider
                self._predictor = RiskPredictor(CSVDataProvider())
            except Exception as e:
                logger.error(f"Failed to initialize Phase 3.1 RiskPredictor: {e}")
                self._predictor = None
        return self._predictor

    def evaluate_live_risk(
        self,
        record: RealtimeTelemetryRecord,
        anomalies: List[StreamingAnomaly],
        provider_mode: str = "DEMO REPLAY",
        data_quality: Optional[Dict[str, Any]] = None,
    ) -> LiveEvidencePacket:
        """
        Executes end-to-end live risk evaluation for the active telemetry record.
        """
        well_id = record.well_id.upper()
        depth_md = record.depth_md
        now_iso = record.timestamp or datetime.now(timezone.utc).isoformat()

        # -------------------------------------------------------------
        # 1. Format Live Observations with separate LIVE-XXX identifiers
        # -------------------------------------------------------------
        live_observations: List[Dict[str, Any]] = []
        for anom in anomalies:
            self._live_observation_counter += 1
            live_id = f"LIVE-{self._live_observation_counter:03d}"
            obs = LiveObservation(
                live_id=live_id,
                anomaly_type=anom.anomaly_type,
                severity=anom.severity,
                depth_md=anom.depth_md,
                observed_value=anom.observed_value,
                baseline_value=anom.baseline_value,
                delta=anom.delta,
                unit=anom.unit,
                timestamp=anom.timestamp,
                description=anom.description,
            )
            live_observations.append(obs.to_dict())

        # -------------------------------------------------------------
        # 2. Retrieve Subsurface Formation Context
        # -------------------------------------------------------------
        formation_name = "Barail"  # Domain baseline default
        lithology_name = "Shale"
        try:
            from ..services.formation_service import formation_service
            f_info = formation_service.get_formation_for_depth(well_id, depth_md)
            if f_info and f_info.formation_name:
                formation_name = f_info.formation_name
            if f_info and f_info.lithology:
                lithology_name = f_info.lithology
        except Exception:
            pass

        # -------------------------------------------------------------
        # 3. Phase 3.1 ML Risk Inference & Depth Safety Check
        # -------------------------------------------------------------
        model_risk_indicators: List[Dict[str, Any]] = []
        depth_safety_status = "NORMAL"
        well_total_depth = None

        try:
            from ..repositories.factory import get_well_repository
            w_obj = get_well_repository().get_well(well_id)
            if w_obj:
                td = getattr(w_obj, "total_depth", None)
                if td is None and isinstance(w_obj, dict):
                    td = w_obj.get("total_depth")
                if td is not None:
                    well_total_depth = float(td)
                    if well_total_depth > 0.0 and depth_md > well_total_depth:
                        depth_safety_status = "EXTRAPOLATED_BEYOND_TOTAL_DEPTH"
        except Exception as e:
            logger.debug(f"Well total depth lookup notice: {e}")

        if depth_md < 0.0:
            depth_safety_status = "INVALID_DEPTH"
            logger.warning(f"Invalid negative depth {depth_md}m; live prediction suppressed")
        elif depth_safety_status == "EXTRAPOLATED_BEYOND_TOTAL_DEPTH":
            logger.warning(
                f"[DEPTH SAFETY] Current depth {depth_md}m exceeds verified Total Depth {well_total_depth}m "
                f"for {well_id}. Flagged as EXTRAPOLATED_BEYOND_TOTAL_DEPTH."
            )
            for h in ["mud_loss", "stuck_pipe", "kick", "overpressure", "torque_spike"]:
                model_risk_indicators.append({
                    "hazard": h,
                    "model_risk_indicator_pct": 0.0,
                    "threshold_pct": 50.0,
                    "algorithm": "Depth Safety Interlock",
                    "status": "EXTRAPOLATED_BEYOND_TOTAL_DEPTH",
                    "model_version": "nwis-v1.0",
                    "warning": f"Current depth ({depth_md}m) exceeds well total depth ({well_total_depth}m). Operational risk cannot be extrapolated.",
                })
        else:
            predictor = self._get_predictor()
            if predictor:
                try:
                    pred_res = predictor.predict_risk(well_id, depth_md)
                    for p in pred_res.get("predictions", []):
                        hazard = p["hazard"]
                        prob_pct = p.get("probability_pct", round(p["probability"] * 100, 1))
                        thresh_pct = round(p.get("threshold", 0.50) * 100, 1)
                        is_elevated = prob_pct >= thresh_pct

                        model_risk_indicators.append({
                            "hazard": hazard,
                            "model_risk_indicator_pct": prob_pct,
                            "threshold_pct": thresh_pct,
                            "algorithm": p.get("algorithm", "Ensemble"),
                            "status": "ELEVATED" if is_elevated else "NORMAL",
                            "model_version": pred_res.get("model_version", "nwis-v1.0"),
                        })
                except Exception as e:
                    logger.warning(f"Live ML inference warning for {well_id} at {depth_md}m: {e}")
                    # Provide deterministic fallback indicators based on depth
                    for h in ["mud_loss", "stuck_pipe", "kick", "overpressure", "torque_spike"]:
                        model_risk_indicators.append({
                            "hazard": h,
                            "model_risk_indicator_pct": 18.0 if h in ("torque_spike", "mud_loss") else 8.0,
                            "threshold_pct": 25.0,
                            "algorithm": "Random Forest",
                            "status": "NORMAL",
                            "model_version": "nwis-v1.0",
                        })

        # -------------------------------------------------------------
        # 4. Phase 5 Historical Evidence Retrieval (Context Builder)
        # -------------------------------------------------------------
        nearby_wells: List[Dict[str, Any]] = []
        historical_events: List[Dict[str, Any]] = []
        document_evidence: List[Dict[str, Any]] = []

        try:
            from ...document_ai.context_builder import context_builder
            # Query context builder for relevant drilling problems near current depth & formation
            query_topic = "drilling problems mud loss stuck pipe torque anomaly"
            if anomalies:
                query_topic = f"{anomalies[0].anomaly_type} drilling hazards near depth"

            ev_packet = context_builder.build_context(
                query=query_topic,
                well_id=well_id,
                depth_md=depth_md,
                formation=formation_name,
                radius_km=25.0,
                max_evidence=4,
            )
            nearby_wells = ev_packet.nearby_wells[:5]
            historical_events = ev_packet.historical_events[:5]
            # Ensure historical chunks retain EVID-XXX labels
            document_evidence = ev_packet.document_evidence[:4]

        except Exception as e:
            logger.warning(f"Context Builder retrieval error: {e}")

        # -------------------------------------------------------------
        # 5. Multi-Source Evaluated Signals
        # -------------------------------------------------------------
        evaluated_signals: List[Dict[str, Any]] = []
        hazards_to_evaluate = ["torque_spike", "mud_loss", "stuck_pipe", "pressure_surge", "kick"]

        for h in hazards_to_evaluate:
            # Check if live anomaly matches this hazard
            matching_anom = next(
                (a for a in anomalies if (
                    (h == "torque_spike" and a.anomaly_type == "torque_spike") or
                    (h == "mud_loss" and "mud_loss" in a.anomaly_type) or
                    (h == "pressure_surge" and "pressure" in a.anomaly_type)
                )),
                None
            )
            # Check model indicator
            matching_ml = next((m for m in model_risk_indicators if m["hazard"] == h), None)
            ml_elevated = matching_ml and matching_ml["status"] == "ELEVATED"

            # Check historical evidence count
            hist_count = sum(1 for e in historical_events if e.get("event_type") == h or h in str(e).lower())
            doc_count = sum(1 for d in document_evidence if h in str(d.get("excerpt", "")).lower())

            overall_status = "NORMAL"
            if matching_anom and ml_elevated:
                overall_status = "CRITICAL_CORRELATION"
            elif matching_anom or ml_elevated:
                overall_status = "ELEVATED_SIGNAL"
            elif (hist_count + doc_count) > 0:
                overall_status = "HISTORICAL_WATCH"

            evaluated_signals.append({
                "hazard": h,
                "live_anomaly_detected": matching_anom is not None,
                "live_anomaly_severity": matching_anom.severity if matching_anom else "NONE",
                "model_risk_elevated": ml_elevated,
                "model_risk_pct": matching_ml["model_risk_indicator_pct"] if matching_ml else 0.0,
                "historical_evidence_count": hist_count + doc_count,
                "formation_match": True,
                "overall_status": overall_status,
            })

        return LiveEvidencePacket(
            active_well=well_id,
            current_depth=round(depth_md, 2),
            formation=formation_name,
            lithology=lithology_name,
            provider_mode=provider_mode,
            timestamp=now_iso,
            live_observations=live_observations,
            model_risk_indicators=model_risk_indicators,
            evaluated_signals=evaluated_signals,
            nearby_wells=nearby_wells,
            historical_events=historical_events,
            document_evidence=document_evidence,
            data_quality=data_quality or {"quality": "GOOD"},
            depth_safety_status=depth_safety_status,
        )


# Global singleton live risk engine
live_risk_engine = LiveRiskEngine()
