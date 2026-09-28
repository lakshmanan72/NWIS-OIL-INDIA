from typing import List, Optional, Dict
import pandas as pd
from ..models.geology import GeologyInterval, GeologyResponse
from .data_path import resolve_data_file


class GeologyService:
    def __init__(self, csv_path: Optional[str] = None):
        self.csv_path = resolve_data_file("nwis_well_geology_15108.csv", custom_path=csv_path)
        self._df: Optional[pd.DataFrame] = None
        self._cache: Dict[str, List[GeologyInterval]] = {}
        self._initialized = False

    def _ensure_loaded(self):
        if self._initialized:
            return

        df = pd.read_csv(self.csv_path, low_memory=False)
        df["well_id"] = df["well_id"].astype(str).str.strip().str.upper()
        self._df = df
        self._initialized = True

    def get_geology_by_well(self, well_id: str) -> GeologyResponse:
        self._ensure_loaded()
        wid = str(well_id).strip().upper()

        if wid in self._cache:
            intervals = self._cache[wid]
            return GeologyResponse(well_id=wid, count=len(intervals), intervals=intervals)

        sub_df = self._df[self._df["well_id"] == wid].sort_values("top_depth_m")
        intervals: List[GeologyInterval] = []

        for _, row in sub_df.iterrows():
            item = GeologyInterval(
                geology_id=str(row["geology_id"]),
                well_id=str(row["well_id"]),
                well_name=str(row["well_name"]) if pd.notnull(row["well_name"]) else None,
                basin=str(row["basin"]) if pd.notnull(row["basin"]) else None,
                field=str(row["field"]) if pd.notnull(row["field"]) else None,
                block=str(row["block"]) if pd.notnull(row["block"]) else None,
                interval_no=int(row["interval_no"]),
                top_depth_m=float(row["top_depth_m"]),
                bottom_depth_m=float(row["bottom_depth_m"]),
                formation=str(row["formation"]),
                lithology=str(row["lithology"]),
                porosity_pct=float(row["porosity_pct"]) if pd.notnull(row["porosity_pct"]) else None,
                permeability_md=float(row["permeability_md"]) if pd.notnull(row["permeability_md"]) else None,
                pore_pressure_psi=int(row["pore_pressure_psi"]) if pd.notnull(row["pore_pressure_psi"]) else None,
                fracture_pressure_psi=int(row["fracture_pressure_psi"]) if pd.notnull(row["fracture_pressure_psi"]) else None,
                temperature_c=float(row["temperature_c"]) if pd.notnull(row["temperature_c"]) else None,
                geological_age=str(row["geological_age"]) if pd.notnull(row["geological_age"]) else None,
                hydrocarbon_show=str(row["hydrocarbon_show"]) if pd.notnull(row["hydrocarbon_show"]) else None,
                reservoir_quality=str(row["reservoir_quality"]) if pd.notnull(row["reservoir_quality"]) else None,
            )
            intervals.append(item)

        self._cache[wid] = intervals
        return GeologyResponse(well_id=wid, count=len(intervals), intervals=intervals)


geology_service = GeologyService()
