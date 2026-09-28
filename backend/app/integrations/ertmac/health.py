"""
NWIS Phase 8 — Integration Health Tracking
==========================================
Standardized health telemetry for all integration adapters.
"""

from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import threading
from typing import Any, Dict, Optional


@dataclass
class IntegrationHealth:
    provider: str
    connected: bool = False
    status: str = "DISABLED"  # CONNECTED | DEGRADED | STALE | DISCONNECTED | DISABLED
    last_message_time: Optional[str] = None
    last_success_time: Optional[str] = None
    last_error_time: Optional[str] = None
    message_count: int = 0
    error_count: int = 0
    latency_ms: float = 0.0
    reconnect_count: int = 0
    endpoint_url: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class IntegrationHealthTracker:
    """Thread-safe tracker for adapter operational health metrics."""

    def __init__(self, provider_name: str, endpoint_url: Optional[str] = None):
        self._lock = threading.Lock()
        self.health = IntegrationHealth(
            provider=provider_name,
            endpoint_url=endpoint_url,
        )

    def record_success(self, latency_ms: float = 0.0) -> None:
        with self._lock:
            now_iso = datetime.now(timezone.utc).isoformat()
            self.health.connected = True
            self.health.last_success_time = now_iso
            self.health.last_message_time = now_iso
            self.health.message_count += 1
            self.health.latency_ms = round(latency_ms, 2)
            if self.health.latency_ms > 5000.0:
                self.health.status = "DEGRADED"
                self.health.notes = f"High transport latency: {self.health.latency_ms}ms"
            else:
                self.health.status = "CONNECTED"
                self.health.notes = "Stream active and nominal"

    def record_error(self, error_msg: str) -> None:
        with self._lock:
            now_iso = datetime.now(timezone.utc).isoformat()
            self.health.last_error_time = now_iso
            self.health.error_count += 1
            self.health.notes = error_msg
            if self.health.error_count > 3:
                self.health.connected = False
                self.health.status = "DISCONNECTED"
            else:
                self.health.status = "DEGRADED"

    def record_reconnect(self) -> None:
        with self._lock:
            self.health.reconnect_count += 1

    def set_status(self, status: str, notes: Optional[str] = None, connected: Optional[bool] = None) -> None:
        with self._lock:
            self.health.status = status
            if notes is not None:
                self.health.notes = notes
            if connected is not None:
                self.health.connected = connected

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            # Check for staleness if currently connected
            if self.health.connected and self.health.last_message_time:
                try:
                    last_dt = datetime.fromisoformat(self.health.last_message_time.replace("Z", "+00:00"))
                    age_sec = (datetime.now(timezone.utc) - last_dt).total_seconds()
                    if age_sec > 60.0:
                        self.health.status = "STALE"
                        self.health.notes = f"No telemetry received in {int(age_sec)}s"
                except Exception:
                    pass
            return self.health.to_dict()
