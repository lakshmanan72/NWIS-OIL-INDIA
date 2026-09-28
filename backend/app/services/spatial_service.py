import logging
import math
from typing import List, Optional, Dict, Any, Tuple
import pandas as pd
from ..models.well import CanonicalWell, NearbyWellItem, NearbyWellsResponse
from ..repositories.well_repository import well_repository
from .data_path import resolve_data_file

logger = logging.getLogger("nwis.spatial")


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Standard great-circle distance between two points on a sphere (WGS-84 mean radius = 6371.0 km).
    Coordinates: latitude = Y, longitude = X.
    """
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2 +
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
        math.sin(dlon / 2.0) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


class SpatialService:
    def __init__(self, csv_path: Optional[str] = None):
        self.csv_path = resolve_data_file("nwis_spatial_well_relationships_15108.csv", custom_path=csv_path)
        self._initialized = False

    def _ensure_loaded(self):
        if self._initialized:
            return
        # Ensure well_repository is loaded
        well_repository._ensure_loaded()
        self._initialized = True

    def get_nearby_wells(
        self,
        well_id: str,
        radius_km: float = 25.0,
        limit: int = 100
    ) -> NearbyWellsResponse:
        self._ensure_loaded()
        source_well = well_repository.get_well(well_id)
        if not source_well:
            raise ValueError(f"Well '{well_id}' does not exist in canonical registry.")

        if source_well.latitude is None or source_well.longitude is None:
            raise ValueError(f"Well '{well_id}' has no geographic coordinates.")

        canonical_wid = source_well.well_id
        src_lat = float(source_well.latitude)
        src_lon = float(source_well.longitude)
        requested_radius = float(radius_km)

        # 1. If PostgreSQL + PostGIS is connected and enabled, query PostGIS authoritative engine
        from ..repositories.factory import is_postgres_available, get_spatial_repository
        if is_postgres_available():
            try:
                pg_items = get_spatial_repository().get_nearby_wells(well_id=canonical_wid, radius_km=requested_radius, limit=limit)
                # Strict server-side verification on PostGIS output (Section 4)
                filtered_pg = [w for w in pg_items if w.distance_km <= requested_radius]
                if filtered_pg:
                    min_d = min((w.distance_km for w in filtered_pg), default=0.0)
                    max_d = max((w.distance_km for w in filtered_pg), default=0.0)
                    logger.info(
                        f"\nNearby Query (PostGIS)\n"
                        f"Well: {canonical_wid}\n"
                        f"Lat: {src_lat:.4f}\n"
                        f"Lon: {src_lon:.4f}\n"
                        f"Radius: {requested_radius} km\n"
                        f"Returned: {len(filtered_pg)}\n"
                        f"Minimum distance: {min_d} km\n"
                        f"Maximum distance: {max_d} km"
                    )
                    return NearbyWellsResponse(
                        source_well=source_well,
                        radius_km=requested_radius,
                        count=len(filtered_pg),
                        nearby_wells=filtered_pg,
                        center={
                            "well_id": source_well.well_id,
                            "latitude": source_well.latitude,
                            "longitude": source_well.longitude,
                        },
                        wells=filtered_pg,
                    )
            except Exception as e:
                logger.warning(f"PostGIS spatial query failed: {e}. Falling back to authoritative Haversine scan.")

        # 2. Authoritative Spatial Haversine Engine (Single Source of Truth)
        # Scan all distinct canonical wells directly from well_repository
        candidate_wells = []
        seen_ids = set()
        for wid, w in well_repository._lookup.items():
            if w.well_id not in seen_ids and w.well_id != canonical_wid:
                seen_ids.add(w.well_id)
                if w.latitude is not None and w.longitude is not None:
                    candidate_wells.append(w)

        total_candidates = len(candidate_wells)
        valid_candidates = []

        # High-performance bounding box pre-filter (1 deg lat ~ 111 km everywhere)
        lat_threshold = (requested_radius / 110.0) + 0.001

        for w in candidate_wells:
            # Fast latitude bounding box check
            if abs(w.latitude - src_lat) > lat_threshold:
                continue

            # Exact spherical Haversine distance
            dist = haversine_distance(src_lat, src_lon, w.latitude, w.longitude)
            dist_rounded = round(dist, 2)

            # STRICT SERVER-SIDE CONDITION (Section 4 & Section 9)
            # Never include any well where distance_km > radius_km
            if dist <= requested_radius and dist_rounded <= requested_radius:
                valid_candidates.append((dist, dist_rounded, w))

        # Sort strictly by distance ascending
        valid_candidates.sort(key=lambda x: x[0])
        total_filtered = len(valid_candidates)

        nearby_items: List[NearbyWellItem] = []
        for dist_raw, dist_rounded, w in valid_candidates[:limit]:
            # Double safety verification
            if dist_rounded > requested_radius:
                continue

            same_field = bool(w.field and source_well.field and w.field.strip().lower() == source_well.field.strip().lower())
            same_block = bool(w.block and source_well.block and w.block.strip().lower() == source_well.block.strip().lower())
            same_basin = bool(w.basin and source_well.basin and w.basin.strip().lower() == source_well.basin.strip().lower())

            if dist_raw < 5.0:
                p_class = "Immediate Offset"
            elif dist_raw < 15.0:
                p_class = "Local Field"
            elif dist_raw < 30.0:
                p_class = "Regional Block"
            else:
                p_class = "Basin Offset"

            item = NearbyWellItem(
                well_id=w.well_id,
                well_name=w.well_name,
                distance_km=dist_rounded,
                operator=w.operator or "Unknown",
                field=w.field or "Unknown",
                basin=w.basin or "Unknown",
                block=w.block or "Unknown",
                well_type=w.well_type or "Well",
                well_status=w.well_status or "Active",
                total_depth=w.total_depth,
                latitude=w.latitude,
                longitude=w.longitude,
                same_field=same_field,
                same_block=same_block,
                same_basin=same_basin,
                proximity_class=p_class,
            )
            nearby_items.append(item)

        # 3. Development logging & Strict Validation (Section 15)
        min_dist = min((item.distance_km for item in nearby_items), default=0.0)
        max_dist = max((item.distance_km for item in nearby_items), default=0.0)

        log_msg = (
            f"\n--- Nearby Query ---\n"
            f"Well: {canonical_wid}\n"
            f"Lat: {src_lat:.4f}\n"
            f"Lon: {src_lon:.4f}\n"
            f"Radius: {requested_radius} km\n\n"
            f"Candidates: {total_candidates}\n"
            f"After radius filter: {total_filtered}\n"
            f"Returned: {len(nearby_items)}\n\n"
            f"Minimum distance: {min_dist} km\n"
            f"Maximum distance: {max_dist} km\n"
            f"--------------------"
        )
        logger.info(log_msg)
        print(log_msg)

        # Strict validation: If maximum distance is greater than radius, fail query validation (Section 15)
        if max_dist > requested_radius:
            raise ValueError(
                f"Spatial integrity violation: Returned well distance {max_dist} km "
                f"exceeds requested radius {requested_radius} km!"
            )

        center_dict = {
            "well_id": well_id or source_well.well_id,
            "latitude": source_well.latitude,
            "longitude": source_well.longitude,
        }

        return NearbyWellsResponse(
            source_well=source_well,
            radius_km=requested_radius,
            count=len(nearby_items),
            nearby_wells=nearby_items,
            center=center_dict,
            wells=nearby_items,
        )


spatial_service = SpatialService()
