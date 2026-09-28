from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from .historical_event import HistoricalDrillingEvent


class DashboardStatsResponse(BaseModel):
    total_wells: int = 15108
    wells_with_drilling_data: int
    wells_with_historical_events: int
    wells_with_documents: int
    high_risk_records_count: int
    total_risk_records_count: int
    total_geology_intervals: int
    total_mud_log_records: int
    basin_distribution: Dict[str, int]
    operator_distribution: Dict[str, int]
    event_type_distribution: Dict[str, int]
    recent_historical_events: List[HistoricalDrillingEvent]
