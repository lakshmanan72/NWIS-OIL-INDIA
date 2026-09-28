"""
NWIS Phase 8 — eRTMAC Integration Configuration
===============================================
Parses eRTMAC credentials and parameters from environment variables.
Scans and redacts sensitive credentials.
"""

from __future__ import annotations
import os
from typing import Any, Dict


def get_ertmac_config() -> Dict[str, Any]:
    enabled = os.getenv("ERTMAC_ENABLED", "false").lower() in ("true", "1", "yes")
    base_url = os.getenv("ERTMAC_BASE_URL", "").strip()
    username = os.getenv("ERTMAC_USERNAME", "").strip()
    password = os.getenv("ERTMAC_PASSWORD", "").strip()
    api_key = os.getenv("ERTMAC_API_KEY", "").strip()
    well_id = os.getenv("ERTMAC_WELL_ID", "").strip()
    timeout_sec = float(os.getenv("INTEGRATION_TIMEOUT_SECONDS", "10.0"))
    max_retries = int(os.getenv("INTEGRATION_RETRY_MAX", "5"))

    return {
        "enabled": enabled,
        "base_url": base_url,
        "username": username,
        "password": password,
        "api_key": api_key,
        "well_id": well_id,
        "timeout_seconds": timeout_sec,
        "max_retries": max_retries,
    }


def get_safe_ertmac_config() -> Dict[str, Any]:
    """Returns configuration with sensitive secrets masked for UI and diagnostics."""
    cfg = get_ertmac_config()
    return {
        "enabled": cfg["enabled"],
        "base_url": cfg["base_url"] or None,
        "username": cfg["username"] or None,
        "has_password": bool(cfg["password"]),
        "has_api_key": bool(cfg["api_key"]),
        "well_id": cfg["well_id"] or None,
        "timeout_seconds": cfg["timeout_seconds"],
        "max_retries": cfg["max_retries"],
        "status": "CONFIGURED" if (cfg["enabled"] and cfg["base_url"]) else ("DISABLED" if not cfg["enabled"] else "INCOMPLETE_CREDENTIALS"),
    }
