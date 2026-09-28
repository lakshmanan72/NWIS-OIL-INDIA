"""
NWIS Phase 6 — Real-Time Telemetry Schema & Validation Engine
============================================================
Enforces physical plausibility, strict typing, and validation transparency.
"""

from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class RealtimeTelemetryRecord:
    timestamp: str
    well_id: str
    depth_md: float
    rop_m_hr: Optional[float] = None
    wob_klbf: Optional[float] = None
    rpm: Optional[float] = None
    torque_kftlb: Optional[float] = None
    standpipe_pressure_psi: Optional[float] = None
    flow_rate_lpm: Optional[float] = None
    mud_weight_ppg: Optional[float] = None
    mud_flow_in_lpm: Optional[float] = None
    mud_flow_out_lpm: Optional[float] = None
    gas_units: Optional[float] = None
    # Phase 8 Enhanced Channels
    pump_pressure: Optional[float] = None
    hookload: Optional[float] = None
    bit_depth: Optional[float] = None
    block_position: Optional[float] = None
    ecd: Optional[float] = None
    temperature: Optional[float] = None
    chlorides: Optional[float] = None
    source: str = "DEMO_REPLAY"
    quality_status: str = "VALID"
    source_timestamp: Optional[str] = None
    ingestion_timestamp: Optional[str] = None
    ingestion_latency_ms: Optional[float] = None
    raw_payload: Optional[Dict[str, Any]] = None

    @property
    def rop(self) -> Optional[float]:
        return self.rop_m_hr

    @property
    def wob(self) -> Optional[float]:
        return self.wob_klbf

    @property
    def torque(self) -> Optional[float]:
        return self.torque_kftlb

    @property
    def spp(self) -> Optional[float]:
        return self.standpipe_pressure_psi

    @property
    def mud_flow_in(self) -> Optional[float]:
        return self.mud_flow_in_lpm

    @property
    def mud_flow_out(self) -> Optional[float]:
        return self.mud_flow_out_lpm

    @property
    def gas(self) -> Optional[float]:
        return self.gas_units

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["rop"] = self.rop_m_hr
        d["wob"] = self.wob_klbf
        d["torque"] = self.torque_kftlb
        d["spp"] = self.standpipe_pressure_psi
        d["mud_flow_in"] = self.mud_flow_in_lpm
        d["mud_flow_out"] = self.mud_flow_out_lpm
        d["gas"] = self.gas_units
        return d


# Physical bounds for validation (Standard Drilling Engineering Ranges)
PHYSICAL_RANGES = {
    "depth_md": (0.0, 12000.0),
    "rop_m_hr": (0.0, 300.0),
    "wob_klbf": (0.0, 150.0),
    "rpm": (0.0, 350.0),
    "torque_kftlb": (0.0, 100.0),
    "standpipe_pressure_psi": (0.0, 10000.0),
    "flow_rate_lpm": (0.0, 6000.0),
    "mud_weight_ppg": (6.0, 22.0),
    "mud_flow_in_lpm": (0.0, 6000.0),
    "mud_flow_out_lpm": (0.0, 6000.0),
    "gas_units": (0.0, 10000.0),
    "pump_pressure": (0.0, 10000.0),
    "hookload": (0.0, 1500.0),
    "bit_depth": (0.0, 12000.0),
    "block_position": (0.0, 50.0),
    "ecd": (6.0, 25.0),
    "temperature": (-20.0, 250.0),
    "chlorides": (0.0, 250000.0),
}


