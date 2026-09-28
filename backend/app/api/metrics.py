"""
NWIS Phase 9 — Metrics & Observability Endpoint
================================================
Exposes lightweight operational metrics for monitoring, health dashboards,
and Prometheus scrapers.
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Header, Query, Response
from ..core.observability import metrics_collector

router = APIRouter(prefix="/api", tags=["Observability & Metrics"])


@router.get("/metrics")
def get_system_metrics(
    format: Optional[str] = Query(None, description="Set to 'prometheus' for Prometheus exposition format"),
    accept: Optional[str] = Header(None),
):
    """
    Returns real-time operational metrics for NWIS.
    Default: JSON payload.
    Prometheus format: Set ?format=prometheus or Accept: text/plain.
    """
    from typing import Optional

    if (format and format.lower() == "prometheus") or (accept and "text/plain" in accept):
        prom_text = metrics_collector.format_prometheus()
        return Response(content=prom_text, media_type="text/plain; version=0.0.4; charset=utf-8")

    return metrics_collector.get_metrics_snapshot()
