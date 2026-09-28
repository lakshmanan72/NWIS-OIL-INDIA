"""
NWIS Phase 8 — Integration Management & Telemetry Stream APIs
=============================================================
REST endpoints for monitoring integration adapters, triggering connect/disconnect,
viewing stream metrics, resolving unmapped well quarantines, and telemetry history.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from ..integrations.ertmac import ertmac_adapter, get_safe_ertmac_config
from ..integrations.identity_resolver import well_identity_resolver
from ..integrations.streaming_pipeline import streaming_pipeline
from ..integrations.wits0 import wits0_adapter
from ..integrations.witsml import witsml_adapter, get_safe_witsml_config
from ..realtime.live_state import live_well_state
from ..realtime.providers import demo_replay_provider
from ..realtime.service import realtime_service
from ..repositories.factory import get_telemetry_repository
from ..security.audit import log_audit_event
from ..security.auth import (
    ROLE_ADMIN,
    ROLE_DRILLING_ENGINEER,
    ROLE_GEOLOGIST,
    ROLE_VIEWER,
    UserResponse,
    get_current_user,
    require_role,
)

logger = logging.getLogger("nwis.api.integrations")

router = APIRouter(prefix="/api/integrations", tags=["Integration Adapters & Streaming"])
live_router = APIRouter(prefix="/api/live", tags=["Live Telemetry & Engineering Intelligence"])


class MappingRequest(BaseModel):
    external_source: str = Field(..., description="Provider source name e.g. eRTMAC, WITSML, WITS0")
    external_well_id: str = Field(..., description="External vendor/rig well identifier")
    canonical_well_id: str = Field(..., description="Canonical NWIS well ID e.g. WELL-000050")
    external_wellbore_id: Optional[str] = Field(None, description="Optional wellbore identifier")


class IngestPacketRequest(BaseModel):
    provider_source: str = Field(default="eRTMAC", description="Provider source identifier")
    payload: Dict[str, Any] = Field(..., description="Raw or normalized telemetry dictionary")


# -------------------------------------------------------------
# 1. Overall Integration Status & Stream Metrics
# -------------------------------------------------------------
@router.get("/status")
def get_integrations_status():
    """
    Returns consolidated health status for all upstream adapters,
    active stream pipeline metrics, and quarantine counts.
    """
    ertmac_h = ertmac_adapter.health()
    witsml_h = witsml_adapter.health()
    wits0_h = wits0_adapter.health()
    demo_h = demo_replay_provider.health()
    metrics = streaming_pipeline.get_metrics()
    quarantine_list = well_identity_resolver.get_quarantined_wells()

    return {
        "status": "OPERATIONAL",
        "providers": {
            "ertmac": ertmac_h,
            "witsml": witsml_h,
            "wits0": wits0_h,
            "demo_replay": demo_h,
        },
        "pipeline_metrics": metrics,
        "quarantined_unmatched_count": len(quarantine_list),
        "advisory": "NWIS is an advisory decision-support system. Autonomous rig control is prohibited.",
    }


# -------------------------------------------------------------
# 2. Individual Provider Health
# -------------------------------------------------------------
@router.get("/{provider}/health")
def get_provider_health(provider: str):
    """Fetches in-depth connection diagnostics and safe configs for a given provider."""
    p_lower = provider.strip().lower()

    if p_lower in ("ertmac", "oil-ertmac"):
        return ertmac_adapter.health()
    elif p_lower in ("witsml", "witsml1411"):
        return witsml_adapter.health()
    elif p_lower in ("wits0", "wits"):
        return wits0_adapter.health()
    elif p_lower in ("demo", "demo_replay"):
        return demo_replay_provider.health()
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown integration provider '{provider}'. Supported: ertmac, witsml, wits0, demo_replay",
        )


# -------------------------------------------------------------
# 3. Provider Connect & Disconnect (RBAC Protected)
# -------------------------------------------------------------
@router.post("/{provider}/connect")
def connect_provider(
    provider: str,
    request: Request,
    user: UserResponse = Depends(require_role(ROLE_ADMIN, ROLE_DRILLING_ENGINEER)),
):
    """Initializes upstream connection to an external provider."""
    p_lower = provider.strip().lower()
    connected = False
    details = {}

    if p_lower in ("ertmac", "oil-ertmac"):
        connected = ertmac_adapter.connect()
        details = ertmac_adapter.health()
    elif p_lower in ("witsml", "witsml1411"):
        connected = witsml_adapter.connect()
        details = witsml_adapter.health()
    elif p_lower in ("wits0", "wits"):
        connected = wits0_adapter.connect()
        details = wits0_adapter.health()
    elif p_lower in ("demo", "demo_replay"):
        connected = demo_replay_provider.connect()
        details = demo_replay_provider.health()
    else:
        raise HTTPException(status_code=404, detail=f"Provider '{provider}' not recognized")

    client_ip = request.client.host if request.client else None
    log_audit_event(
        username=user.username,
        role=user.role,
        action="INTEGRATION_CONNECT",
        resource_type="provider",
        resource_id=provider,
        reason=f"Operator requested connect for {provider}",
        ip_address=client_ip,
        new_value={"connected": connected, "status": details.get("status")},
    )

    return {
        "provider": provider,
        "connected": connected,
        "details": details,
        "initiated_by": user.username,
    }


@router.post("/{provider}/disconnect")
def disconnect_provider(
    provider: str,
    request: Request,
    user: UserResponse = Depends(require_role(ROLE_ADMIN, ROLE_DRILLING_ENGINEER)),
):
    """Disconnects upstream stream from an external provider."""
    p_lower = provider.strip().lower()
    details = {}

    if p_lower in ("ertmac", "oil-ertmac"):
        ertmac_adapter.disconnect()
        details = ertmac_adapter.health()
    elif p_lower in ("witsml", "witsml1411"):
        witsml_adapter.disconnect()
        details = witsml_adapter.health()
    elif p_lower in ("wits0", "wits"):
        wits0_adapter.disconnect()
        details = wits0_adapter.health()
    elif p_lower in ("demo", "demo_replay"):
        demo_replay_provider.disconnect()
        details = demo_replay_provider.health()
    else:
        raise HTTPException(status_code=404, detail=f"Provider '{provider}' not recognized")

    client_ip = request.client.host if request.client else None
    log_audit_event(
        username=user.username,
        role=user.role,
        action="INTEGRATION_DISCONNECT",
        resource_type="provider",
        resource_id=provider,
        reason=f"Operator requested disconnect for {provider}",
        ip_address=client_ip,
        new_value={"connected": False, "status": details.get("status")},
    )

    return {
        "provider": provider,
        "connected": False,
        "details": details,
        "disconnected_by": user.username,
    }


# -------------------------------------------------------------
# 4. Identity Resolver Quarantine & Mappings
# -------------------------------------------------------------
@router.get("/quarantine")
def list_quarantined_wells():
    """Lists unmapped upstream well events quarantined from canonical attachment."""
    return {"quarantined_wells": well_identity_resolver.get_quarantined_wells()}


@router.get("/mappings")
def list_identity_mappings():
    """Lists current external-to-canonical well identity mappings."""
    return {"mappings": well_identity_resolver.get_mappings()}


@router.post("/mappings")
def register_identity_mapping(
    req: MappingRequest,
    request: Request,
    user: UserResponse = Depends(require_role(ROLE_ADMIN, ROLE_DRILLING_ENGINEER)),
):
    """Maps an external vendor well ID to a canonical NWIS well."""
    res = well_identity_resolver.register_mapping(
        external_source=req.external_source,
        external_well_id=req.external_well_id,
        canonical_well_id=req.canonical_well_id,
        external_wellbore_id=req.external_wellbore_id,
    )

    client_ip = request.client.host if request.client else None
    log_audit_event(
        username=user.username,
        role=user.role,
        action="WELL_MAPPING_UPDATED",
        resource_type="well_identity_mapping",
        resource_id=res.get("key"),
        well_id=req.canonical_well_id,
        reason=f"Mapped {req.external_source}:{req.external_well_id} -> {req.canonical_well_id}",
        ip_address=client_ip,
        new_value=res,
    )

    return res


# -------------------------------------------------------------
# 5. Pipeline Ingest Gateway (RBAC Protected)
# -------------------------------------------------------------
@router.post("/ingest")
def pipeline_ingest(
    req: IngestPacketRequest,
    user: UserResponse = Depends(require_role(ROLE_ADMIN, ROLE_DRILLING_ENGINEER)),
):
    """Processes a raw telemetry packet through the bounded streaming pipeline."""
    res = streaming_pipeline.ingest(
        raw_payload=req.payload,
        provider_source=req.provider_source,
    )
    if not res.get("success") and res.get("status") in ("INVALID", "UNMATCHED_WELL"):
        raise HTTPException(status_code=400, detail=res)
    return res


# -------------------------------------------------------------
# 6. Live Telemetry Latest & History Endpoints (/api/live)
# -------------------------------------------------------------
@live_router.get("/{well_id}/telemetry/latest")
def get_live_telemetry_latest(well_id: str):
    """Returns the latest authoritative telemetry point with data quality and source transparency."""
    repo = get_telemetry_repository()
    latest_db = repo.get_latest_telemetry(well_id)
    state_snap = live_well_state.get_state_snapshot()
    cur_rec = live_well_state.latest_record

    rec_data = cur_rec.to_dict() if cur_rec else latest_db

    return {
        "well_id": well_id.upper(),
        "live_state": state_snap,
        "telemetry": rec_data,
        "source_transparency": {
            "source": rec_data.get("source", "DEMO_REPLAY") if rec_data else "UNKNOWN",
            "quality_status": rec_data.get("quality_status", "VALID") if rec_data else "UNKNOWN",
            "timestamp": rec_data.get("timestamp") if rec_data else None,
            "source_timestamp": rec_data.get("source_timestamp") if rec_data else None,
            "ingestion_timestamp": rec_data.get("ingestion_timestamp") if rec_data else None,
            "ingestion_latency_ms": rec_data.get("ingestion_latency_ms") if rec_data else None,
        } if rec_data else None,
    }


@live_router.get("/{well_id}/telemetry/history")
def get_live_telemetry_history(
    well_id: str,
    limit: int = Query(50, ge=1, le=500, description="Max history points"),
):
    """Retrieves recent depth-indexed telemetry history."""
    repo = get_telemetry_repository()
    history = repo.get_telemetry_range(well_id=well_id, limit=limit)
    if not history and live_well_state.telemetry_history:
        # Fallback to in-memory history
        history = [r.to_dict() for r in list(live_well_state.telemetry_history)[-limit:]]

    return {
        "well_id": well_id.upper(),
        "count": len(history),
        "history": history,
    }
