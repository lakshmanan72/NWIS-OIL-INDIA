from typing import List, Optional, Dict
import pandas as pd
from ..models.historical_event import HistoricalDrillingEvent, HistoricalEventsResponse
from .data_path import resolve_data_file


class HistoricalEventService:
    def __init__(self, csv_path: Optional[str] = None):
        self.csv_path = resolve_data_file("nwis_historical_drilling_events_15108.csv", custom_path=csv_path)
        self._df: Optional[pd.DataFrame] = None
        self._cache: Dict[str, List[HistoricalDrillingEvent]] = {}
        self._events_by_id: Dict[str, HistoricalDrillingEvent] = {}
        self._initialized = False

    def _ensure_loaded(self):
        if self._initialized:
            return

        df = pd.read_csv(self.csv_path, low_memory=False)
        df["well_id"] = df["well_id"].astype(str).str.strip().str.upper()
        df["event_id"] = df["event_id"].astype(str).str.strip().str.upper()
        self._df = df
        self._initialized = True

    def get_events_by_well(self, well_id: str) -> HistoricalEventsResponse:
        self._ensure_loaded()
        wid = str(well_id).strip().upper()

        if wid in self._cache:
            events = self._cache[wid]
            return HistoricalEventsResponse(well_id=wid, count=len(events), events=events)

        sub_df = self._df[self._df["well_id"] == wid].sort_values("depth_md")
        events: List[HistoricalDrillingEvent] = []

        for _, row in sub_df.iterrows():
            item = HistoricalDrillingEvent(
                event_id=str(row["event_id"]),
                well_id=str(row["well_id"]),
                report_id=str(row["report_id"]),
                report_type=str(row["report_type"]),
                report_date=str(row["report_date"]),
                depth_md=float(row["depth_md"]),
                formation=str(row["formation"]),
                event_type=str(row["event_type"]),
                severity=str(row["severity"]),
                description=str(row["description"]),
                action_taken=str(row["action_taken"]),
                outcome=str(row["outcome"]),
                npt_hours=float(row["npt_hours"]),
                page_number=int(row["page_number"]),
                source_document=str(row["source_document"]),
            )
            events.append(item)
            self._events_by_id[item.event_id] = item

        # Also check dynamic approved drilling events from document repository
        try:
            from ...document_ai.document_repository import document_repository
            approved_doc_events = document_repository.get_approved_events()
            for devt in approved_doc_events:
                if devt.well_id.upper() == wid and not any(e.event_id == devt.event_id for e in events):
                    item = HistoricalDrillingEvent(
                        event_id=devt.event_id,
                        well_id=devt.well_id,
                        report_id=devt.document_id,
                        report_type="WCR_EXTRACTED",
                        report_date="2026-09-27",
                        depth_md=float(devt.depth_md) if devt.depth_md is not None else 0.0,
                        formation=str(devt.formation or "Barail"),
                        event_type=devt.event_type,
                        severity="High" if devt.confidence > 0.9 else "Medium",
                        description=devt.raw_event_text,
                        action_taken=devt.hazard_assumption,
                        outcome="Operational review documented in institutional memory.",
                        npt_hours=0.0,
                        page_number=devt.source_page,
                        source_document=devt.document_id,
                    )
                    events.append(item)
                    self._events_by_id[item.event_id] = item
        except Exception:
            pass

        self._cache[wid] = events
        return HistoricalEventsResponse(well_id=wid, count=len(events), events=events)

    def get_event_by_id(self, event_id: str) -> Optional[HistoricalDrillingEvent]:
        self._ensure_loaded()
        eid = str(event_id).strip().upper()
        if eid in self._events_by_id:
            return self._events_by_id[eid]

        sub = self._df[self._df["event_id"] == eid]
        if sub.empty:
            return None

        row = sub.iloc[0]
        item = HistoricalDrillingEvent(
            event_id=str(row["event_id"]),
            well_id=str(row["well_id"]),
            report_id=str(row["report_id"]),
            report_type=str(row["report_type"]),
            report_date=str(row["report_date"]),
            depth_md=float(row["depth_md"]),
            formation=str(row["formation"]),
            event_type=str(row["event_type"]),
            severity=str(row["severity"]),
            description=str(row["description"]),
            action_taken=str(row["action_taken"]),
            outcome=str(row["outcome"]),
            npt_hours=float(row["npt_hours"]),
            page_number=int(row["page_number"]),
            source_document=str(row["source_document"]),
        )
        self._events_by_id[eid] = item
        return item

    def get_recent_events(self, limit: int = 20) -> List[HistoricalDrillingEvent]:
        self._ensure_loaded()
        sub = self._df.sort_values("report_date", ascending=False).head(limit)
        events: List[HistoricalDrillingEvent] = []
        for _, row in sub.iterrows():
            item = HistoricalDrillingEvent(
                event_id=str(row["event_id"]),
                well_id=str(row["well_id"]),
                report_id=str(row["report_id"]),
                report_type=str(row["report_type"]),
                report_date=str(row["report_date"]),
                depth_md=float(row["depth_md"]),
                formation=str(row["formation"]),
                event_type=str(row["event_type"]),
                severity=str(row["severity"]),
                description=str(row["description"]),
                action_taken=str(row["action_taken"]),
                outcome=str(row["outcome"]),
                npt_hours=float(row["npt_hours"]),
                page_number=int(row["page_number"]),
                source_document=str(row["source_document"]),
            )
            events.append(item)
        return events


historical_event_service = HistoricalEventService()
