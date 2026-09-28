from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class WellCompletionRecord(BaseModel):
    wcr_id: str
    well_id: str
    well_name: str
    operator: str
    field: str
    basin: str
    block: str
    report_date: Optional[str] = None
    completion_date: Optional[str] = None
    total_depth_m: Optional[float] = None
    measured_depth_m: Optional[float] = None
    true_vertical_depth_m: Optional[float] = None
    well_type: Optional[str] = None
    trajectory_type: Optional[str] = None
    completion_type: Optional[str] = None
    reservoir_formation: Optional[str] = None
    reservoir_top_depth_m: Optional[float] = None
    reservoir_bottom_depth_m: Optional[float] = None
    reservoir_temperature_c: Optional[float] = None
    reservoir_pressure_psi: Optional[float] = None
    porosity_pct: Optional[float] = None
    permeability_md: Optional[float] = None
    water_saturation_pct: Optional[float] = None
    oil_saturation_pct: Optional[float] = None
    gas_saturation_pct: Optional[float] = None
    net_pay_m: Optional[float] = None
    gross_pay_m: Optional[float] = None
    mud_type: Optional[str] = None
    completion_fluid: Optional[str] = None
    casing_size_in: Optional[str] = None
    production_tubing_size_in: Optional[str] = None
    cement_top_depth_m: Optional[float] = None
    cement_bottom_depth_m: Optional[float] = None
    perforation_top_depth_m: Optional[float] = None
    perforation_bottom_depth_m: Optional[float] = None
    perforation_interval_m: Optional[float] = None
    completion_pressure_psi: Optional[float] = None
    initial_oil_rate_bopd: Optional[float] = None
    initial_gas_rate_mscfd: Optional[float] = None
    initial_water_rate_bwpd: Optional[float] = None
    production_test_duration_hr: Optional[float] = None
    well_test_pressure_psi: Optional[float] = None
    well_test_temperature_c: Optional[float] = None
    formation_test_result: Optional[str] = None
    completion_status: Optional[str] = None
    completion_method: Optional[str] = None
    artificial_lift: Optional[str] = None
    wellhead_pressure_psi: Optional[float] = None
    initial_production_status: Optional[str] = None
    completion_problems: Optional[str] = None
    workover_required: Optional[bool] = None
    workover_type: Optional[str] = None
    final_well_status: Optional[str] = None
    wcr_summary: Optional[str] = None


class WellCompletionResponse(BaseModel):
    well_id: str
    completion: Optional[WellCompletionRecord] = None
