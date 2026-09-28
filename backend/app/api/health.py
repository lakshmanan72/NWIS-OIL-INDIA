from typing import Dict, Any
from fastapi import APIRouter
from ..db.config import db_config
from ..db.session import check_database_connection
from ..repositories.factory import get_well_repository

router = APIRouter(prefix="/api", tags=["System Health & Readiness"])


@router.get("/health")
def api_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "system": "NWIS - Nearby Wells Intelligence System",
        "advisory": "NWIS is an advisory decision-support system. Autonomous rig control is prohibited.",
        "version": "8.0.0",
    }


@router.get("/ready")
def api_ready() -> Dict[str, Any]:
    db_status = check_database_connection()
    repo = get_well_repository()
    total_wells, _ = repo.get_all_wells(offset=0, limit=1)

    # Integrations Subsystem Status
    from ..integrations.ertmac import ertmac_adapter
    from ..integrations.witsml import witsml_adapter
    from ..integrations.wits0 import wits0_adapter
    from ..realtime.providers import demo_replay_provider

    integrations_summary = {
        "subsystem": "ready",
        "ertmac": ertmac_adapter.health()["status"],
        "witsml": witsml_adapter.health()["status"],
        "wits0": wits0_adapter.health()["status"],
        "demo_replay": "CONNECTED" if demo_replay_provider.is_connected else "STANDBY",
    }

    return {
        "status": "ready",
        "database": db_status.get("dialect", "none"),
        "database_connected": db_status.get("connected", False),
        "postgis": db_status.get("postgis_active", False),
        "postgis_version": db_status.get("postgis_version"),
        "backend_mode": db_config.data_backend,
        "telemetry_storage": db_config.telemetry_storage,
        "alert_storage": db_config.alert_storage,
        "canonical_wells_available": total_wells > 0,
        "total_canonical_wells": total_wells,
        "integrations": integrations_summary,
    }
