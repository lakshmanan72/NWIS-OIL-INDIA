from typing import List, Optional, Dict
import pandas as pd
from ..models.drilling import DailyDrillingRecord, DailyDrillingResponse
from .data_path import resolve_data_file


class DrillingService:
    def __init__(self, csv_path: Optional[str] = None):
        self.csv_path = resolve_data_file("nwis_daily_drilling_parameters_15108.csv", custom_path=csv_path)
        self._df: Optional[pd.DataFrame] = None
        self._cache: Dict[str, List[DailyDrillingRecord]] = {}
        self._initialized = False

    def _ensure_loaded(self):
        if self._initialized:
            return

        df = pd.read_csv(self.csv_path, low_memory=False)
        df["well_id"] = df["well_id"].astype(str).str.strip().str.upper()
        self._df = df
        self._initialized = True

    def get_drilling_parameters_by_well(self, well_id: str) -> DailyDrillingResponse:
        self._ensure_loaded()
        wid = str(well_id).strip().upper()

        if wid in self._cache:
            records = self._cache[wid]
            return DailyDrillingResponse(well_id=wid, count=len(records), records=records)

        sub_df = self._df[self._df["well_id"] == wid].sort_values("record_date")
        records: List[DailyDrillingRecord] = []

        for _, row in sub_df.iterrows():
            item = DailyDrillingRecord(
                drilling_record_id=str(row["drilling_record_id"]),
                well_id=str(row["well_id"]),
                record_date=str(row["record_date"]),
                depth_md=float(row["depth_md"]),
                depth_tvd=float(row["depth_tvd"]),
                rop_m_per_hr=float(row["rop_m_per_hr"]),
                wob_klbf=float(row["wob_klbf"]),
                rpm=int(row["rpm"]),
                torque_knm=float(row["torque_knm"]),
                flow_rate_lpm=int(row["flow_rate_lpm"]),
                pump_pressure_psi=int(row["pump_pressure_psi"]),
                standpipe_pressure_psi=int(row["standpipe_pressure_psi"]),
                mud_weight_ppg=float(row["mud_weight_ppg"]),
                mud_viscosity_cp=int(row["mud_viscosity_cp"]),
                mud_loss_lph=float(row["mud_loss_lph"]),
                ecd_ppg=float(row["ecd_ppg"]),
                hook_load_klbf=float(row["hook_load_klbf"]),
            )
            records.append(item)

        self._cache[wid] = records
        return DailyDrillingResponse(well_id=wid, count=len(records), records=records)


drilling_service = DrillingService()
