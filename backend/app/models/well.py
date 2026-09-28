from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class WellMarker(BaseModel):
    id: str = Field(..., description="Unique identifier of the well record / Leaflet element key")
    well_id: Optional[str] = Field(None, description="Canonical well identifier, e.g. WELL-000001")
    legacy_id: Optional[str] = Field(None, description="Legacy GIS identifier e.g. wells_all_public.fid--...")
    source_id: Optional[str] = Field(None, description="Cleaned source system identifier")
    identity_status: str = Field(default="RESOLVED", description="Identity resolution status: RESOLVED, CANONICAL_DIRECT, or UNRESOLVED")
    gid: int = Field(0, description="Geographic/Grid ID")
    well_name: str = Field(..., description="Name of the well")
    operator: str = Field(..., description="Operating company")
    latitude: float = Field(..., description="Latitude coordinate in decimal degrees [-90, 90]")
    longitude: float = Field(..., description="Longitude coordinate in decimal degrees [-180, 180]")
    basin: Optional[str] = Field(None, description="Sedimentary basin")
    field: Optional[str] = Field(None, description="Oil/Gas field")
    total_depth: Optional[float] = Field(None, description="Total depth in meters")
    formation: Optional[str] = Field(None, description="Formation name")
    document_count: Optional[int] = Field(None, description="Number of associated technical documents")
    event_count: Optional[int] = Field(None, description="Number of historical drilling events")
    is_new_well: bool = Field(False, description="Whether this well is a newly added WCR well")
    coordinate_source: Optional[str] = Field(None, description="Origin of coordinates: WCR_DOCUMENT or ENGINEER_ENTERED")
    coordinate_confidence: Optional[float] = Field(None, description="Extraction confidence score for coordinates")
    source_document: Optional[str] = Field(None, description="Document ID or filename of source WCR")
    uploaded_at: Optional[str] = Field(None, description="Upload timestamp of WCR")
    extraction_confidence: Optional[float] = Field(None, description="Overall extraction confidence")


class WellMarkersResponse(BaseModel):
    count: int = Field(..., description="Total number of valid well markers")
    data_source: str = Field(default="REAL_PUBLIC", description="Provenance of data source")
    dataset_name: str = Field(default="nwis_wells_columns.csv", description="Source dataset file name")
    markers: List[WellMarker] = Field(..., description="List of valid well marker locations")


class CanonicalWell(BaseModel):
    well_id: str = Field(..., description="Canonical well identifier, e.g. WELL-000001")
    well_name: str = Field(..., description="Designated well name, e.g. RAJASTHAN-WELL-00001")
    operator: str = Field(..., description="Operating company, e.g. ONGC, Vedanta, BPCL")
    field: str = Field(..., description="Oil/Gas field name")
    basin: str = Field(..., description="Sedimentary basin")
    block: str = Field(..., description="Exploration/Production block identifier")
    latitude: float = Field(..., description="Latitude in decimal degrees")
    longitude: float = Field(..., description="Longitude in decimal degrees")
    spud_date: Optional[str] = Field(None, description="Drilling commencement date (YYYY-MM-DD)")
    completion_date: Optional[str] = Field(None, description="Well completion date (YYYY-MM-DD)")
    total_depth: Optional[float] = Field(None, description="Total depth in meters")
    well_type: Optional[str] = Field(None, description="Exploratory, Development, Gas, Oil, etc.")
    well_status: Optional[str] = Field(None, description="Producing, Suspended, Abandoned, Active")
    trajectory_type: Optional[str] = Field(None, description="Vertical, Directional, Horizontal")
    formation: Optional[str] = Field(None, description="Formation name")
    is_new_well: bool = Field(False, description="Whether this is a newly created WCR well")
    coordinate_source: Optional[str] = Field(default="REAL_PUBLIC", description="Source of coordinates")
    coordinate_confidence: Optional[float] = Field(default=1.0, description="Confidence score")
    source_document: Optional[str] = Field(None, description="Source WCR document ID")
    uploaded_at: Optional[str] = Field(None, description="Timestamp added to NWIS")


class CanonicalWellsResponse(BaseModel):
    total: int
    count: int
    offset: int
    limit: int
    wells: List[CanonicalWell]


class NearbyWellItem(BaseModel):
    well_id: str
    well_name: str
    distance_km: float
    operator: str
    field: str
    basin: str
    block: str
    well_type: Optional[str] = None
    well_status: Optional[str] = None
    total_depth: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    same_field: bool = False
    same_block: bool = False
    same_basin: bool = False
    proximity_class: str = "Nearby"


class NearbyWellsResponse(BaseModel):
    source_well: CanonicalWell
    radius_km: float
    count: int
    nearby_wells: List[NearbyWellItem]
    center: Optional[Dict[str, Any]] = None
    wells: Optional[List[NearbyWellItem]] = None
