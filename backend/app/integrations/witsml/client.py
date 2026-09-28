"""
NWIS Phase 8 — WITSML SOAP & Store Client
=========================================
Interfaces with WITSML 1.3.1.1 / 1.4.1.1 servers via WMLS_GetFromStore.
Supports query framing by well, wellbore, log, time range, and depth range.
"""

from __future__ import annotations
import base64
import logging
import ssl
import time
from typing import Any, Dict, Optional
import urllib.error
import urllib.request

from ..ertmac.health import IntegrationHealthTracker
from .config import get_witsml_config

logger = logging.getLogger("nwis.integrations.witsml.client")


class WitsmlClient:
    """
    Client for Energistics WITSML Web Services (WMLS_GetFromStore).
    """

    def __init__(self, config_override: Optional[Dict[str, Any]] = None):
        self.config = config_override or get_witsml_config()
        self.health_tracker = IntegrationHealthTracker("WITSML", self.config.get("url"))
        self._backoff_delays = [1.0, 2.0, 4.0, 8.0, 16.0, 30.0]
        self._consecutive_failures = 0

        if not self.config["enabled"]:
            self.health_tracker.set_status("DISABLED", "WITSML integration is disabled via WITSML_ENABLED=false", connected=False)
        elif not self.config["url"]:
            self.health_tracker.set_status("DISABLED", "No server URL configured for WITSML", connected=False)
        else:
            self.health_tracker.set_status("DISCONNECTED", "Configured, awaiting connection initialization", connected=False)

    def connect(self) -> bool:
        """Verifies upstream WITSML server reachability."""
        if not self.config["enabled"]:
            self.health_tracker.set_status("DISABLED", "WITSML disabled", connected=False)
            logger.info("WITSML connect skipped: WITSML_ENABLED is false")
            return False

        if not self.config["url"]:
            self.health_tracker.set_status("DISABLED", "WITSML url missing", connected=False)
            logger.warning("WITSML connect skipped: url not configured")
            return False

        logger.info(f"Connecting to WITSML server at {self.config['url']}...")
        return self._execute_version_probe()

    def _execute_version_probe(self) -> bool:
        headers = self._build_headers("WMLS_GetVersion")
        soap_body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
            '<soap:Body>'
            '<WMLS_GetVersion xmlns="http://www.witsml.org/message/120"/>'
            '</soap:Body>'
            '</soap:Envelope>'
        ).encode("utf-8")

        start_t = time.time()
        try:
            req = urllib.request.Request(self.config["url"], data=soap_body, headers=headers, method="POST")
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

    def query_log_data(
        self,
        well_uid: Optional[str] = None,
        wellbore_uid: Optional[str] = None,
        depth_from: Optional[float] = None,
        depth_to: Optional[float] = None,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
    ) -> Optional[str]:
        """
        Executes a WMLS_GetFromStore log query with optional depth or time boundaries.
        Returns the raw XML log string.
        """
        if not self.config["enabled"] or not self.config["url"]:
            return None

        w_uid = well_uid or self.config.get("well_id", "")
        wb_uid = wellbore_uid or self.config.get("wellbore_id", "")

        query_xml = self._build_log_query_xml(
            well_uid=w_uid,
            wellbore_uid=wb_uid,
            depth_from=depth_from,
            depth_to=depth_to,
            time_from=time_from,
            time_to=time_to,
        )

        headers = self._build_headers("WMLS_GetFromStore")
        soap_body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
            '<soap:Body>'
            '<WMLS_GetFromStore xmlns="http://www.witsml.org/message/120">'
            '<WMLtypeIn>log</WMLtypeIn>'
            f'<QueryIn><![CDATA[{query_xml}]]></QueryIn>'
            '<OptionsIn>data=all</OptionsIn>'
            '<CapabilitiesIn/>'
            '</WMLS_GetFromStore>'
            '</soap:Body>'
            '</soap:Envelope>'
        ).encode("utf-8")

        start_t = time.time()
        try:
            req = urllib.request.Request(self.config["url"], data=soap_body, headers=headers, method="POST")
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=self.config["timeout_seconds"], context=ctx) as resp:
                latency = (time.time() - start_t) * 1000.0
                raw_resp = resp.read().decode("utf-8")
                self._consecutive_failures = 0
                self.health_tracker.record_success(latency_ms=latency)
                return raw_resp
        except Exception as e:
            self._handle_failure(str(e))
            return None

    def _build_log_query_xml(
        self,
        well_uid: str,
        wellbore_uid: str,
        depth_from: Optional[float] = None,
        depth_to: Optional[float] = None,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
    ) -> str:
        depth_filter = ""
        if depth_from is not None:
            depth_filter += f'<startIndex uom="m">{depth_from}</startIndex>'
        if depth_to is not None:
            depth_filter += f'<endIndex uom="m">{depth_to}</endIndex>'

        time_filter = ""
        if time_from is not None:
            time_filter += f"<startDateTimeIndex>{time_from}</startDateTimeIndex>"
        if time_to is not None:
            time_filter += f"<endDateTimeIndex>{time_to}</endDateTimeIndex>"

        return (
            '<logs xmlns="http://www.witsml.org/schemas/1series" version="1.4.1.1">'
            f'<log uidWell="{well_uid}" uidWellbore="{wellbore_uid}">'
            '<nameWell/>'
            '<nameWellbore/>'
            '<name/>'
            '<indexType>measured depth</indexType>'
            f"{depth_filter}"
            f"{time_filter}"
            "<logCurveInfo/>"
            "<logData/>"
            "</log>"
            "</logs>"
        )

    def _build_headers(self, soap_action: str) -> Dict[str, str]:
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f'"{soap_action}"',
            "User-Agent": "NWIS-WITSML-Adapter/8.0.0",
        }
        if self.config.get("username") and self.config.get("password"):
            auth_str = f"{self.config['username']}:{self.config['password']}"
            encoded = base64.b64encode(auth_str.encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {encoded}"
        return headers

    def _handle_failure(self, reason: str) -> None:
        self._consecutive_failures += 1
        self.health_tracker.record_reconnect()
        delay_idx = min(self._consecutive_failures - 1, len(self._backoff_delays) - 1)
        next_delay = self._backoff_delays[delay_idx]

        safe_reason = reason.replace(self.config.get("password", "___"), "***")
        logger.warning(
            f"WITSML server query failed ({safe_reason}). "
            f"Backoff delay: {next_delay}s. Attempt {self._consecutive_failures}/{self.config['max_retries']}"
        )
        self.health_tracker.record_error(f"WITSML failure: {safe_reason}")

    def disconnect(self) -> None:
        self._consecutive_failures = 0
        self.health_tracker.set_status("DISCONNECTED", "WITSML disconnected by operator", connected=False)
        logger.info("WITSML client disconnected")

    def get_health(self) -> Dict[str, Any]:
        return self.health_tracker.get_snapshot()
