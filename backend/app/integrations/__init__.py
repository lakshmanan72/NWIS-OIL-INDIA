"""
NWIS Phase 8 — External Integrations & Telemetry Adapters
==========================================================
Includes:
- WellIdentityResolver (Quarantine & Canonical mapping)
- eRTMAC REST/JSON Adapter
- WITSML 1.3.1.1/1.4.1.1 XML Store Adapter
- WITS0 Level 0 Parser
- Ingestion Queue & Backpressure Pipeline
"""

from .identity_resolver import well_identity_resolver, WellIdentityResolver

__all__ = [
    "well_identity_resolver",
    "WellIdentityResolver",
]
