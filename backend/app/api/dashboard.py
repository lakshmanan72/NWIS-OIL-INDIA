from fastapi import APIRouter
from ..models.dashboard import DashboardStatsResponse
from ..services.dashboard_service import dashboard_service

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats() -> DashboardStatsResponse:
    """
    Returns actual aggregated KPI statistics across all 11 NWIS datasets.
    """
    return dashboard_service.get_dashboard_stats()
