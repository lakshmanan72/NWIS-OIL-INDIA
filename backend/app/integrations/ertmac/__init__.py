"""
NWIS Phase 8 — eRTMAC Integration Package
=========================================
"""

from .config import get_ertmac_config, get_safe_ertmac_config
from .health import IntegrationHealth, IntegrationHealthTracker
from .schema import ERTMAC_CHANNEL_MAP, normalize_ertmac_payload
from .client import ERTMACClient
from .adapter import ERTMACAdapter, ertmac_adapter

__all__ = [
    "get_ertmac_config",
    "get_safe_ertmac_config",
    "IntegrationHealth",
    "IntegrationHealthTracker",
    "ERTMAC_CHANNEL_MAP",
    "normalize_ertmac_payload",
    "ERTMACClient",
    "ERTMACAdapter",
    "ertmac_adapter",
]
