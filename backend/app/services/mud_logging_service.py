from typing import List, Optional, Dict, Any
import pandas as pd
from ..models.mud_logging import MudLogRecord, MudLoggingResponse
from .data_path import resolve_data_file


class MudLoggingService:
    def __init__(self, csv_path: Optional[str] = None):
        self.csv_path = resolve_data_file("nwis_mud_logging_15108_wells.csv", custom_path=csv_path)
        self._df: Optional[pd.DataFrame] = None
        self._initialized = False

    def _ensure_loaded(self):
        if self._initialized:
            return

        df = pd.read_csv(self.csv_path, low_memory=False)
        df["well_id"] = df["well_id"].astype(str).str.strip().str.upper()
        # Set index and sort for microsecond lookup
        df.set_index("well_id", drop=False, inplace=True)
        df.sort_index(inplace=True)
        self._df = df
        self._initialized = True

    def get_mud_logging_by_well(
        self,
        well_id: str,
        limit: int = 50,
        depth_min: Optional[float] = None,
        depth_max: Optional[float] = None
    ) -> MudLoggingResponse:
        self._ensure_loaded()
        wid = str(well_id).strip().upper()

        if wid not in self._df.index:
            return MudLoggingResponse(well_id=wid, count=0, total_available=0, records=[])

        # Efficient slice on sorted index
        sub_df = self._df.loc[[wid]]
        if isinstance(sub_df, pd.Series):
            sub_df = sub_df.to_frame().T

        if depth_min is not None:
            sub_df = sub_df[sub_df["depth_m"] >= depth_min]
        if depth_max is not None:
            sub_df = sub_df[sub_df["depth_m"] <= depth_max]

        sub_df = sub_df.sort_values("depth_m")
        total_avail = len(sub_df)
        paged_df = sub_df.head(limit)

        records: List[MudLogRecord] = []
        for _, row in paged_df.iterrows():
            item = MudLogRecord(
                mud_log_id=str(row["mud_log_id"]),
                well_id=str(row["well_id"]),
                well_name=str(row["well_name"]) if pd.notnull(row["well_name"]) else None,
                depth_m=float(row["depth_m"]),
                timestamp=str(row["timestamp"]),
                mud_type=str(row["mud_type"]) if pd.notnull(row["mud_type"]) else None,
                mud_weight_ppg=float(row["mud_weight_ppg"]) if pd.notnull(row["mud_weight_ppg"]) else None,
                mud_viscosity_cp=float(row["mud_viscosity_cp"]) if pd.notnull(row["mud_viscosity_cp"]) else None,
                mud_temperature_c=float(row["mud_temperature_c"]) if pd.notnull(row["mud_temperature_c"]) else None,
                mud_pH=float(row["mud_pH"]) if pd.notnull(row["mud_pH"]) else None,
                mud_flow_rate_lpm=float(row["mud_flow_rate_lpm"]) if pd.notnull(row["mud_flow_rate_lpm"]) else None,
                standpipe_pressure_psi=float(row["standpipe_pressure_psi"]) if pd.notnull(row["standpipe_pressure_psi"]) else None,
                pit_volume_bbl=float(row["pit_volume_bbl"]) if pd.notnull(row["pit_volume_bbl"]) else None,
                pit_gain_loss_bbl=float(row["pit_gain_loss_bbl"]) if pd.notnull(row["pit_gain_loss_bbl"]) else None,
                flow_out_pct=float(row["flow_out_pct"]) if pd.notnull(row["flow_out_pct"]) else None,
                gas_total_units=float(row["gas_total_units"]) if pd.notnull(row["gas_total_units"]) else None,
                methane_units=float(row["methane_units"]) if pd.notnull(row["methane_units"]) else None,
                ethane_units=float(row["ethane_units"]) if pd.notnull(row["ethane_units"]) else None,
                propane_units=float(row["propane_units"]) if pd.notnull(row["propane_units"]) else None,
                connection_gas_units=float(row["connection_gas_units"]) if pd.notnull(row["connection_gas_units"]) else None,
                trip_gas_units=float(row["trip_gas_units"]) if pd.notnull(row["trip_gas_units"]) else None,
                cuttings_rate_kg_hr=float(row["cuttings_rate_kg_hr"]) if pd.notnull(row["cuttings_rate_kg_hr"]) else None,
                cuttings_size_mm=float(row["cuttings_size_mm"]) if pd.notnull(row["cuttings_size_mm"]) else None,
                cuttings_shape=str(row["cuttings_shape"]) if pd.notnull(row["cuttings_shape"]) else None,
                cuttings_color=str(row["cuttings_color"]) if pd.notnull(row["cuttings_color"]) else None,
                lithology_observed=str(row["lithology_observed"]) if pd.notnull(row["lithology_observed"]) else None,
                oil_show=str(row["oil_show"]) if pd.notnull(row["oil_show"]) else None,
                gas_show=str(row["gas_show"]) if pd.notnull(row["gas_show"]) else None,
                fluorescence=str(row["fluorescence"]) if pd.notnull(row["fluorescence"]) else None,
                formation_pressure_estimate_psi=float(row["formation_pressure_estimate_psi"]) if pd.notnull(row["formation_pressure_estimate_psi"]) else None,
                kick_indicator=bool(row["kick_indicator"]) if pd.notnull(row["kick_indicator"]) else False,
                loss_indicator=bool(row["loss_indicator"]) if pd.notnull(row["loss_indicator"]) else False,
                overpressure_indicator=bool(row["overpressure_indicator"]) if pd.notnull(row["overpressure_indicator"]) else False,
                mud_loss_severity=str(row["mud_loss_severity"]) if pd.notnull(row["mud_loss_severity"]) else None,
                drilling_event=str(row["drilling_event"]) if pd.notnull(row["drilling_event"]) else None,
            )
            records.append(item)

        return MudLoggingResponse(
            well_id=wid,
            count=len(records),
            total_available=total_avail,
            records=records
        )


mud_logging_service = MudLoggingService()