def validate_telemetry_payload(
    payload: Dict[str, Any],
    source: str = "LIVE_FIELD",
    store_raw: bool = False,
) -> Tuple[bool, str, List[str], Optional[RealtimeTelemetryRecord]]:
    """
    Validates an incoming real-time telemetry dictionary against physical domain bounds.
    Normalizes timestamps to UTC, computes ingestion latency, and evaluates data quality.

    Returns:
        is_valid: bool
        status: "VALID" | "VALID_WITH_WARNINGS" | "SUSPECT" | "STALE" | "INVALID"
        warnings: List[str]
        record: Optional[RealtimeTelemetryRecord]
    """
    now_utc = datetime.now(timezone.utc)
    ingestion_ts = now_utc.isoformat()

    if not isinstance(payload, dict):
        return False, "INVALID", ["Payload must be a JSON object dictionary"], None

    warnings: List[str] = []
    errors: List[str] = []

    # 1. Required: well_id
    raw_well_id = payload.get("well_id") or payload.get("wellId") or payload.get("canonical_well_id")
    if not raw_well_id or not isinstance(raw_well_id, str) or not raw_well_id.strip():
        errors.append("Missing required field: well_id")
        well_id = "UNKNOWN"
    else:
        well_id = raw_well_id.strip().upper()

    # 2. Required: timestamp (normalized to UTC)
    raw_ts = payload.get("timestamp") or payload.get("source_timestamp") or payload.get("time")
    source_timestamp_str = str(raw_ts).strip() if raw_ts is not None else None
    parsed_dt = None
    ingestion_latency_ms: Optional[float] = None

    if raw_ts is None:
        warnings.append("Missing source timestamp; defaulting to ingestion UTC timestamp")
        parsed_dt = now_utc
        timestamp_str = ingestion_ts
    else:
        try:
            if isinstance(raw_ts, (int, float)):
                parsed_dt = datetime.fromtimestamp(float(raw_ts), tz=timezone.utc)
            else:
                iso_clean = str(raw_ts).strip().replace("Z", "+00:00")
                parsed_dt = datetime.fromisoformat(iso_clean)
                if parsed_dt.tzinfo is None:
                    parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
                else:
                    parsed_dt = parsed_dt.astimezone(timezone.utc)

            timestamp_str = parsed_dt.isoformat()
            # Calculate latency in ms
            ingestion_latency_ms = round(max(0.0, (now_utc - parsed_dt).total_seconds() * 1000.0), 1)

            # Check clock drift / future / stale
            delta_sec = (parsed_dt - now_utc).total_seconds()
            if delta_sec > 300.0:  # > 5 minutes in future
                warnings.append(f"Clock drift detected: timestamp is {round(delta_sec, 1)}s in the future")
            elif delta_sec < -86400.0:  # > 24 hours old
                warnings.append("Historical/stale telemetry: timestamp is older than 24 hours")

        except Exception as e:
            warnings.append(f"Timestamp '{raw_ts}' could not be parsed strictly ({e}); using ingestion time")
            parsed_dt = now_utc
            timestamp_str = ingestion_ts

    # 3. Required: depth_md
    raw_depth = payload.get("depth_md") if payload.get("depth_md") is not None else payload.get("depth")
    if raw_depth is None:
        raw_depth = payload.get("hole_depth")
    depth_md: Optional[float] = None
    if raw_depth is None:
        errors.append("Missing required field: depth_md")
    else:
        try:
            d_val = float(raw_depth)
            if math.isnan(d_val) or math.isinf(d_val):
                errors.append("depth_md must be a finite number")
            elif d_val < 0.0:
                errors.append(f"Impossible negative depth_md: {d_val}")
            elif d_val > 12000.0:
                warnings.append(f"depth_md {d_val} exceeds typical drilling range (>12,000m)")
                depth_md = d_val
            else:
                depth_md = d_val
        except (ValueError, TypeError):
            errors.append(f"Invalid non-numeric depth_md: {raw_depth}")

    if errors:
        return False, "INVALID", errors + warnings, None

    # 4. Telemetry channels with alias support
    alias_map = {
        "rop_m_hr": ["rop_m_hr", "rop", "drill_rate", "rate_of_penetration"],
        "wob_klbf": ["wob_klbf", "wob", "weight_on_bit"],
        "rpm": ["rpm", "surf_rpm", "rotary_speed"],
        "torque_kftlb": ["torque_kftlb", "torque", "surf_torq", "trq"],
        "standpipe_pressure_psi": ["standpipe_pressure_psi", "standpipe_pressure", "spp"],
        "flow_rate_lpm": ["flow_rate_lpm", "flow_rate", "flow_in"],
        "mud_weight_ppg": ["mud_weight_ppg", "mud_weight", "mw"],
        "mud_flow_in_lpm": ["mud_flow_in_lpm", "mud_flow_in", "flow_in_lpm"],
        "mud_flow_out_lpm": ["mud_flow_out_lpm", "mud_flow_out", "flow_out_lpm"],
        "gas_units": ["gas_units", "gas", "total_gas"],
        "pump_pressure": ["pump_pressure", "pump_press"],
        "hookload": ["hookload", "hook_load", "hkld"],
        "bit_depth": ["bit_depth", "bit_depth_md"],
        "block_position": ["block_position", "block_pos"],
        "ecd": ["ecd", "equivalent_circulating_density"],
        "temperature": ["temperature", "temp_c"],
        "chlorides": ["chlorides", "cl_ppm"],
    }

    cleaned_fields: Dict[str, Optional[float]] = {}
    is_suspect = False

    for canonical_key, aliases in alias_map.items():
        val = None
        for a in aliases:
            if a in payload and payload[a] is not None:
                val = payload[a]
                break

        if val is None or val == "" or str(val).lower() in ("none", "null", "nan"):
            cleaned_fields[canonical_key] = None
            continue

        try:
            f_val = float(val)
            if math.isnan(f_val) or math.isinf(f_val):
                warnings.append(f"Non-finite value for '{canonical_key}'; set to null")
                cleaned_fields[canonical_key] = None
                continue

            if canonical_key in PHYSICAL_RANGES:
                min_v, max_v = PHYSICAL_RANGES[canonical_key]
                if f_val < min_v:
                    warnings.append(f"Field '{canonical_key}' value {f_val} below min {min_v}; clipped")
                    f_val = min_v
                    is_suspect = True
                elif f_val > max_v:
                    warnings.append(f"Field '{canonical_key}' value {f_val} exceeds max {max_v}; flagged")
                    is_suspect = True

            cleaned_fields[canonical_key] = round(f_val, 3)

        except (ValueError, TypeError):
            warnings.append(f"Non-numeric value for '{canonical_key}': '{val}'; set to null")
            cleaned_fields[canonical_key] = None

    # Determine Quality Status
    if any("older than 24 hours" in w for w in warnings):
        quality_status = "STALE"
    elif is_suspect:
        quality_status = "SUSPECT"
    elif warnings:
        quality_status = "VALID_WITH_WARNINGS"
    else:
        quality_status = "VALID"

    # Scrub raw payload if requested
    sanitized_raw = None
    if store_raw:
        sanitized_raw = {
            k: v for k, v in payload.items()
            if not any(secret_term in k.lower() for secret_term in ("pass", "secret", "token", "auth", "key"))
        }

    rec_source = payload.get("source") or source

    record = RealtimeTelemetryRecord(
        timestamp=timestamp_str,
        well_id=well_id,
        depth_md=depth_md,
        rop_m_hr=cleaned_fields.get("rop_m_hr"),
        wob_klbf=cleaned_fields.get("wob_klbf"),
        rpm=cleaned_fields.get("rpm"),
        torque_kftlb=cleaned_fields.get("torque_kftlb"),
        standpipe_pressure_psi=cleaned_fields.get("standpipe_pressure_psi"),
        flow_rate_lpm=cleaned_fields.get("flow_rate_lpm"),
        mud_weight_ppg=cleaned_fields.get("mud_weight_ppg"),
        mud_flow_in_lpm=cleaned_fields.get("mud_flow_in_lpm"),
        mud_flow_out_lpm=cleaned_fields.get("mud_flow_out_lpm"),
        gas_units=cleaned_fields.get("gas_units"),
        pump_pressure=cleaned_fields.get("pump_pressure"),
        hookload=cleaned_fields.get("hookload"),
        bit_depth=cleaned_fields.get("bit_depth"),
        block_position=cleaned_fields.get("block_position"),
        ecd=cleaned_fields.get("ecd"),
        temperature=cleaned_fields.get("temperature"),
        chlorides=cleaned_fields.get("chlorides"),
        source=str(rec_source),
        quality_status=quality_status,
        source_timestamp=source_timestamp_str,
        ingestion_timestamp=ingestion_ts,
        ingestion_latency_ms=ingestion_latency_ms,
        raw_payload=sanitized_raw,
    )

    return True, quality_status, warnings, record
