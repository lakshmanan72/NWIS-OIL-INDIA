"""
NWIS Phase 8 — eRTMAC Telemetry Payload Schema & Channel Mapping
================================================================
Defines typical eRTMAC JSON REST payload fields and translation to NWIS canonical format.
"""

from __future__ import annotations
from typing import Any, Dict, Optional


# Canonical eRTMAC to NWIS field mapping dictionary
ERTMAC_CHANNEL_MAP = {
    "HOLE_DEPTH": "depth_md",
    "MD": "depth_md",
    "DEPTH": "depth_md",
    "ROP": "rop_m_hr",
    "DRILL_RATE": "rop_m_hr",
    "WOB": "wob_klbf",
    "BIT_WEIGHT": "wob_klbf",
    "SURF_RPM": "rpm",
    "RPM": "rpm",
    "SURF_TORQ": "torque_kftlb",
    "TORQUE": "torque_kftlb",
    "STANDPIPE_PRESS": "standpipe_pressure_psi",
    "SPP": "standpipe_pressure_psi",
    "FLOW_IN": "mud_flow_in_lpm",
    "MUD_FLOW_IN": "mud_flow_in_lpm",
    "FLOW_OUT": "mud_flow_out_lpm",
    "MUD_FLOW_OUT": "mud_flow_out_lpm",
    "TOTAL_GAS": "gas_units",
    "GAS": "gas_units",
    "MUD_WEIGHT": "mud_weight_ppg",
    "MW_IN": "mud_weight_ppg",
    "HOOK_LOAD": "hookload",
    "PUMP_PRESS": "pump_pressure",
}


def normalize_ertmac_payload(raw_payload: Dict[str, Any], default_well: str = "WELL-000050") -> Dict[str, Any]:
    """
    Translates an eRTMAC JSON message into the standard NWIS telemetry dictionary.
    Handles nested 'channels', 'data', or flat JSON key-value schemas.
    """
    output: Dict[str, Any] = {
        "source": "eRTMAC",
    }

    # Extract well identifier
    well_id = (
        raw_payload.get("well_id")
        or raw_payload.get("wellId")
        or raw_payload.get("well")
        or raw_payload.get("rig_id")
        or default_well
    )
    output["well_id"] = str(well_id).strip().upper()

    # Extract timestamp
    ts = (
        raw_payload.get("timestamp")
        or raw_payload.get("time")
        or raw_payload.get("dateTime")
        or raw_payload.get("ts")
    )
    if ts is not None:
        output["timestamp"] = ts

    # Check for nested channels object
    channels = raw_payload.get("channels") or raw_payload.get("data") or raw_payload

    for ext_key, val in channels.items():
        if val is None:
            continue
        norm_key = ERTMAC_CHANNEL_MAP.get(str(ext_key).upper())
        if norm_key:
            output[norm_key] = val
        elif ext_key.lower() in (
            "depth_md", "rop_m_hr", "wob_klbf", "rpm", "torque_kftlb",
            "standpipe_pressure_psi", "flow_rate_lpm", "mud_weight_ppg",
            "mud_flow_in_lpm", "mud_flow_out_lpm", "gas_units",
            "pump_pressure", "hookload", "bit_depth", "ecd"
        ):
            output[ext_key.lower()] = val

    return output
