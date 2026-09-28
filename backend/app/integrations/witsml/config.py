"""
NWIS Phase 8 — WITSML Integration Configuration
===============================================
Parses WITSML 1.3.1.1/1.4.1.1 connection settings from environment.
Redacts passwords for telemetry health diagnostics.
"""

from __future__ import annotations
import os
from typing import Any, Dict


def get_witsml_config() -> Dict[str, Any]:
    enabled = os.getenv("WITSML_ENABLED", "false").lower() in ("true", "1", "yes")
    url = os.getenv("WITSML_URL", "").strip()
    username = os.getenv("WITSML_USERNAME", "").strip()
    password = os.getenv("WITSML_PASSWORD", "").strip()
    well_id = os.getenv("WITSML_WELL_ID", "").strip()
    wellbore_id = os.getenv("WITSML_WELLBORE_ID", "").strip()
    timeout_sec = float(os.getenv("INTEGRATION_TIMEOUT_SECONDS", "10.0"))
    max_retries = int(os.getenv("INTEGRATION_RETRY_MAX", "5"))

    return {
        "enabled": enabled,
        "url": url,
        "username": username,
        "password": password,
        "well_id": well_id,
        "wellbore_id": wellbore_id,
        "timeout_seconds": timeout_sec,
        "max_retries": max_retries,
    }


def get_safe_witsml_config() -> Dict[str, Any]:
    cfg = get_witsml_config()
    return {
        "enabled": cfg["enabled"],
        "url": cfg["url"] or None,
        "username": cfg["username"] or None,
        "has_password": bool(cfg["password"]),
        "well_id": cfg["well_id"] or None,
        "wellbore_id": cfg["wellbore_id"] or None,
        "timeout_seconds": cfg["timeout_seconds"],
        "max_retries": cfg["max_retries"],
        "status": "CONFIGURED" if (cfg["enabled"] and cfg["url"]) else ("DISABLED" if not cfg["enabled"] else "INCOMPLETE_CREDENTIALS"),
    }
