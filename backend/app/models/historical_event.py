from pydantic import BaseModel, Field
from typing import List, Optional


class HistoricalDrillingEvent(BaseModel):
    event_id: str
    well_id: str
    report_id: str
    report_type: str
    report_date: str
    depth_md: float
    formation: str
    event_type: str
    severity: str
    description: str
    action_taken: str
    outcome: str
    npt_hours: float
    page_number: int
    source_document: str


class HistoricalEventsResponse(BaseModel):
    well_id: str
    count: int
    events: List[HistoricalDrillingEvent]
