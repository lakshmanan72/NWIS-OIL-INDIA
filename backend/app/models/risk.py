from pydantic import BaseModel, Field
from typing import List, Optional


class RiskRecommendationRecord(BaseModel):
    prediction_id: str
    well_id: str
    depth_md: float
    formation: str
    predicted_event: str
    risk_score: float
    risk_level: str
    similar_historical_wells: str
    recommended_action: str
    supporting_event_id: Optional[str] = None
    confidence: float
    prediction_rank: int


class RiskRecommendationsResponse(BaseModel):
    well_id: str
    disclaimer: str = "PROTOTYPE RISK ANALYSIS — For Demonstration & Research Purposes Only"
    count: int
    recommendations: List[RiskRecommendationRecord]
