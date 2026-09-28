from typing import List, Optional, Dict
import pandas as pd
from ..models.risk import RiskRecommendationRecord, RiskRecommendationsResponse
from .data_path import resolve_data_file


class RiskService:
    def __init__(self, csv_path: Optional[str] = None):
        self.csv_path = resolve_data_file("nwis_risk_recommendations.csv", custom_path=csv_path)
        self._df: Optional[pd.DataFrame] = None
        self._cache: Dict[str, List[RiskRecommendationRecord]] = {}
        self._initialized = False

    def _ensure_loaded(self):
        if self._initialized:
            return

        df = pd.read_csv(self.csv_path, low_memory=False)
        df["well_id"] = df["well_id"].astype(str).str.strip().str.upper()
        self._df = df
        self._initialized = True

    def get_risks_by_well(self, well_id: str) -> RiskRecommendationsResponse:
        self._ensure_loaded()
        wid = str(well_id).strip().upper()

        if wid in self._cache:
            recs = self._cache[wid]
            return RiskRecommendationsResponse(
                well_id=wid,
                count=len(recs),
                recommendations=recs
            )

        sub_df = self._df[self._df["well_id"] == wid].sort_values("prediction_rank")
        recs: List[RiskRecommendationRecord] = []

        for _, row in sub_df.iterrows():
            item = RiskRecommendationRecord(
                prediction_id=str(row["prediction_id"]),
                well_id=str(row["well_id"]),
                depth_md=float(row["depth_md"]),
                formation=str(row["formation"]),
                predicted_event=str(row["predicted_event"]),
                risk_score=float(row["risk_score"]),
                risk_level=str(row["risk_level"]),
                similar_historical_wells=str(row["similar_historical_wells"]),
                recommended_action=str(row["recommended_action"]),
                supporting_event_id=str(row["supporting_event_id"]) if pd.notnull(row["supporting_event_id"]) else None,
                confidence=float(row["confidence"]),
                prediction_rank=int(row["prediction_rank"]),
            )
            recs.append(item)

        self._cache[wid] = recs
        return RiskRecommendationsResponse(
            well_id=wid,
            count=len(recs),
            recommendations=recs
        )

    def get_high_risk_records_count(self) -> int:
        self._ensure_loaded()
        return int((self._df["risk_level"].str.upper() == "HIGH").sum())

    def get_total_risk_records_count(self) -> int:
        self._ensure_loaded()
        return len(self._df)


risk_service = RiskService()
