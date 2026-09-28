from fastapi import APIRouter, HTTPException, Query, Response
from typing import Optional, List, Dict, Any
from ..models.well import (
    WellMarkersResponse,
    CanonicalWell,
    CanonicalWellsResponse,
    NearbyWellsResponse,
)
from ..models.geology import GeologyResponse, FormationLithologyResponse
from ..models.drilling import DailyDrillingResponse
from ..models.mud_logging import MudLoggingResponse
from ..models.historical_event import HistoricalEventsResponse
from ..models.completion import WellCompletionResponse
from ..models.document import DocumentMetadataResponse, WellLinkedDocumentResponse
from ..models.risk import RiskRecommendationsResponse
from ..models.offset_intelligence import OffsetIntelligenceResponse
from ..services.well_service import well_service
from ..services.spatial_service import spatial_service
from ..services.geology_service import geology_service
from ..services.formation_service import formation_service
from ..services.drilling_service import drilling_service
from ..services.mud_logging_service import mud_logging_service
from ..services.historical_event_service import historical_event_service
from ..services.completion_service import completion_service
from ..services.document_service import document_service
from ..services.risk_service import risk_service
from ..services.offset_intelligence_service import offset_intelligence_service

router = APIRouter(prefix="/api/wells", tags=["Wells"])


# --- Existing Map Route (Preserved for existing frontend map & pytest) ---
@router.get("/map-markers", response_model=WellMarkersResponse)
def get_well_map_markers(response: Response, include_new: bool = Query(True)) -> WellMarkersResponse:
    """
    Returns valid well marker locations dynamically loaded from the legacy public dataset.
    When include_new=true, also includes newly created and approved canonical wells.
    Preserved for backwards compatibility with the existing Leaflet map.
    """
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return well_service.load_markers(include_new_wells=include_new)


# --- Dynamic Database Well Count ---
@router.get("/count")
def get_well_count() -> Dict[str, Any]:
    """
    Returns the authoritative real-time database well count directly from PostgreSQL / active repository.
    Never hardcoded.
    """
    return well_service.get_count_response()


# --- Canonical Well Endpoints ---
@router.get("", response_model=CanonicalWellsResponse)
def get_wells(
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=500, description="Number of wells to return"),
    basin: Optional[str] = Query(None, description="Filter by basin"),
    operator: Optional[str] = Query(None, description="Filter by operator"),
    search: Optional[str] = Query(None, description="Search term for well name or ID")
) -> CanonicalWellsResponse:
    """
    Retrieves canonical wells from the master registry (nwis_well_locations_15108_new.csv).
    """
    return well_service.get_all_canonical_wells(
        offset=offset,
        limit=limit,
        basin=basin,
        operator=operator,
        search=search
    )


@router.get("/search", response_model=List[CanonicalWell])
def search_wells(
    q: str = Query(..., min_length=1, description="Query string for search"),
    limit: int = Query(20, ge=1, le=100)
) -> List[CanonicalWell]:
    """
    Quick search across canonical wells by ID, name, operator, or basin.
    """
    return well_service.search_canonical_wells(q, limit=limit)


@router.get("/{well_id}", response_model=CanonicalWell)
def get_well(well_id: str) -> CanonicalWell:
    """
    Retrieves a single canonical well record by well_id (e.g. WELL-000001).
    """
    well = well_service.get_well_by_id(well_id)
    if not well:
        raise HTTPException(status_code=404, detail=f"Well '{well_id}' was not found in canonical master registry.")
    return well


