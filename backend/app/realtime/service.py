"""
NWIS Phase 6 — Real-Time Operations Coordinator Service
======================================================
Unified orchestration of telemetry ingestion, validation, streaming features,
anomaly detection, Phase 3.1 ML inference, Context Builder, and Alert Engine.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

from .alert_engine import alert_engine
from .anomaly_detector import streaming_anomaly_detector
from .config import REALTIME_CONFIG
from .feature_engine import realtime_feature_engine
from .live_risk_engine import live_risk_engine, LiveEvidencePacket
from .live_state import live_well_state
from .providers import (
    demo_replay_provider,
    RESTPollingProvider,
    WebSocketProvider,
    RealtimeDrillingProvider,
)
from .schema import RealtimeTelemetryRecord, validate_telemetry_payload

logger = logging.getLogger("nwis.realtime.service")


class RealtimeDrillingService:
    """
    Central orchestration service for Phase 6 Real-Time Drilling Intelligence.
    """

    def __init__(self):
        self.active_provider: RealtimeDrillingProvider = demo_replay_provider
        self.last_packet: Optional[LiveEvidencePacket] = None
        self.last_features: Dict[str, Any] = {}

    def get_status(self) -> Dict[str, Any]:
        """Provides overall health, provider state, and transport diagnostics."""
        state_snap = live_well_state.get_state_snapshot()
        provider_health = self.active_provider.health()

        return {
            "status": "OPERATIONAL",
            "engine_version": REALTIME_CONFIG["system"]["engine_version"],
            "advisory_mode": REALTIME_CONFIG["system"]["advisory_mode_only"],
            "provider": provider_health,
            "live_well": state_snap,
            "active_alerts_count": len(alert_engine.get_alerts(status="ACTIVE")),
        }

    def process_telemetry_point(
        self,
        payload: Dict[str, Any],
        provider_mode: str = "LIVE FIELD DATA",
    ) -> Dict[str, Any]:
        """
        Processes an incoming real-time telemetry point through the complete pipeline:
        Validate -> Update State -> Compute Features -> Detect Anomalies ->
        Evaluate Risk -> Update Alerts.
        """
        is_valid, val_status, warnings, record = validate_telemetry_payload(payload)
        if not is_valid or not record:
            live_well_state.record_rejected("; ".join(warnings))
            return {
                "success": False,
                "validation_status": val_status,
                "errors": warnings,
            }

        # 1. Update live well state & persist telemetry
        live_well_state.update_telemetry(record, provider_mode=provider_mode, warnings=warnings)
        try:
            from ..repositories.factory import get_telemetry_repository
            get_telemetry_repository().record_telemetry(record.to_dict())
        except Exception as e:
            logger.debug(f"Telemetry persistence notice: {e}")

        # 2. Compute streaming features
        features = realtime_feature_engine.compute_features(
            history=live_well_state.telemetry_history,
            current_record=record,
        )
        self.last_features = features

        # 3. Detect anomalies (deterministic)
        anomalies = streaming_anomaly_detector.detect_anomalies(
            current_record=record,
            computed_features=features,
        )

        # 4. Evaluate live risk & context synthesis
        data_quality = live_well_state.get_data_quality()
        evidence_packet = live_risk_engine.evaluate_live_risk(
            record=record,
            anomalies=anomalies,
            provider_mode=provider_mode,
            data_quality=data_quality,
        )
        self.last_packet = evidence_packet

        # 5. Process through Alert Engine
        alerts = alert_engine.process_live_packet(evidence_packet)

        return {
            "success": True,
            "validation_status": val_status,
            "record": record.to_dict(),
            "anomalies_detected": [a.to_dict() for a in anomalies],
            "alerts_triggered": [a.to_dict() for a in alerts],
            "packet_summary": {
                "active_well": evidence_packet.active_well,
                "current_depth": evidence_packet.current_depth,
                "formation": evidence_packet.formation,
                "signals": evidence_packet.evaluated_signals,
            },
        }

    def poll_or_step(self, well_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Steps the active provider (e.g. DemoReplayProvider) and processes the latest slice.
        """
        target_well = well_id or live_well_state.well_id
        if isinstance(self.active_provider, type(demo_replay_provider)):
            if well_id and well_id.upper() != demo_replay_provider.active_well_id:
                demo_replay_provider.subscribe(well_id)

            rec = demo_replay_provider.step()
            if rec:
                return self.process_telemetry_point(rec.to_dict(), provider_mode="DEMO REPLAY")

        # Fallback to latest known record
        latest = self.active_provider.get_latest(target_well)
        if latest:
            return self.process_telemetry_point(latest.to_dict(), provider_mode="DEMO REPLAY")

        return {"success": False, "message": "No telemetry available from active provider"}

    def start_replay(
        self,
        well_id: str = "WELL-000050",
        interval_ms: int = 1000,
    ) -> Dict[str, Any]:
        """Starts real-time deterministic DEMO REPLAY."""
        self.active_provider = demo_replay_provider
        demo_replay_provider.start_replay(well_id=well_id, interval_ms=interval_ms)
        # Advance at least one step immediately so state updates
        res = self.poll_or_step(well_id)
        return {
            "mode": "DEMO REPLAY",
            "active": True,
            "well_id": well_id,
            "interval_ms": interval_ms,
            "initial_step": res,
        }

    def stop_replay(self) -> Dict[str, Any]:
        """Stops demo replay."""
        demo_replay_provider.stop_replay()
        return {
            "mode": "DEMO REPLAY",
            "active": False,
            "message": "Replay stopped",
        }

    def inject_anomaly(self, anomaly_type: str = "torque_spike") -> Dict[str, Any]:
        """Injects a real-time anomaly slice for testing/demonstration."""
        injected_rec = demo_replay_provider.inject_anomaly(anomaly_type)
        if injected_rec:
            return self.process_telemetry_point(injected_rec.to_dict(), provider_mode="DEMO REPLAY")
        return {"success": False, "message": "Failed to inject anomaly"}

    def get_latest_telemetry(self, well_id: str) -> Dict[str, Any]:
        state_snap = live_well_state.get_state_snapshot()
        return {
            "well_id": well_id.upper(),
            "live_state": state_snap,
            "latest_record": live_well_state.latest_record.to_dict() if live_well_state.latest_record else None,
        }

    def get_features(self, well_id: str) -> Dict[str, Any]:
        return {
            "well_id": well_id.upper(),
            "features": self.last_features,
            "data_quality": live_well_state.get_data_quality(),
        }

    def get_live_risks(self, well_id: str) -> Dict[str, Any]:
        if not self.last_packet or self.last_packet.active_well != well_id.upper():
            # If no packet yet, trigger one evaluation step
            self.poll_or_step(well_id)

        if self.last_packet:
            return {
                "well_id": well_id.upper(),
                "current_depth": self.last_packet.current_depth,
                "formation": self.last_packet.formation,
                "model_risk_indicators": self.last_packet.model_risk_indicators,
                "evaluated_signals": self.last_packet.evaluated_signals,
                "live_observations": self.last_packet.live_observations,
            }

        return {"well_id": well_id.upper(), "message": "No risk data calculated yet"}

    def get_live_context(self, well_id: str) -> Dict[str, Any]:
        if not self.last_packet or self.last_packet.active_well != well_id.upper():
            self.poll_or_step(well_id)

        if self.last_packet:
            return self.last_packet.to_dict()

        return {"well_id": well_id.upper(), "message": "No live context packet available"}

    def get_alerts(
        self,
        well_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return alert_engine.get_alerts(well_id=well_id, status=status)

    def acknowledge_alert(
        self,
        alert_id: str,
        reviewer: str = "Drilling Engineer",
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        alert = alert_engine.acknowledge_alert(alert_id=alert_id, reviewer=reviewer, note=note)
        return alert.to_dict()

    def close_alert(
        self,
        alert_id: str,
        reviewer: str = "Drilling Engineer",
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        alert = alert_engine.close_alert(alert_id=alert_id, reviewer=reviewer, note=note)
        return alert.to_dict()


# Global singleton realtime service
realtime_service = RealtimeDrillingService()
