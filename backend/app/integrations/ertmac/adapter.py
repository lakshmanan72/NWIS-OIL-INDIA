"""
NWIS Phase 8 — eRTMAC Adapter
=============================
Integrates eRTMAC Client and Schema Normalizer with NWIS Live Pipeline.
Normalizes incoming eRTMAC telemetry into RealtimeTelemetryRecord.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, Optional, Tuple

from ...realtime.schema import RealtimeTelemetryRecord, validate_telemetry_payload
from ..identity_resolver import well_identity_resolver
from .client import ERTMACClient
from .config import get_safe_ertmac_config
from .schema import normalize_ertmac_payload

logger = logging.getLogger("nwis.integrations.ertmac.adapter")


class ERTMACAdapter:
    """
    Adapter bridging eRTMAC upstream streams into NWIS canonical data contracts.
    """

    def __init__(self, client: Optional[ERTMACClient] = None):
        self.client = client or ERTMACClient()

    def connect(self) -> bool:
        return self.client.connect()

    def disconnect(self) -> None:
        self.client.disconnect()

    def health(self) -> Dict[str, Any]:
        h = self.client.get_health()
        h["config"] = get_safe_ertmac_config()
        return h

    def ingest_payload(
        self,
        raw_payload: Dict[str, Any],
        store_raw: bool = False,
    ) -> Tuple[bool, str, Dict[str, Any], Optional[RealtimeTelemetryRecord]]:
        """
        Processes a raw incoming eRTMAC payload through normalization,
        identity resolution, and validation.
        """
        # 1. Normalize fields into standard keys
        normalized = normalize_ertmac_payload(raw_payload)
        ext_well = normalized.get("well_id", "UNKNOWN")

        # 2. Resolve well identity
        can_id, id_status, id_details = well_identity_resolver.resolve(
            external_source="eRTMAC",
            external_well_id=ext_well,
            raw_payload=raw_payload,
        )

        if not can_id or id_status == "UNMATCHED_WELL":
            return False, "UNMATCHED_WELL", id_details, None

        normalized["well_id"] = can_id

        # 3. Validate physical bounds and timestamps
        is_valid, qual_status, warnings, record = validate_telemetry_payload(
            payload=normalized,
            source="eRTMAC",
            store_raw=store_raw,
        )

        if not is_valid or not record:
            return False, "INVALID_PHYSICAL_BOUNDS", {"warnings": warnings}, None

        return True, qual_status, {"warnings": warnings, "canonical_well_id": can_id}, record

    def fetch_latest(self, well_id: Optional[str] = None) -> Optional[RealtimeTelemetryRecord]:
        raw = self.client.fetch_latest_telemetry(well_id)
        if not raw:
            return None
        success, _, _, record = self.ingest_payload(raw)
        return record if success else None


# Global singleton instance
ertmac_adapter = ERTMACAdapter()
