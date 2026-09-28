"""
NWIS Phase 8 — WITS Level 0 (WITS0) Stream & Packet Parser
==========================================================
Parses standard WITS0 serial/TCP packets (Record 01: Time-Based, Record 02: Depth-Based)
into normalized NWIS telemetry records.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("nwis.integrations.wits0.parser")

# WITS0 Record 01 (General Time-Based) and Record 02 (Drilling Depth-Based) item mappings
WITS0_ITEM_MAP = {
    # Record 01: General Time-Based
    "0108": "depth_md",
    "0110": "rop_m_hr",
    "0111": "hookload",
    "0112": "wob_klbf",
    "0113": "torque_kftlb",
    "0114": "rpm",
    "0115": "standpipe_pressure_psi",
    "0116": "pump_pressure",
    "0120": "mud_flow_in_lpm",
    "0121": "mud_flow_out_lpm",
    "0123": "gas_units",
    "0124": "mud_weight_ppg",
    # Record 02: Drilling Depth-Based
    "0208": "bit_depth",
    "0209": "depth_md",
    "0210": "rop_m_hr",
    "0211": "wob_klbf",
    "0212": "hookload",
    "0213": "torque_kftlb",
    "0214": "rpm",
    "0215": "standpipe_pressure_psi",
    "0220": "mud_flow_in_lpm",
    "0221": "mud_flow_out_lpm",
    "0223": "gas_units",
}


class Wits0Parser:
    """
    Parser for WITS Level 0 data stream blocks framed by '&&' and '!!'.
    """

    @classmethod
    def parse_packet(cls, packet_text: str, default_well_id: str = "WELL-000050") -> Optional[Dict[str, Any]]:
        """
        Parses a single WITS0 packet block.
        Example packet:
            &&
            0101WELL-ABC
            01081155.5
            011024.2
            011214.8
            011319.4
            011498.0
            01151920.0
            01201250.0
            01211240.0
            01234.5
            !!
        """
        if not packet_text:
            return None

        lines = [line.strip() for line in packet_text.strip().splitlines() if line.strip()]
        record: Dict[str, Any] = {
            "well_id": default_well_id,
            "source": "WITS0",
        }

        for line in lines:
            if line in ("&&", "!!"):
                continue

            if len(line) < 4:
                continue

            code = line[:4]
            val_str = line[4:].strip()

            # Record 0101 / 0201 = Well Identifier
            if code in ("0101", "0201"):
                record["well_id"] = val_str.upper()
                continue

            # Record 0105 / 0205 = Date/Time or time string
            if code in ("0105", "0205"):
                record["timestamp"] = val_str
                continue

            if code in WITS0_ITEM_MAP:
                field_name = WITS0_ITEM_MAP[code]
                try:
                    f_val = float(val_str)
                    if f_val not in (-999.25, -9999.0, -999.0):
                        record[field_name] = round(f_val, 3)
                except ValueError:
                    pass

        if record.get("depth_md") is not None:
            return record
        return None

    @classmethod
    def parse_stream(cls, stream_text: str, default_well_id: str = "WELL-000050") -> List[Dict[str, Any]]:
        """Splits multi-packet streams and parses each block."""
        blocks = stream_text.split("&&")
        records = []
        for blk in blocks:
            if not blk.strip():
                continue
            rec = cls.parse_packet(blk, default_well_id=default_well_id)
            if rec:
                records.append(rec)
        return records
