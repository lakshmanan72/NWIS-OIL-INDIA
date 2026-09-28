"""
NWIS Phase 8 — WITSML Adapter
=============================
Bridges WITSML SOAP queries and XML parsing with NWIS Live Pipeline.
Normalizes incoming WITSML telemetry logs into RealtimeTelemetryRecord.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional, Tuple

from ...realtime.schema import RealtimeTelemetryRecord, validate_telemetry_payload
from ..identity_resolver import well_identity_resolver
from .client import WitsmlClient
from .config import get_safe_witsml_config
from .parser import WitsmlParser

logger = logging.getLogger("nwis.integrations.witsml.adapter")


class WITSMLAdapter:
    """
    Adapter bridging upstream WITSML log stores to NWIS canonical data contracts.
    """

    def __init__(self, client: Optional[WitsmlClient] = None):
        self.client = client or WitsmlClient()

    def connect(self) -> bool:
        return self.client.connect()

    def disconnect(self) -> None:
        self.client.disconnect()

    def health(self) -> Dict[str, Any]:
        h = self.client.get_health()
        h["config"] = get_safe_witsml_config()
        return h

    def ingest_xml(
        self,
        xml_text: str,
        default_well_id: str = "WELL-000050",
        store_raw: bool = False,
    ) -> List[Tuple[bool, str, Dict[str, Any], Optional[RealtimeTelemetryRecord]]]:
        """
        Parses WITSML XML, resolves well identities, validates physical parameters,
        and returns normalized records.
        """
        raw_records = WitsmlParser.parse_log_xml(xml_text, default_well_id=default_well_id)
        results = []

        for raw_rec in raw_records:
            ext_well = raw_rec.get("well_id", default_well_id)

            # Resolve well identity
            can_id, id_status, id_details = well_identity_resolver.resolve(
                external_source="WITSML",
                external_well_id=ext_well,
                raw_payload=raw_rec,
            )

            if not can_id or id_status == "UNMATCHED_WELL":
                results.append((False, "UNMATCHED_WELL", id_details, None))
                continue

            raw_rec["well_id"] = can_id

            # Validate physical parameters
            is_valid, qual_status, warnings, record = validate_telemetry_payload(
                payload=raw_rec,
                source="WITSML",
                store_raw=store_raw,
            )

            if not is_valid or not record:
                results.append((False, "INVALID_PHYSICAL_BOUNDS", {"warnings": warnings}, None))
            else:
                results.append((True, qual_status, {"warnings": warnings, "canonical_well_id": can_id}, record))

        return results

    def fetch_latest(self, well_id: Optional[str] = None) -> Optional[RealtimeTelemetryRecord]:
        """Queries WITSML store for latest log slice and returns validated record."""
        raw_xml = self.client.query_log_data(well_uid=well_id)
        if not raw_xml:
            return None

        results = self.ingest_xml(raw_xml, default_well_id=well_id or "WELL-000050")
        for success, _, _, record in reversed(results):
            if success and record:
                return record
        return None


# Global singleton instance
witsml_adapter = WITSMLAdapter()
