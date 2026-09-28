"""
NWIS Phase 6 — Real-Time Operations & Alerting API Endpoints
============================================================
Exposes REST and WebSocket endpoints for streaming telemetry,
data freshness, rolling features, live risk synthesis, and alert lifecycle.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from ..realtime.service import realtime_service
from ..realtime.schema import validate_telemetry_payload
from ..security.auth import require_role, ROLE_ADMIN, ROLE_DRILLING_ENGINEER, UserResponse

logger = logging.getLogger("nwis.api.realtime")

router = APIRouter(prefix="/api/realtime", tags=["Real-Time eRTMAC & Live Risk Operations"])


class ReplayStartRequest(BaseModel):
    well_id: str = Field(default="WELL-000050", description="Canonical well ID for replay")
    interval_ms: int = Field(default=1000, description="Replay interval cadence in milliseconds")


class IngestTelemetryRequest(BaseModel):
    timestamp: Optional[str] = None
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


class InjectAnomalyRequest(BaseModel):
    anomaly_type: str = Field(default="torque_spike", description="Type of anomaly (torque_spike, pressure_surge, flow_imbalance, rop_drop)")


class AlertActionRequest(BaseModel):
    reviewer: str = Field(default="Drilling Operations Engineer", description="Engineer identity")
    note: Optional[str] = Field(default=None, description="Optional engineering review comment")


# -------------------------------------------------------------
# 1. System Health & Status
# -------------------------------------------------------------
@router.get("/status")
def get_realtime_status():
    """Returns provider status, active well freshness, and alert count."""
    return realtime_service.get_status()


# -------------------------------------------------------------
# 2. Latest Telemetry & State
# -------------------------------------------------------------
@router.get("/latest/{well_id}")
def get_latest_telemetry(well_id: str):
    """Fetches the latest real-time parameters and freshness state for a well."""
    return realtime_service.get_latest_telemetry(well_id)


# -------------------------------------------------------------
# 3. Demo Replay Control
# -------------------------------------------------------------
@router.post("/replay/start")
def start_demo_replay(req: ReplayStartRequest):
    """Activates deterministic real-time DEMO REPLAY mode."""
    return realtime_service.start_replay(well_id=req.well_id, interval_ms=req.interval_ms)


@router.post("/replay/stop")
def stop_demo_replay():
    """Stops the real-time demo replay stream."""
    return realtime_service.stop_replay()


@router.post("/inject-anomaly")
def inject_anomaly(req: InjectAnomalyRequest):
    """Injects a demonstration anomaly into the real-time stream."""
    return realtime_service.inject_anomaly(req.anomaly_type)


# -------------------------------------------------------------
# 4. Ingest External Telemetry
# -------------------------------------------------------------
@router.post("/ingest")
def ingest_telemetry_point(payload: IngestTelemetryRequest):
    """Ingests and validates an untrusted incoming live telemetry point."""
    res = realtime_service.process_telemetry_point(payload.dict(), provider_mode="LIVE FIELD DATA")
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res)
    return res


# -------------------------------------------------------------
# 5. Polling Stream (Fallback for Non-WebSocket Clients)
# -------------------------------------------------------------
@router.get("/stream/{well_id}")
def poll_stream_slice(well_id: str):
    """Advances replay / polls latest telemetry slice with full signal evaluation."""
    return realtime_service.poll_or_step(well_id)


# -------------------------------------------------------------
# 6. Streaming Features
# -------------------------------------------------------------
@router.get("/features/{well_id}")
def get_streaming_features(well_id: str):
    """Returns computed rolling features (means, max, rate-of-change, flow imbalance)."""
    return realtime_service.get_features(well_id)


# -------------------------------------------------------------
# 7. Live Risk Inference & Signals
# -------------------------------------------------------------
@router.get("/risks/{well_id}")
def get_live_risks(well_id: str):
    """Fetches synthesized multi-source signals and Phase 3.1 Model Risk Indicators."""
    return realtime_service.get_live_risks(well_id)


# -------------------------------------------------------------
# 8. Live Evidence Packet & Historical Context
# -------------------------------------------------------------
@router.get("/context/{well_id}")
def get_live_context(well_id: str):
    """Fetches the complete LiveEvidencePacket correlating live observations with historical EVID records."""
    return realtime_service.get_live_context(well_id)


# -------------------------------------------------------------
# 9. Alert Engine Endpoints
# -------------------------------------------------------------
@router.get("/alerts")
def get_alerts(
    well_id: Optional[str] = Query(None, description="Filter by well ID"),
    status: Optional[str] = Query(None, description="Filter by status (ACTIVE, ACKNOWLEDGED, CLOSED)"),
):
    """Lists drilling alerts matching criteria."""
    return {"alerts": realtime_service.get_alerts(well_id=well_id, status=status)}


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: str,
    req: AlertActionRequest,
    user: UserResponse = Depends(require_role(ROLE_ADMIN, ROLE_DRILLING_ENGINEER)),
):
    """Engineer acknowledges an active alert."""
    try:
        reviewer_name = req.reviewer or user.full_name or user.username
        return realtime_service.acknowledge_alert(
            alert_id=alert_id,
            reviewer=reviewer_name,
            note=req.note,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")


@router.post("/alerts/{alert_id}/close")
def close_alert(
    alert_id: str,
    req: AlertActionRequest,
    user: UserResponse = Depends(require_role(ROLE_ADMIN, ROLE_DRILLING_ENGINEER)),
):
    """Engineer formally closes an alert with review notes."""
    try:
        reviewer_name = req.reviewer or user.full_name or user.username
        return realtime_service.close_alert(
            alert_id=alert_id,
            reviewer=reviewer_name,
            note=req.note,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")


# -------------------------------------------------------------
# 10. WebSocket Endpoint
# -------------------------------------------------------------
ws_router = APIRouter(tags=["Real-Time WebSocket"])


@ws_router.websocket("/ws/realtime/{well_id}")
async def websocket_realtime_stream(websocket: WebSocket, well_id: str):
    """
    Bi-directional streaming WebSocket for real-time telemetry, risks, and alerts.
    Clients receive updates continuously and can send control commands.
    """
    await websocket.accept()
    logger.info(f"WebSocket client connected for {well_id}")

    try:
        while True:
            # Poll or step the provider
            step_result = realtime_service.poll_or_step(well_id)

            # Send telemetry message
            msg = {
                "type": "telemetry",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "well_id": well_id.upper(),
                "data": step_result,
            }
            await websocket.send_text(json.dumps(msg))

            # Sleep between pushes
            await asyncio.sleep(1.0)

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected for {well_id}")
    except Exception as e:
        logger.warning(f"WebSocket stream error for {well_id}: {e}")
        try:
            await websocket.close()
        except Exception:
            pass
