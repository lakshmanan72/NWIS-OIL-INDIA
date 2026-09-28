"""
NWIS Phase 6 — Alert Engine & Deduplication Manager
===================================================
Manages engineering drilling alert lifecycle:
- Severity: INFO, LOW, MEDIUM, HIGH, CRITICAL
- Lifecycle: DETECTED -> EVALUATED -> ACTIVE -> ACKNOWLEDGED -> CLOSED
- Deduplication: Depth-window aggregation (e.g. 3185–3188 m) and cooldown suppression
- Persistence: JSON file store for state recovery
- Explicit governance: Alerts are NEVER automatically closed; requires engineer review
"""

from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional

from ..data_path import resolve_data_file
from .config import REALTIME_CONFIG
from .live_risk_engine import LiveEvidencePacket

logger = logging.getLogger("nwis.alert_engine")


@dataclass
class DrillingAlert:
    alert_id: str
    well_id: str
    hazard: str
    severity: str  # INFO, LOW, MEDIUM, HIGH, CRITICAL
    status: str    # DETECTED, EVALUATED, ACTIVE, ACKNOWLEDGED, CLOSED
    depth_from: float
    depth_to: float
    depth_interval: str
    formation: str
    created_at: str
    updated_at: str
    title: str
    description: str
    model_risk_indicator_pct: float
    historical_evidence_count: int
    live_observations: List[str] = field(default_factory=list)
    historical_citations: List[str] = field(default_factory=list)
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[str] = None
    closed_by: Optional[str] = None
    closed_at: Optional[str] = None
    engineer_note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AlertEngine:
    """
    Stateful alert engine implementing persistence-filtered alerting,
    depth-window grouping, cooldown hysteresis, and engineer review lifecycle.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.alerts: Dict[str, DrillingAlert] = {}
        self.alert_counter = 0
        self.last_alert_time_by_hazard: Dict[str, float] = {}
        self.anomaly_persistence_tracker: Dict[str, int] = {}
        self.storage_path = resolve_data_file("documents", "active_alerts.json")

        self._load_from_storage()

    def _load_from_storage(self) -> None:
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data.get("alerts", []):
                        alert = DrillingAlert(**item)
                        self.alerts[alert.alert_id] = alert
                        # Update counter
                        try:
                            num = int(alert.alert_id.split("-")[-1])
                            if num > self.alert_counter:
                                self.alert_counter = num
                        except Exception:
                            pass
            except Exception as e:
                logger.warning(f"Could not load alerts from storage: {e}")

    def _save_to_storage(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(
                    {"alerts": [a.to_dict() for a in self.alerts.values()], "count": len(self.alerts)},
                    f,
                    indent=2,
                )
            # Dual repository persistence
            try:
                from ..repositories.factory import get_alert_repository
                repo = get_alert_repository()
                for a in self.alerts.values():
                    repo.create_alert(a.to_dict())
            except Exception as e:
                logger.debug(f"Alert repository persistence notice: {e}")
        except Exception as e:
            logger.error(f"Failed to persist alerts to storage: {e}")

    def process_live_packet(self, packet: LiveEvidencePacket) -> List[DrillingAlert]:
        """
        Evaluates LiveEvidencePacket to update active alerts or trigger new alerts.
        Applies depth-window deduplication and cooldown periods.
        """
        new_or_updated: List[DrillingAlert] = []
        now_epoch = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()
        well_id = packet.active_well
        cur_depth = packet.current_depth
        formation = packet.formation
        cooldown_sec = REALTIME_CONFIG["alerts"]["cooldown_seconds"]
        depth_window = REALTIME_CONFIG["alerts"]["depth_grouping_window_m"]
        persistence_needed = REALTIME_CONFIG["alerts"]["persistence_samples_required"]

        with self._lock:
            # Check for anomalies in the packet
            for obs in packet.live_observations:
                anom_type = obs.get("anomaly_type", "unknown")
                hazard_key = anom_type.split("_")[0]  # e.g. "torque" from "torque_spike"

                # Update persistence tracker
                current_hits = self.anomaly_persistence_tracker.get(hazard_key, 0) + 1
                self.anomaly_persistence_tracker[hazard_key] = current_hits

                # Check if an existing ACTIVE or ACKNOWLEDGED alert for this well and hazard is within depth_window
                existing_alert: Optional[DrillingAlert] = None
                for a in self.alerts.values():
                    if a.well_id == well_id and a.status in ("ACTIVE", "ACKNOWLEDGED"):
                        if (a.hazard == anom_type or hazard_key in a.hazard):
                            # Depth proximity check
                            if abs(cur_depth - a.depth_to) <= depth_window or abs(cur_depth - a.depth_from) <= depth_window:
                                existing_alert = a
                                break

                if existing_alert:
                    # Deduplication: expand existing alert's depth range instead of creating a duplicate
                    new_from = min(existing_alert.depth_from, cur_depth)
                    new_to = max(existing_alert.depth_to, cur_depth)
                    existing_alert.depth_from = round(new_from, 1)
                    existing_alert.depth_to = round(new_to, 1)
                    existing_alert.depth_interval = f"{new_from:.0f}–{new_to:.0f} m" if new_from != new_to else f"{new_from:.0f} m"
                    existing_alert.updated_at = now_iso
                    if obs.get("live_id") and obs["live_id"] not in existing_alert.live_observations:
                        existing_alert.live_observations.append(obs["live_id"])
                    new_or_updated.append(existing_alert)
                    self._save_to_storage()
                    continue

                # Cooldown check for new alert
                last_time = self.last_alert_time_by_hazard.get(hazard_key, 0.0)
                if (now_epoch - last_time) < cooldown_sec and current_hits < 4:
                    continue  # Suppressed by cooldown

                # Multi-signal check: require persistence OR elevated ML indicator OR historical evidence
                matching_sig = next((s for s in packet.evaluated_signals if hazard_key in s["hazard"]), None)
                ml_elevated = matching_sig and matching_sig.get("model_risk_elevated", False)
                hist_count = matching_sig.get("historical_evidence_count", 0) if matching_sig else 0

                should_alert = (
                    current_hits >= persistence_needed or
                    ml_elevated or
                    hist_count > 0 or
                    obs.get("severity") in ("HIGH", "CRITICAL")
                )

                if should_alert:
                    self.alert_counter += 1
                    alert_id = f"ALT-{self.alert_counter:06d}"
                    severity = obs.get("severity", "MEDIUM")
                    if ml_elevated and hist_count > 0:
                        severity = "HIGH"

                    citations = [d["evidence_id"] for d in packet.document_evidence if "evidence_id" in d]
                    live_refs = [obs["live_id"]] if obs.get("live_id") else []

                    hazard_title = anom_type.replace("_", " ").title()
                    new_alert = DrillingAlert(
                        alert_id=alert_id,
                        well_id=well_id,
                        hazard=anom_type,
                        severity=severity,
                        status="ACTIVE",
                        depth_from=round(cur_depth, 1),
                        depth_to=round(cur_depth, 1),
                        depth_interval=f"{cur_depth:.0f} m",
                        formation=formation,
                        created_at=now_iso,
                        updated_at=now_iso,
                        title=f"{hazard_title} in {formation} Formation",
                        description=obs.get("description") or f"Telemetry indicates {anom_type} at {cur_depth} m.",
                        model_risk_indicator_pct=matching_sig.get("model_risk_pct", 0.0) if matching_sig else 0.0,
                        historical_evidence_count=hist_count,
                        live_observations=live_refs,
                        historical_citations=citations,
                    )
                    self.alerts[alert_id] = new_alert
                    self.last_alert_time_by_hazard[hazard_key] = now_epoch
                    new_or_updated.append(new_alert)
                    self._save_to_storage()

            return new_or_updated

    def acknowledge_alert(
        self,
        alert_id: str,
        reviewer: str = "Drilling Engineer",
        note: Optional[str] = None,
    ) -> DrillingAlert:
        with self._lock:
            if alert_id not in self.alerts:
                raise KeyError(f"Alert {alert_id} not found")

            alert = self.alerts[alert_id]
            alert.status = "ACKNOWLEDGED"
            alert.acknowledged_by = reviewer
            alert.acknowledged_at = datetime.now(timezone.utc).isoformat()
            if note:
                alert.engineer_note = note
            alert.updated_at = alert.acknowledged_at
            self._save_to_storage()

            try:
                from ..security.audit import log_audit_event
                log_audit_event(
                    username=reviewer,
                    role="DRILLING_ENGINEER",
                    action="ALERT_ACKNOWLEDGED",
                    resource_type="ALERT",
                    resource_id=alert_id,
                    well_id=alert.well_id,
                    depth_md=alert.depth_to,
                    reason=note,
                )
            except Exception:
                pass

            return alert

    def close_alert(
        self,
        alert_id: str,
        reviewer: str = "Drilling Engineer",
        note: Optional[str] = None,
    ) -> DrillingAlert:
        with self._lock:
            if alert_id not in self.alerts:
                raise KeyError(f"Alert {alert_id} not found")

            alert = self.alerts[alert_id]
            alert.status = "CLOSED"
            alert.closed_by = reviewer
            alert.closed_at = datetime.now(timezone.utc).isoformat()
            if note:
                alert.engineer_note = note
            alert.updated_at = alert.closed_at
            self._save_to_storage()

            try:
                from ..security.audit import log_audit_event
                log_audit_event(
                    username=reviewer,
                    role="DRILLING_ENGINEER",
                    action="ALERT_CLOSED",
                    resource_type="ALERT",
                    resource_id=alert_id,
                    well_id=alert.well_id,
                    depth_md=alert.depth_to,
                    reason=note,
                )
            except Exception:
                pass

            return alert

    def get_alerts(
        self,
        well_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            results: List[Dict[str, Any]] = []
            for a in self.alerts.values():
                if well_id and a.well_id.upper() != well_id.upper():
                    continue
                if status and a.status.upper() != status.upper():
                    continue
                results.append(a.to_dict())
            # Return sorted newest first
            return sorted(results, key=lambda x: x["created_at"], reverse=True)


# Global singleton alert engine
alert_engine = AlertEngine()
