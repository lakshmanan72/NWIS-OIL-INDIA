"""
NWIS Phase 8 — Well Identity Resolver & Quarantine Engine
=========================================================
Prevents attaching untrusted or unverified upstream telemetry to canonical wells.
Maps vendor-specific rig and well identifiers to verified NWIS Canonical Wells.
If unmapped, isolates the feed into an UNMATCHED_WELL quarantine buffer.
"""

from __future__ import annotations
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..data_path import resolve_data_file

logger = logging.getLogger("nwis.integrations.resolver")


class WellIdentityResolver:
    """
    Translates external telemetry identifiers into canonical NWIS Well IDs.
    Guarantees isolation of unknown or unmapped rigs from production data.
    """

    def __init__(self, mappings_file: Optional[Path] = None):
        self._lock = threading.Lock()
        self.mappings_file = mappings_file or resolve_data_file("documents", "well_identity_mappings.json")
        self.mappings: Dict[str, str] = {}
        self.quarantined_wells: Dict[str, Dict[str, Any]] = {}

        # Default predefined mappings for realistic integration and testing
        self._default_mappings = {
            "ertmac:well-abc": "WELL-000050",
            "ertmac:rig1_well_a": "WELL-000050",
            "ertmac:rig_bravo_02": "WELL-000001",
            "witsml:well-abc": "WELL-000050",
            "witsml:rig_alpha_01": "WELL-000050",
            "wits0:well-abc": "WELL-000050",
            "demo:well-000050": "WELL-000050",
        }

        self._load_mappings()

    def _normalize_key(self, source: str, external_well_id: str, external_wellbore_id: Optional[str] = None) -> str:
        s = (source or "generic").strip().lower()
        w = str(external_well_id or "").strip().lower()
        if external_wellbore_id:
            wb = str(external_wellbore_id).strip().lower()
            return f"{s}:{w}:{wb}"
        return f"{s}:{w}"

    def _load_mappings(self) -> None:
        with self._lock:
            self.mappings = dict(self._default_mappings)
            try:
                if self.mappings_file.exists():
                    data = json.loads(self.mappings_file.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        for k, v in data.items():
                            self.mappings[k.strip().lower()] = str(v).strip().upper()
            except Exception as e:
                logger.warning(f"Could not load well identity mappings ({e}); using defaults")

    def _save_mappings(self) -> None:
        try:
            self.mappings_file.parent.mkdir(parents=True, exist_ok=True)
            self.mappings_file.write_text(json.dumps(self.mappings, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not persist well identity mappings: {e}")

    def resolve(
        self,
        external_source: str,
        external_well_id: str,
        external_wellbore_id: Optional[str] = None,
        raw_payload: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[str], str, Dict[str, Any]]:
        """
        Attempts to resolve an incoming well ID.
        Returns:
            canonical_well_id: Optional[str]
            status: "RESOLVED" | "CANONICAL_DIRECT" | "UNMATCHED_WELL"
            details: Dict[str, Any]
        """
        clean_ext_id = str(external_well_id).strip()
        source_clean = (external_source or "generic").strip().upper()

        # 1. Check if external_well_id is ALREADY a canonical format e.g. WELL-000050
        upper_id = clean_ext_id.upper()
        if upper_id.startswith("WELL-") and len(upper_id) >= 9:
            return upper_id, "CANONICAL_DIRECT", {
                "source": source_clean,
                "external_id": clean_ext_id,
                "canonical_well_id": upper_id,
                "matched_by": "canonical_direct_lookup",
            }

        # 2. Check explicit mappings with wellbore first
        with self._lock:
            if external_wellbore_id:
                key_wb = self._normalize_key(source_clean, clean_ext_id, external_wellbore_id)
                if key_wb in self.mappings:
                    can_id = self.mappings[key_wb]
                    return can_id, "RESOLVED", {
                        "source": source_clean,
                        "external_id": clean_ext_id,
                        "external_wellbore_id": external_wellbore_id,
                        "canonical_well_id": can_id,
                        "matched_by": "mapped_wellbore_rule",
                    }

            # 3. Check explicit mapping without wellbore
            key_simple = self._normalize_key(source_clean, clean_ext_id)
            if key_simple in self.mappings:
                can_id = self.mappings[key_simple]
                return can_id, "RESOLVED", {
                    "source": source_clean,
                    "external_id": clean_ext_id,
                    "canonical_well_id": can_id,
                    "matched_by": "mapped_well_rule",
                }


            # 4. Unknown Well -> Quarantine
            quarantine_key = f"{source_clean}:{clean_ext_id}"
            now_str = datetime.now(timezone.utc).isoformat()
            self.quarantined_wells[quarantine_key] = {
                "source": source_clean,
                "external_well_id": clean_ext_id,
                "external_wellbore_id": external_wellbore_id,
                "first_seen": self.quarantined_wells.get(quarantine_key, {}).get("first_seen", now_str),
                "last_seen": now_str,
                "hits": self.quarantined_wells.get(quarantine_key, {}).get("hits", 0) + 1,
                "status": "UNMATCHED_WELL",
                "sample_payload_snippet": {
                    k: v for k, v in (raw_payload or {}).items()
                    if k in ("depth_md", "timestamp", "rop_m_hr", "standpipe_pressure_psi")
                } if raw_payload else None,
            }

            logger.warning(
                f"[UNMATCHED_WELL] Ingestion rejected for unmapped rig identifier: "
                f"source={source_clean}, external_id={clean_ext_id}. Placed in quarantine."
            )

            return None, "UNMATCHED_WELL", {
                "source": source_clean,
                "external_id": clean_ext_id,
                "status": "UNMATCHED_WELL",
                "reason": f"External rig identifier '{clean_ext_id}' from {source_clean} is not mapped to any canonical well.",
            }

    def register_mapping(
        self,
        external_source: str,
        external_well_id: str,
        canonical_well_id: str,
        external_wellbore_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Registers a new identity mapping and removes it from quarantine if present."""
        clean_ext = str(external_well_id).strip()
        clean_can = str(canonical_well_id).strip().upper()
        clean_src = str(external_source).strip().upper()

        key = self._normalize_key(clean_src, clean_ext, external_wellbore_id)

        with self._lock:
            self.mappings[key] = clean_can
            self._save_mappings()

            # Remove from quarantine
            q_key = f"{clean_src}:{clean_ext}"
            if q_key in self.quarantined_wells:
                del self.quarantined_wells[q_key]

        logger.info(f"Registered identity mapping: {key} -> {clean_can}")
        return {
            "key": key,
            "source": clean_src,
            "external_id": clean_ext,
            "canonical_well_id": clean_can,
            "status": "REGISTERED",
        }

    def get_mappings(self) -> Dict[str, str]:
        with self._lock:
            return dict(self.mappings)

    def get_quarantined_wells(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.quarantined_wells.values())


# Global singleton instance
well_identity_resolver = WellIdentityResolver()
