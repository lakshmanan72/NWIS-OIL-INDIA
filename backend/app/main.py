import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .api.wells import router as wells_router
from .api.dashboard import router as dashboard_router
from .api.prediction import router as prediction_router
from .api.documents import router as documents_router
from .api.realtime import router as realtime_router, ws_router
from .api.auth import router as auth_router
from .api.audit import router as audit_router
from .api.health import router as health_router
from .api.integrations import router as integrations_router, live_router
from .api.metrics import router as metrics_router
from .api.wcr import router as wcr_router
from .core.observability import ObservabilityMiddleware

logger = logging.getLogger("nwis.server")

app = FastAPI(
    title="NWIS Well Map API",
    description="Nearby Wells Intelligence System - Unified Data Layer, Offset Intelligence & Production Data Platform",
    version="8.0.0",
)

# Enable CORS for frontend Vite development (allow standard dev origins)
ALLOWED_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Phase 9 — Request Correlation & Observability Middleware
app.add_middleware(ObservabilityMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        f"Unhandled server error on {request.method} {request.url.path}: {exc}",
        exc_info=True,
        extra={"request_id": req_id, "event": "UNHANDLED_EXCEPTION"},
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error occurred. Diagnostic reference generated.",
            "request_id": req_id,
            "advisory": "NWIS is an advisory decision-support system.",
        },
        headers={"X-Request-ID": req_id},
    )


app.include_router(health_router)
app.include_router(auth_router)
app.include_router(audit_router)
app.include_router(metrics_router)
app.include_router(wells_router)
app.include_router(dashboard_router)
app.include_router(prediction_router)
app.include_router(documents_router)
app.include_router(wcr_router)
app.include_router(realtime_router)
app.include_router(ws_router)
app.include_router(integrations_router)
app.include_router(live_router)


@app.get("/")
def root():
    return {
        "system": "NWIS - Nearby Wells Intelligence System",
        "version": "8.0.0",
        "description": "Unified Data Layer, Offset Intelligence, Real-Time eRTMAC & Production Data Platform",
        "endpoints": {
            "health": "/api/health",
            "ready": "/api/ready",
            "metrics": "/api/metrics",
            "integrations_status": "/api/integrations/status",
            "live_telemetry_latest": "/api/live/{well_id}/telemetry/latest",
            "live_telemetry_history": "/api/live/{well_id}/telemetry/history",
            "auth_login": "/api/auth/login",
            "auth_me": "/api/auth/me",
            "audit_trail": "/api/audit",
            "realtime_status": "/api/realtime/status",
            "realtime_latest": "/api/realtime/latest/{well_id}",
            "realtime_replay_start": "/api/realtime/replay/start",
            "realtime_replay_stop": "/api/realtime/replay/stop",
            "realtime_stream": "/api/realtime/stream/{well_id}",
            "realtime_features": "/api/realtime/features/{well_id}",
            "realtime_risks": "/api/realtime/risks/{well_id}",
            "realtime_alerts": "/api/realtime/alerts",
            "realtime_context": "/api/realtime/context/{well_id}",
            "realtime_ws": "/ws/realtime/{well_id}",
            "document_upload": "/api/documents/upload",
            "documents_registry": "/api/documents",
            "document_search": "/api/documents/search",
            "rag_intelligence_query": "/api/intelligence/query",
            "risk_prediction": "/api/prediction/risk",
            "benchmark_comparison": "/api/prediction/benchmark",
            "selection_report": "/api/prediction/selection-report",
            "map_markers": "/api/wells/map-markers",
            "canonical_wells": "/api/wells",
            "nearby_wells": "/api/wells/{well_id}/nearby",
            "offset_intelligence": "/api/wells/{well_id}/offset-intelligence",
            "geology": "/api/wells/{well_id}/geology",
            "formations": "/api/wells/{well_id}/formations",
            "drilling": "/api/wells/{well_id}/drilling",
            "mud_logging": "/api/wells/{well_id}/mud-logging",
            "events": "/api/wells/{well_id}/events",
            "completion": "/api/wells/{well_id}/completion",
            "documents": "/api/wells/{well_id}/documents",
            "risks": "/api/wells/{well_id}/risks",
            "dashboard_stats": "/api/dashboard/stats",
            "docs": "/docs",
        },
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "system": "NWIS - Nearby Wells Intelligence System",
        "advisory": "NWIS is an advisory decision-support system. Autonomous rig control is prohibited.",
        "version": "8.0.0",
    }
