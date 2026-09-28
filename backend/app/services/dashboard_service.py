from typing import Dict, Any, List
import pandas as pd
from ..models.dashboard import DashboardStatsResponse
from ..repositories.well_repository import well_repository
from .historical_event_service import historical_event_service
from .risk_service import risk_service
from .drilling_service import drilling_service
from .document_service import document_service
from .geology_service import geology_service
from .mud_logging_service import mud_logging_service


class DashboardService:
    def __init__(self):
        self._cached_stats: Dict[str, Any] = {}

    def get_dashboard_stats(self) -> DashboardStatsResponse:
        wells_df = well_repository.dataframe
        total_wells = well_repository.get_total_count()

        drilling_service._ensure_loaded()
        drill_df = drilling_service._df
        wells_with_drilling = int(drill_df["well_id"].nunique())

        historical_event_service._ensure_loaded()
        events_df = historical_event_service._df
        wells_with_events = int(events_df["well_id"].nunique())

        document_service._ensure_loaded()
        docs_df = document_service._df
        wells_with_docs = int(docs_df["well_id"].nunique())

        risk_service._ensure_loaded()
        risk_df = risk_service._df
        high_risk_count = int((risk_df["risk_level"].str.upper() == "HIGH").sum())
        total_risk_records = len(risk_df)

        geology_service._ensure_loaded()
        total_geology = len(geology_service._df)

        mud_logging_service._ensure_loaded()
        total_mud = len(mud_logging_service._df)

        basin_dist = wells_df["basin"].value_counts().head(10).to_dict()
        operator_dist = wells_df["operator"].value_counts().head(10).to_dict()
        event_dist = events_df["event_type"].value_counts().head(8).to_dict()

        recent_events = historical_event_service.get_recent_events(limit=8)

        return DashboardStatsResponse(
            total_wells=total_wells,
            wells_with_drilling_data=wells_with_drilling,
            wells_with_historical_events=wells_with_events,
            wells_with_documents=wells_with_docs,
            high_risk_records_count=high_risk_count,
            total_risk_records_count=total_risk_records,
            total_geology_intervals=total_geology,
            total_mud_log_records=total_mud,
            basin_distribution=basin_dist,
            operator_distribution=operator_dist,
            event_type_distribution=event_dist,
            recent_historical_events=recent_events,
        )


dashboard_service = DashboardService()
