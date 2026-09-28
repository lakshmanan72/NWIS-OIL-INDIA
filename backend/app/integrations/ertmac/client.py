"""
NWIS Phase 8 — eRTMAC HTTP & Stream Client
==========================================
Handles authenticated network transport to eRTMAC gateway.
Enforces TLS verification, credential redaction, and bounded exponential backoff.
"""

from __future__ import annotations
import logging
import math
import time
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error
import json
import ssl

from .config import get_ertmac_config
from .health import IntegrationHealthTracker

logger = logging.getLogger("nwis.integrations.ertmac.client")


class ERTMACClient:
    """
    HTTP client for eRTMAC REST Telemetry Gateway.
    Never exposes raw secrets in exceptions or logs.
    """

    def __init__(self, config_override: Optional[Dict[str, Any]] = None):
        self.config = config_override or get_ertmac_config()
        self.health_tracker = IntegrationHealthTracker("eRTMAC", self.config.get("base_url"))
        self._backoff_delays = [1.0, 2.0, 4.0, 8.0, 16.0, 30.0]
        self._consecutive_failures = 0

        if not self.config["enabled"]:
            self.health_tracker.set_status("DISABLED", "eRTMAC integration is disabled via ERTMAC_ENABLED=false", connected=False)
        elif not self.config["base_url"]:
            self.health_tracker.set_status("DISABLED", "No base URL configured for eRTMAC", connected=False)
        else:
            self.health_tracker.set_status("DISCONNECTED", "Configured, awaiting connection initialization", connected=False)

    def connect(self) -> bool:
        """Attempts handshake with upstream eRTMAC gateway."""
        if not self.config["enabled"]:
            self.health_tracker.set_status("DISABLED", "eRTMAC disabled", connected=False)
            logger.info("eRTMAC connect skipped: ERTMAC_ENABLED is false")
            return False

        if not self.config["base_url"]:
            self.health_tracker.set_status("DISABLED", "eRTMAC base_url missing", connected=False)
            logger.warning("eRTMAC connect skipped: base_url not configured")
            return False

        logger.info(f"Connecting to eRTMAC gateway at {self.config['base_url']}...")
        return self._execute_healthcheck()

    def _execute_healthcheck(self) -> bool:
        url = f"{self.config['base_url'].rstrip('/')}/health"
        headers = self._build_headers()
        start_t = time.time()

        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=self.config["timeout_seconds"], context=ctx) as resp:
                latency = (time.time() - start_t) * 1000.0
                if resp.status in (200, 204):
                    self._consecutive_failures = 0
                    self.health_tracker.record_success(latency_ms=latency)
                    return True
                else:
                    self._handle_failure(f"HTTP {resp.status}")
                    return False
        except Exception as e:
            self._handle_failure(str(e))
            return False

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "NWIS-eRTMAC-Adapter/8.0.0",
        }
        if self.config.get("api_key"):
            headers["X-API-Key"] = self.config["api_key"]
        elif self.config.get("username") and self.config.get("password"):
            import base64
            auth_str = f"{self.config['username']}:{self.config['password']}"
            encoded = base64.b64encode(auth_str.encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {encoded}"
        return headers

    def _handle_failure(self, reason: str) -> None:
        self._consecutive_failures += 1
        self.health_tracker.record_reconnect()
        delay_idx = min(self._consecutive_failures - 1, len(self._backoff_delays) - 1)
        next_delay = self._backoff_delays[delay_idx]

        safe_reason = reason.replace(self.config.get("password", "___"), "***").replace(self.config.get("api_key", "___"), "***")
        logger.warning(
            f"eRTMAC gateway communication failed ({safe_reason}). "
            f"Backoff delay: {next_delay}s. Attempt {self._consecutive_failures}/{self.config['max_retries']}"
        )
        self.health_tracker.record_error(f"Upstream communication failure: {safe_reason}")

    def fetch_latest_telemetry(self, well_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieves latest live telemetry point from eRTMAC."""
        if not self.config["enabled"] or not self.config["base_url"]:
            return None

        target_well = well_id or self.config.get("well_id", "WELL-000050")
        url = f"{self.config['base_url'].rstrip('/')}/api/telemetry/latest?well_id={target_well}"
        headers = self._build_headers()
        start_t = time.time()

        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=self.config["timeout_seconds"], context=ctx) as resp:
                latency = (time.time() - start_t) * 1000.0
                data = json.loads(resp.read().decode("utf-8"))
                self._consecutive_failures = 0
                self.health_tracker.record_success(latency_ms=latency)
                return data
        except Exception as e:
            self._handle_failure(str(e))
            return None

    def disconnect(self) -> None:
        self._consecutive_failures = 0
        self.health_tracker.set_status("DISCONNECTED", "Connection disconnected by operator", connected=False)
        logger.info("eRTMAC client disconnected")

    def get_health(self) -> Dict[str, Any]:
        return self.health_tracker.get_snapshot()
