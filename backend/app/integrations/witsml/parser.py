"""
NWIS Phase 8 — WITSML 1.3.1.1 / 1.4.1.1 XML Parser & Normalizer
================================================================
Parses Energistics WITSML XML log responses into normalized telemetry dictionaries.
Supports unit conversions and curve mnemonic aliases.
"""

from __future__ import annotations
import logging
import re
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET

from .models import WitsmlLog, WitsmlLogCurveInfo, WitsmlLogData

logger = logging.getLogger("nwis.integrations.witsml.parser")

# Standard Mnemonic to Canonical Field map
WITSML_MNEMONIC_MAP = {
    "DEPT": "depth_md",
    "MD": "depth_md",
    "DEPTH": "depth_md",
    "HOLE_DEPTH": "depth_md",
    "ROP": "rop_m_hr",
    "ROPA": "rop_m_hr",
    "ROP_AVG": "rop_m_hr",
    "WOB": "wob_klbf",
    "WOBA": "wob_klbf",
    "SWOB": "wob_klbf",
    "RPM": "rpm",
    "CRPM": "rpm",
    "SR_RPM": "rpm",
    "TORQ": "torque_kftlb",
    "STOR": "torque_kftlb",
    "TRQ": "torque_kftlb",
    "SPP": "standpipe_pressure_psi",
    "STPP": "standpipe_pressure_psi",
    "PUMP_PRESS": "standpipe_pressure_psi",
    "FLOWIN": "mud_flow_in_lpm",
    "FLOW_IN": "mud_flow_in_lpm",
    "MFI": "mud_flow_in_lpm",
    "FLOWOUT": "mud_flow_out_lpm",
    "FLOW_OUT": "mud_flow_out_lpm",
    "MFO": "mud_flow_out_lpm",
    "GAS": "gas_units",
    "TGAS": "gas_units",
    "TOT_GAS": "gas_units",
    "MW": "mud_weight_ppg",
    "MWIN": "mud_weight_ppg",
    "MUD_WT": "mud_weight_ppg",
    "HKLD": "hookload",
    "HKLA": "hookload",
    "HOOKLOAD": "hookload",
    "TIME": "timestamp",
    "DATE_TIME": "timestamp",
}

# Unit conversion factors to NWIS canonical units
UNIT_CONVERSIONS = {
    ("depth_md", "ft"): 0.3048,
    ("rop_m_hr", "ft/h"): 0.3048,
    ("rop_m_hr", "ft/hr"): 0.3048,
    ("wob_klbf", "kn"): 0.224809,
    ("torque_kftlb", "kn.m"): 0.737562,
    ("torque_kftlb", "knm"): 0.737562,
    ("standpipe_pressure_psi", "kpa"): 0.145038,
    ("standpipe_pressure_psi", "bar"): 14.5038,
    ("mud_flow_in_lpm", "gpm"): 3.78541,
    ("mud_flow_out_lpm", "gpm"): 3.78541,
    ("mud_weight_ppg", "sg"): 8.3454,
    ("hookload", "kn"): 0.224809,
}


def _strip_ns(tag: str) -> str:
    """Removes XML namespace prefix from element tag."""
    return re.sub(r"\{.*?\}", "", tag)


class WitsmlParser:
    """
    Parses WITSML 1.3.1.1 and 1.4.1.1 log XML documents into normalized telemetry records.
    """

    @classmethod
    def parse_log_xml(cls, xml_text: str, default_well_id: str = "WELL-000050") -> List[Dict[str, Any]]:
        """
        Parses a <logs> or <log> XML document into a list of normalized row dictionaries.
        """
        if not xml_text or not xml_text.strip():
            return []

        try:
            root = ET.fromstring(xml_text.strip())
        except ET.ParseError as e:
            logger.error(f"Malformed WITSML XML payload: {e}")
            raise ValueError(f"Invalid WITSML XML: {e}")

        # Find log elements
        logs: List[ET.Element] = []
        clean_tag = _strip_ns(root.tag).lower()
        if clean_tag == "log":
            logs.append(root)
        else:
            for child in root.iter():
                if _strip_ns(child.tag).lower() == "log":
                    logs.append(child)

        records: List[Dict[str, Any]] = []

        for log_elem in logs:
            well_id = log_elem.attrib.get("uidWell") or default_well_id

            # 1. Parse logCurveInfo mnemonics and units
            mnemonics: List[str] = []
            units: List[str] = []

            for elem in log_elem:
                tag = _strip_ns(elem.tag).lower()
                if tag == "logcurveinfo":
                    mnem = ""
                    unit = ""
                    for sub in elem:
                        sub_tag = _strip_ns(sub.tag).lower()
                        if sub_tag == "mnemonic" and sub.text:
                            mnem = sub.text.strip().upper()
                        elif sub_tag == "unit" and sub.text:
                            unit = sub.text.strip().lower()
                    if mnem:
                        mnemonics.append(mnem)
                        units.append(unit)

            # 2. Parse logData
            for elem in log_elem:
                tag = _strip_ns(elem.tag).lower()
                if tag == "logdata":
                    # Check for mnemonicList child (WITSML 1.4.1.1)
                    for sub in elem:
                        sub_tag = _strip_ns(sub.tag).lower()
                        if sub_tag == "mnemoniclist" and sub.text and not mnemonics:
                            mnemonics = [m.strip().upper() for m in sub.text.split(",") if m.strip()]
                        elif sub_tag == "unitlist" and sub.text and not units:
                            units = [u.strip().lower() for u in sub.text.split(",") if u.strip()]

                    # Parse data rows
                    for sub in elem:
                        sub_tag = _strip_ns(sub.tag).lower()
                        if sub_tag == "data" and sub.text:
                            data_lines = [line.strip() for line in sub.text.strip().split("\n") if line.strip()]
                            for line in data_lines:
                                row_vals = [v.strip() for v in line.split(",")]
                                rec = cls._map_row_to_record(row_vals, mnemonics, units, well_id)
                                if rec and rec.get("depth_md") is not None:
                                    records.append(rec)

        return records

    @classmethod
    def _map_row_to_record(
        cls,
        vals: List[str],
        mnemonics: List[str],
        units: List[str],
        well_id: str,
    ) -> Optional[Dict[str, Any]]:
        record: Dict[str, Any] = {
            "well_id": well_id,
            "source": "WITSML",
        }

        for i, val_str in enumerate(vals):
            if i >= len(mnemonics):
                break
            if val_str in ("", "null", "NaN", "None", "-999.25", "-9999"):
                continue

            mnem = mnemonics[i]
            canonical_field = WITSML_MNEMONIC_MAP.get(mnem)
            if not canonical_field:
                continue

            unit = units[i] if i < len(units) else ""

            if canonical_field == "timestamp":
                record["timestamp"] = val_str
            else:
                try:
                    f_val = float(val_str)
                    # Apply unit conversion if needed
                    conv_key = (canonical_field, unit)
                    if conv_key in UNIT_CONVERSIONS:
                        f_val = f_val * UNIT_CONVERSIONS[conv_key]
                    record[canonical_field] = round(f_val, 3)
                except ValueError:
                    pass

        return record if len(record) > 2 else None
