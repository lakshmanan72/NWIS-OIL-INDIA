from pydantic import BaseModel, Field
from typing import List, Optional


class MudLogRecord(BaseModel):
    mud_log_id: str
    well_id: str
    well_name: Optional[str] = None
    depth_m: float
    timestamp: str
    mud_type: Optional[str] = None
    mud_weight_ppg: Optional[float] = None
    mud_viscosity_cp: Optional[float] = None
    mud_temperature_c: Optional[float] = None
    mud_pH: Optional[float] = None
    mud_flow_rate_lpm: Optional[float] = None
    standpipe_pressure_psi: Optional[float] = None
    pit_volume_bbl: Optional[float] = None
    pit_gain_loss_bbl: Optional[float] = None
    flow_out_pct: Optional[float] = None
    gas_total_units: Optional[float] = None
    methane_units: Optional[float] = None
    ethane_units: Optional[float] = None
    propane_units: Optional[float] = None
    connection_gas_units: Optional[float] = None
    trip_gas_units: Optional[float] = None
    cuttings_rate_kg_hr: Optional[float] = None
    cuttings_size_mm: Optional[float] = None
    cuttings_shape: Optional[str] = None
    cuttings_color: Optional[str] = None
    lithology_observed: Optional[str] = None
    oil_show: Optional[str] = None
    gas_show: Optional[str] = None
    fluorescence: Optional[str] = None
    formation_pressure_estimate_psi: Optional[float] = None
    kick_indicator: Optional[bool] = None
    loss_indicator: Optional[bool] = None
    overpressure_indicator: Optional[bool] = None
    mud_loss_severity: Optional[str] = None
    drilling_event: Optional[str] = None


class MudLoggingResponse(BaseModel):
    well_id: str
    count: int
    total_available: int
    records: List[MudLogRecord]