# --- Nearby Well Engine ---
@router.get("/{well_id}/nearby", response_model=NearbyWellsResponse)
def get_nearby_wells(
    well_id: str,
    radius_km: float = Query(25.0, ge=0.1, le=500.0, description="Search radius in kilometers"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of nearby offset wells")
) -> NearbyWellsResponse:
    """
    Nearby Well Engine: Returns proximate offset wells using precomputed spatial relationships,
    with automatic mathematical Haversine fallback.
    """
    try:
        return spatial_service.get_nearby_wells(well_id=well_id, radius_km=radius_km, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Subsurface Geology & Formation ---
@router.get("/{well_id}/geology", response_model=GeologyResponse)
def get_well_geology(well_id: str) -> GeologyResponse:
    """
    Returns subsurface geological intervals and reservoir properties from nwis_well_geology_15108.csv.
    """
    well = well_service.get_well_by_id(well_id)
    if not well:
        raise HTTPException(status_code=404, detail=f"Well '{well_id}' not found.")
    return geology_service.get_geology_by_well(well.well_id)


@router.get("/{well_id}/formations", response_model=FormationLithologyResponse)
def get_well_formations(well_id: str) -> FormationLithologyResponse:
    """
    Returns formation stratigraphy and lithology from nwis_formation_lithology_15108.csv.
    """
    well = well_service.get_well_by_id(well_id)
    if not well:
        raise HTTPException(status_code=404, detail=f"Well '{well_id}' not found.")
    return formation_service.get_formations_by_well(well.well_id)


# --- Drilling Telemetry ---
@router.get("/{well_id}/drilling", response_model=DailyDrillingResponse)
def get_well_drilling(well_id: str) -> DailyDrillingResponse:
    """
    Returns daily operational drilling telemetry from nwis_daily_drilling_parameters_15108.csv.
    """
    well = well_service.get_well_by_id(well_id)
    if not well:
        raise HTTPException(status_code=404, detail=f"Well '{well_id}' not found.")
    return drilling_service.get_drilling_parameters_by_well(well.well_id)


# --- Mud Logging Sensor Telemetry ---
@router.get("/{well_id}/mud-logging", response_model=MudLoggingResponse)
def get_well_mud_logging(
    well_id: str,
    limit: int = Query(50, ge=1, le=200, description="Page limit for sensor rows"),
    depth_min: Optional[float] = Query(None, description="Minimum depth filter in meters"),
    depth_max: Optional[float] = Query(None, description="Maximum depth filter in meters")
) -> MudLoggingResponse:
    """
    Returns server-filtered mud logging sensor telemetry from nwis_mud_logging_15108_wells.csv.
    """
    well = well_service.get_well_by_id(well_id)
    if not well:
        raise HTTPException(status_code=404, detail=f"Well '{well_id}' not found.")
    return mud_logging_service.get_mud_logging_by_well(
        well_id=well.well_id,
        limit=limit,
        depth_min=depth_min,
        depth_max=depth_max
    )


# --- Historical Drilling Events ---
@router.get("/{well_id}/events", response_model=HistoricalEventsResponse)
def get_well_events(well_id: str) -> HistoricalEventsResponse:
    """
    Returns historical drilling incidents and non-productive time records from nwis_historical_drilling_events_15108.csv.
    """
    well = well_service.get_well_by_id(well_id)
    if not well:
        raise HTTPException(status_code=404, detail=f"Well '{well_id}' not found.")
    return historical_event_service.get_events_by_well(well.well_id)


# --- Well Completion Report (WCR) ---
@router.get("/{well_id}/completion", response_model=WellCompletionResponse)
def get_well_completion(well_id: str) -> WellCompletionResponse:
    """
    Returns Well Completion Report (WCR) technical handover data from nwis_well_completion_wcr_15108.csv.
    """
    well = well_service.get_well_by_id(well_id)
    if not well:
        raise HTTPException(status_code=404, detail=f"Well '{well_id}' not found.")
    return completion_service.get_completion_by_well(well.well_id)


# --- Document Metadata ---
@router.get("/{well_id}/documents", response_model=DocumentMetadataResponse)
def get_well_documents(well_id: str) -> DocumentMetadataResponse:
    """
    Returns archival document catalog from nwis_document_metadata_15108.csv.
    """
    well = well_service.get_well_by_id(well_id)
    if not well:
        raise HTTPException(status_code=404, detail=f"Well '{well_id}' not found.")
    return document_service.get_documents_by_well(well.well_id)


# --- Single Linked WCR Document Resolution ---
@router.get("/{well_id}/document", response_model=WellLinkedDocumentResponse)
@router.get("/{well_id}/wcr-document", response_model=WellLinkedDocumentResponse)
def get_well_linked_document(well_id: str) -> WellLinkedDocumentResponse:
    """
    Resolves a canonical well_id to its actual linked WCR document_id and metadata.
    Returns 404 with a semantic message if no WCR document exists for the well.
    """
    well = well_service.get_well_by_id(well_id)
    if not well:
        raise HTTPException(status_code=404, detail=f"Well '{well_id}' not found.")

    doc_info = document_service.get_linked_wcr_document(well.well_id)
    if not doc_info:
        raise HTTPException(
            status_code=404,
            detail=f"No WCR document available for well '{well.well_id}'."
        )

    return WellLinkedDocumentResponse(**doc_info)


# --- Risk Recommendations ---
@router.get("/{well_id}/risks", response_model=RiskRecommendationsResponse)
def get_well_risks(well_id: str) -> RiskRecommendationsResponse:
    """
    Returns prototype risk recommendations and offset hazard predictions from nwis_risk_recommendations.csv.
    """
    well = well_service.get_well_by_id(well_id)
    if not well:
        raise HTTPException(status_code=404, detail=f"Well '{well_id}' not found.")
    return risk_service.get_risks_by_well(well.well_id)


# --- Offset Well Historical Event Intelligence ---
@router.get("/{well_id}/offset-intelligence", response_model=OffsetIntelligenceResponse)
def get_well_offset_intelligence(
    well_id: str,
    current_depth: Optional[float] = Query(None, description="Current drilling bit depth in meters"),
    current_formation: Optional[str] = Query(None, description="Active formation name"),
    radius_km: float = Query(25.0, ge=1.0, le=200.0, description="Offset search radius in kilometers"),
    depth_window_m: float = Query(200.0, ge=10.0, le=1000.0, description="Depth correlation window in meters (±)")
) -> OffsetIntelligenceResponse:
    """
    NWIS Core Intelligence: Correlates active well depth and formation against nearby offset wells'
    historical drilling events. Provides supporting evidence with data provenance.
    """
    well = well_service.get_well_by_id(well_id)
    if not well:
        raise HTTPException(status_code=404, detail=f"Well '{well_id}' not found.")
    try:
        return offset_intelligence_service.get_offset_intelligence(
            well_id=well.well_id,
            current_depth=current_depth,
            current_formation=current_formation,
            radius_km=radius_km,
            depth_window_m=depth_window_m
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
