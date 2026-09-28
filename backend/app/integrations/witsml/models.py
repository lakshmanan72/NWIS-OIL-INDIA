"""
NWIS Phase 8 — WITSML 1.3.1.1 / 1.4.1.1 Domain Models
======================================================
Represents standard WITSML well, wellbore, log, and curve objects.
"""

from __future__ import annotations
from dataclasses import asdict, dataclass, field as dc_field
from typing import Any, Dict, List, Optional


@dataclass
class WitsmlLogCurveInfo:
    mnemonic: str
    unit: Optional[str] = None
    curve_description: Optional[str] = None
    type_log_data: Optional[str] = "double"
    canonical_field: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WitsmlLog:
    uid: str
    name: str
    well_uid: str
    wellbore_uid: str
    index_type: str = "measured depth"  # 'measured depth' or 'date-time'
    index_curve: str = "DEPT"
    start_index: Optional[str] = None
    end_index: Optional[str] = None
    curves: List[WitsmlLogCurveInfo] = dc_field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WitsmlLogData:
    log_uid: str
    mnemonics: List[str]
    units: List[str]
    rows: List[List[str]] = dc_field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WitsmlWellbore:
    uid: str
    name: str
    well_uid: str
    status_wellbore: Optional[str] = "active"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WitsmlWell:
    uid: str
    name: str
    status: Optional[str] = "drilling"
    field: Optional[str] = None
    country: Optional[str] = "India"
    operator: Optional[str] = None
    wellbores: List[WitsmlWellbore] = dc_field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
