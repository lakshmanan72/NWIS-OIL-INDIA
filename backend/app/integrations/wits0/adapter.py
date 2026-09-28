"""
NWIS Phase 8 — WITS Level 0 (WITS0) Adapter
===========================================
Bridges WITS0 stream ingestion with NWIS Canonical Pipeline.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional, Tuple

from ...realtime.schema import RealtimeTelemetryRecord, validate_telemetry_payload
from ..ertmac.health import IntegrationHealthTracker
from ..identity_resolver import well_identity_resolver
from .parser import Wits0Parser

logger = logging.getLogger("nwis.integrations.wits0.adapter")


class WITS0Adapter:
    """
    Adapter for WITS Level 0 telemetry streams.
    """

    def __init__(self, endpoint_desc: str = "WITS0 Serial/TCP Interface"):
        self.health_tracker = IntegrationHealthTracker("WITS0", endpoint_desc)
        self.health_tracker.set_status("DISABLED", "WITS0 listener is on standby", connected=False)

    def connect(self) -> bool:
        self.health_tracker.set_status("CONNECTED", "WITS0 stream listener active", connected=True)
        return True

    def disconnect(self) -> None:
        self.health_tracker.set_status("DISCONNECTED", "WITS0 stream listener stopped", connected=False)

    def health(self) -> Dict[str, Any]:
        return self.health_tracker.get_snapshot()

    def ingest_packet(
        self,
        packet_text: str,
        default_well_id: str = "WELL-000050",
        store_raw: bool = False,
    ) -> Tuple[bool, str, Dict[str, Any], Optional[RealtimeTelemetryRecord]]:
        parsed = Wits0Parser.parse_packet(packet_text, default_well_id=default_well_id)
        if not parsed:
            return False, "INVALID_PACKET_FORMAT", {"error": "Failed to parse WITS0 packet"}, None

        ext_well = parsed.get("well_id", default_well_id)

        # Well Identity Resolution
        can_id, id_status, id_details = well_identity_resolver.resolve(
            external_source="WITS0",
            external_well_id=ext_well,
            raw_payload=parsed,
        )

        if not can_id or id_status == "UNMATCHED_WELL":
            return False, "UNMATCHED_WELL", id_details, None

        parsed["well_id"] = can_id

        is_valid, qual_status, warnings, record = validate_telemetry_payload(
            payload=parsed,
            source="WITS0",
            store_raw=store_raw,
        )

        if not is_valid or not record:
            self.health_tracker.record_error("Physical validation failure on WITS0 packet")
            return False, "INVALID_PHYSICAL_BOUNDS", {"warnings": warnings}, None

        self.health_tracker.record_success()
        return True, qual_status, {"warnings": warnings, "canonical_well_id": can_id}, record


wits0_adapter = WITS0Adapter()
