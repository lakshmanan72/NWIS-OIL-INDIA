from typing import List, Optional, Dict
import pandas as pd
from ..models.geology import FormationLithologyItem, FormationLithologyResponse
from .data_path import resolve_data_file


class FormationService:
    def __init__(self, csv_path: Optional[str] = None):
        self.csv_path = resolve_data_file("nwis_formation_lithology_15108.csv", custom_path=csv_path)
        self._df: Optional[pd.DataFrame] = None
        self._cache: Dict[str, List[FormationLithologyItem]] = {}
        self._initialized = False

    def _ensure_loaded(self):
        if self._initialized:
            return

        df = pd.read_csv(self.csv_path, low_memory=False)
        df["well_id"] = df["well_id"].astype(str).str.strip().str.upper()
        self._df = df
        self._initialized = True

    def get_formations_by_well(self, well_id: str) -> FormationLithologyResponse:
        self._ensure_loaded()
        wid = str(well_id).strip().upper()

        if wid in self._cache:
            formations = self._cache[wid]
            return FormationLithologyResponse(well_id=wid, count=len(formations), formations=formations)

        sub_df = self._df[self._df["well_id"] == wid].sort_values("depth_from_md")
        formations: List[FormationLithologyItem] = []

        for _, row in sub_df.iterrows():
            item = FormationLithologyItem(
                formation_id=str(row["formation_id"]),
                well_id=str(row["well_id"]),
                depth_from_md=float(row["depth_from_md"]),
                depth_to_md=float(row["depth_to_md"]),
                formation_name=str(row["formation_name"]),
                lithology=str(row["lithology"]),
                rock_type=str(row["rock_type"]),
                geological_age=str(row["geological_age"]),
                porosity_percent=float(row["porosity_percent"]) if pd.notnull(row["porosity_percent"]) else None,
                permeability_md=float(row["permeability_md"]) if pd.notnull(row["permeability_md"]) else None,
                formation_pressure_psi=int(row["formation_pressure_psi"]) if pd.notnull(row["formation_pressure_psi"]) else None,
                formation_temperature_c=float(row["formation_temperature_c"]) if pd.notnull(row["formation_temperature_c"]) else None,
                formation_description=str(row["formation_description"]) if pd.notnull(row["formation_description"]) else None,
            )
            formations.append(item)

        self._cache[wid] = formations
        return FormationLithologyResponse(well_id=wid, count=len(formations), formations=formations)


formation_service = FormationService()
