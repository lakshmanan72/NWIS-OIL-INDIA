"""
NWIS Phase 6 — Live Well State & Freshness Monitor
=================================================
Maintains real-time well telemetry state, rolling telemetry buffers,
data freshness lifecycle, and operational quality diagnostics.
"""

from __future__ import annotations
from collections import deque
from datetime import datetime, timezone
import time
from typing import Any, Deque, Dict, List, Optional

from .config import REALTIME_CONFIG
from .schema import RealtimeTelemetryRecord


class LiveWellState:
    """
    State container for an active drilling well stream.
    Tracks real-time parameters, rolling buffers, freshness transitions,
    and operational data quality.
    """

    def __init__(self, well_id: str = "WELL-000050", max_buffer_size: int = 100):
        self.well_id = well_id.upper()
        self.current_depth: float = 1132.0
        self.last_update_iso: Optional[str] = None
        self.last_update_epoch: float = 0.0
        self.provider_mode: str = "DEMO REPLAY"  # "DEMO REPLAY" or "LIVE FIELD DATA"
        self.telemetry_history: Deque[RealtimeTelemetryRecord] = deque(maxlen=max_buffer_size)
        self.latest_record: Optional[RealtimeTelemetryRecord] = None

        # Data quality counters
        self.total_records_processed: int = 0
        self.records_rejected_count: int = 0
        self.last_warning_messages: List[str] = []

        # Freshness configuration
        self.live_threshold = REALTIME_CONFIG["freshness"]["live_threshold_seconds"]
        self.delayed_threshold = REALTIME_CONFIG["freshness"]["delayed_threshold_seconds"]
        self.stale_threshold = REALTIME_CONFIG["freshness"]["stale_threshold_seconds"]

    def reset(self, well_id: str = "WELL-000050") -> None:
        """Resets the live state to a clean slate."""
        self.well_id = well_id.upper()
        self.current_depth = 1132.0
        self.last_update_iso = None
        self.last_update_epoch = 0.0
        self.provider_mode = "DEMO REPLAY"
        self.telemetry_history.clear()
        self.latest_record = None
        self.total_records_processed = 0
        self.records_rejected_count = 0
        self.last_warning_messages = []

    def update_telemetry(
        self,
        record: RealtimeTelemetryRecord,
        provider_mode: str = "DEMO REPLAY",
        warnings: Optional[List[str]] = None,
    ) -> None:
        """Ingests a validated real-time telemetry record into the live state."""
        rec_well = record.well_id.upper()
        if self.well_id != rec_well:
            self.reset(well_id=rec_well)

        self.well_id = rec_well

        # Out-of-order arrival check
        is_newer = True
        if self.last_update_iso and record.timestamp:
            try:
                cur_dt = datetime.fromisoformat(self.last_update_iso.replace("Z", "+00:00"))
                new_dt = datetime.fromisoformat(record.timestamp.replace("Z", "+00:00"))
                if new_dt < cur_dt:
                    is_newer = False
            except Exception:
                pass

        if is_newer:
            self.current_depth = record.depth_md
            self.last_update_iso = record.timestamp
            self.last_update_epoch = time.time()
            self.provider_mode = provider_mode
            self.latest_record = record

        self.telemetry_history.append(record)
        self.total_records_processed += 1
        if warnings:
            self.last_warning_messages = warnings

    def record_rejected(self, reason: str) -> None:
        self.records_rejected_count += 1
        self.last_warning_messages = [reason]

    @property
    def data_age_seconds(self) -> float:
        """Returns age of the last telemetry update in seconds."""
        if self.last_update_epoch == 0.0:
            return 999.0
        return max(0.0, round(time.time() - self.last_update_epoch, 2))

    def get_freshness_status(self) -> str:
        """
        Computes dynamic data freshness according to engineering criteria:
        < 5 sec: LIVE (or REPLAY if in Demo Replay mode)
        5–30 sec: DELAYED
        > 30 sec: STALE
        No data: DISCONNECTED
        """
        age = self.data_age_seconds
        if self.total_records_processed == 0 or age > 120.0:
            return "DISCONNECTED"

        if age > self.stale_threshold:
            return "STALE"
        if age > self.delayed_threshold:
            return "DELAYED"

        if self.provider_mode == "DEMO REPLAY":
            return "REPLAY"
        return "LIVE"

    def get_data_quality(self) -> Dict[str, Any]:
        """Assesses overall operational telemetry signal quality."""
        if not self.latest_record:
            return {
                "quality": "INVALID",
                "missing_fields_count": 10,
                "data_age_seconds": self.data_age_seconds,
                "warnings": ["No telemetry received"],
            }

        # Check missing optional telemetry fields
        rec_dict = self.latest_record.to_dict()
        optional_fields = [
            "rop_m_hr", "wob_klbf", "rpm", "torque_kftlb",
            "standpipe_pressure_psi", "flow_rate_lpm", "mud_weight_ppg",
            "mud_flow_in_lpm", "mud_flow_out_lpm", "gas_units"
        ]
        missing_count = sum(1 for k in optional_fields if rec_dict.get(k) is None)

        if missing_count > 6 or self.data_age_seconds > self.stale_threshold:
            quality = "DEGRADED"
        elif self.data_age_seconds > 120.0:
            quality = "INVALID"
        else:
            quality = "GOOD"

        return {
            "quality": quality,
            "missing_fields_count": missing_count,
            "data_age_seconds": self.data_age_seconds,
            "total_processed": self.total_records_processed,
            "total_rejected": self.records_rejected_count,
            "warnings": self.last_warning_messages,
        }

    def get_state_snapshot(self) -> Dict[str, Any]:
        """Serializes current live well state for API and WebSocket consumers."""
        freshness = self.get_freshness_status()
        quality_info = self.get_data_quality()

        return {
            "well_id": self.well_id,
            "current_depth": self.current_depth,
            "depth_md": self.current_depth,
            "last_update": self.last_update_iso or datetime.now(timezone.utc).isoformat(),
            "data_age_seconds": self.data_age_seconds,
            "freshness": freshness,
            "provider_mode": self.provider_mode,
            "connection_status": "ONLINE" if freshness in ("LIVE", "REPLAY", "DELAYED") else "OFFLINE",
            "latest_parameters": self.latest_record.to_dict() if self.latest_record else None,
            "buffer_depth_samples": len(self.telemetry_history),
            "data_quality": quality_info,
        }


# Global singleton live well state
live_well_state = LiveWellState()
