from pydantic import BaseModel, Field
from typing import List, Optional


class DailyDrillingRecord(BaseModel):
    drilling_record_id: str
    well_id: str
    record_date: str
    depth_md: float
    depth_tvd: float
    rop_m_per_hr: float
    wob_klbf: float
    rpm: int
    torque_knm: float
    flow_rate_lpm: int
    pump_pressure_psi: int
    standpipe_pressure_psi: int
    mud_weight_ppg: float
    mud_viscosity_cp: int
    mud_loss_lph: float
    ecd_ppg: float
    hook_load_klbf: float


class DailyDrillingResponse(BaseModel):
    well_id: str
    count: int
    records: List[DailyDrillingRecord]
