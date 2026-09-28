from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from .well import CanonicalWell, NearbyWellItem
from .historical_event import HistoricalDrillingEvent


class OffsetHistoricalEvidence(BaseModel):
    event_id: str
    well_id: str
    well_name: Optional[str] = None
    distance_km: Optional[float] = None
    event_type: str
    severity: str
    depth_md: float
    depth_difference_m: float
    formation: str
    formation_match: bool
    description: str
    action_taken: str
    outcome: str
    npt_hours: float
    source_document: str
    page_number: int
    source_dataset: str = "nwis_historical_drilling_events_15108.csv"


class OffsetIntelligenceResponse(BaseModel):
    current_well: CanonicalWell
    current_depth: float
    current_formation: Optional[str] = None
    historical_event_interval: str
    nearby_wells_count: int
    nearby_wells: List[NearbyWellItem]
    historical_events_count: int
    historical_events: List[OffsetHistoricalEvidence]
    formation_matches: List[OffsetHistoricalEvidence]
    depth_matches: List[OffsetHistoricalEvidence]
    event_matches: Dict[str, int]
    supporting_wells: List[str]
    alert_summary: Optional[str] = None
