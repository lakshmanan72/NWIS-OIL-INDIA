from pydantic import BaseModel, Field
from typing import List, Optional


class GeologyInterval(BaseModel):
    geology_id: str
    well_id: str
    well_name: Optional[str] = None
    basin: Optional[str] = None
    field: Optional[str] = None
    block: Optional[str] = None
    interval_no: int
    top_depth_m: float
    bottom_depth_m: float
    formation: str
    lithology: str
    porosity_pct: Optional[float] = None
    permeability_md: Optional[float] = None
    pore_pressure_psi: Optional[int] = None
    fracture_pressure_psi: Optional[int] = None
    temperature_c: Optional[float] = None
    geological_age: Optional[str] = None
    hydrocarbon_show: Optional[str] = None
    reservoir_quality: Optional[str] = None


class GeologyResponse(BaseModel):
    well_id: str
    count: int
    intervals: List[GeologyInterval]


class FormationLithologyItem(BaseModel):
    formation_id: str
    well_id: str
    depth_from_md: float
    depth_to_md: float
    formation_name: str
    lithology: str
    rock_type: str
    geological_age: str
    porosity_percent: Optional[float] = None
    permeability_md: Optional[float] = None
    formation_pressure_psi: Optional[int] = None
    formation_temperature_c: Optional[float] = None
    formation_description: Optional[str] = None


class FormationLithologyResponse(BaseModel):
    well_id: str
    count: int
    formations: List[FormationLithologyItem]
