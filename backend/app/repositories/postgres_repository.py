import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, and_, or_, desc, func, text
from sqlalchemy.orm import Session

from ..models.well import CanonicalWell, WellMarker, NearbyWellItem
from ..db.session import get_session
from ..db.models import (
    Well,
    WellGeology,
    WellFormation,
    HistoricalEvent,
    DailyDrillingParameter,
    MudLogging,
    WellCompletionWCR,
    RiskRecommendation,
    TelemetryRecord,
    WellLiveState,
    Alert,
    AuditLog,
)
from .interfaces import (
    IWellRepository,
    ISpatialRepository,
    IGeologyRepository,
    IFormationRepository,
    IDrillingRepository,
    IMudLoggingRepository,
    IEventRepository,
    ICompletionRepository,
    IRiskRepository,
    ITelemetryRepository,
    IAlertRepository,
    IAuditRepository,
)
from .csv_repository import haversine_distance

logger = logging.getLogger("nwis.db.repo")


# ============================================================
# 1. POSTGRES WELL REPOSITORY
# ============================================================
class PostgresWellRepository(IWellRepository):
    def get_all_wells(
        self,
        offset: int = 0,
        limit: int = 100,
        basin: Optional[str] = None,
        operator: Optional[str] = None,
        search: Optional[str] = None
    ) -> Tuple[int, List[CanonicalWell]]:
        with get_session() as session:
            q = select(Well)
            if basin:
                q = q.where(Well.basin.ilike(f"%{basin}%"))
            if operator:
                q = q.where(Well.operator.ilike(f"%{operator}%"))
            if search:
                s_pat = f"%{search}%"
                q = q.where(
                    or_(
                        Well.well_id.ilike(s_pat),
                        Well.well_name.ilike(s_pat),
                        Well.field.ilike(s_pat),
                    )
                )

            # Count query
            count_q = select(func.count()).select_from(q.subquery())
            total = session.execute(count_q).scalar() or 0

            # Pagination query
            q = q.offset(offset).limit(limit)
            db_wells = session.scalars(q).all()

            results = [
                CanonicalWell(
                    well_id=w.well_id,
                    well_name=w.well_name,
                    operator=w.operator or "Unknown",
                    field=w.field or "Unknown",
                    basin=w.basin or "Unknown",
                    block=w.block or "Unknown",
                    latitude=w.latitude,
                    longitude=w.longitude,
                    spud_date=w.spud_date,
                    completion_date=w.completion_date,
                    total_depth=w.total_depth,
                    well_type=w.well_type or "Development",
                    well_status=w.status or "Active",
                    trajectory_type=w.trajectory_type or "Vertical",
                )
                for w in db_wells
            ]
            return total, results

    def get_well(self, well_id: str) -> Optional[CanonicalWell]:
        if not well_id:
            return None
        wid = str(well_id).strip().upper()
        with get_session() as session:
            w = session.scalars(select(Well).where(func.upper(Well.well_id) == wid)).first()
            if not w:
                w = session.scalars(select(Well).where(func.upper(Well.well_name) == wid)).first()
            if not w:
                try:
                    from ..integrations.identity_resolver import well_identity_resolver
                    resolved_id, status, _ = well_identity_resolver.resolve("generic", str(well_id).strip())
                    if resolved_id:
                        w = session.scalars(select(Well).where(func.upper(Well.well_id) == resolved_id.upper())).first()
                except Exception:
                    pass
            if not w:
                return None
            return CanonicalWell(
                well_id=w.well_id,
                well_name=w.well_name,
                operator=w.operator or "Unknown",
                field=w.field or "Unknown",
                basin=w.basin or "Unknown",
                block=w.block or "Unknown",
                latitude=w.latitude,
                longitude=w.longitude,
                spud_date=w.spud_date,
                completion_date=w.completion_date,
                total_depth=w.total_depth,
                well_type=w.well_type or "Development",
                well_status=w.status or "Active",
                trajectory_type=w.trajectory_type or "Vertical",
            )

    def search_wells(self, query: str, limit: int = 50) -> List[CanonicalWell]:
        q_str = str(query).strip()
        if not q_str:
            return []
        pat = f"%{q_str}%"
        with get_session() as session:
            stmt = select(Well).where(
                or_(
                    Well.well_id.ilike(pat),
                    Well.well_name.ilike(pat),
                    Well.operator.ilike(pat),
                    Well.field.ilike(pat),
                    Well.basin.ilike(pat),
                )
            ).limit(limit)
            db_wells = session.scalars(stmt).all()
            return [
                CanonicalWell(
                    well_id=w.well_id,
                    well_name=w.well_name,
                    operator=w.operator or "Unknown",
                    field=w.field or "Unknown",
                    basin=w.basin or "Unknown",
                    block=w.block or "Unknown",
                    latitude=w.latitude,
                    longitude=w.longitude,
                    spud_date=w.spud_date,
                    completion_date=w.completion_date,
                    total_depth=w.total_depth,
                    well_type=w.well_type or "Development",
                    well_status=w.status or "Active",
                    trajectory_type=w.trajectory_type or "Vertical",
                )
                for w in db_wells
            ]

    def get_well_location(self, well_id: str) -> Optional[Tuple[float, float]]:
        wid = str(well_id).strip().upper()
        with get_session() as session:
            w = session.scalars(select(Well).where(func.upper(Well.well_id) == wid)).first()
            if w:
                return (w.latitude, w.longitude)
            return None

    ORIGINAL_CANONICAL_SEED_COUNT: int = 15108

    def get_total_count(self) -> int:
        """
        Returns the dynamic authoritative count of all canonical wells in PostgreSQL.
        Never hardcoded.
        """
        with get_session() as session:
            return session.execute(select(func.count(Well.well_id))).scalar() or 0

    def create_canonical_well(self, well_data: Dict[str, Any], reviewer: str = "Engineer") -> CanonicalWell:
        wid = str(well_data.get("well_id", "")).strip().upper()
        with get_session() as session:
            if not wid:
                all_ids = session.scalars(select(Well.well_id).where(Well.well_id.like("WELL-%"))).all()
                numeric_ids = []
                for existing_id in all_ids:
                    raw_num = existing_id.replace("WELL-", "").strip()
                    if raw_num.isdigit():
                        numeric_ids.append(int(raw_num))
                max_id = max(numeric_ids) if numeric_ids else self.ORIGINAL_CANONICAL_SEED_COUNT
                wid = f"WELL-{max_id + 1:06d}"

            lat = float(well_data.get("latitude", 16.5))
            lon = float(well_data.get("longitude", 82.2))

            new_well = Well(
                well_id=wid,
                well_name=str(well_data.get("well_name", wid)).strip(),
                operator=str(well_data.get("operator", "ONGC")).strip(),
                field=str(well_data.get("field", "Offshore Field")).strip(),
                basin=str(well_data.get("basin", "KG Basin")).strip(),
                block=str(well_data.get("block", "KG-DWN-98/2")).strip(),
                latitude=lat,
                longitude=lon,
                spud_date=str(well_data.get("spud_date", "2024-01-15")),
                completion_date=str(well_data.get("completion_date", "2024-06-30")),
                total_depth=float(well_data.get("total_depth", 3450.0)),
                well_type=str(well_data.get("well_type", "Development")),
                status=str(well_data.get("well_status", "Active")),
                trajectory_type=str(well_data.get("trajectory_type", "Vertical")),
                source="WCR_DISCOVERED",
                is_canonical=True,
                is_new_well=True,
            )
            session.add(new_well)
            session.commit()

            return CanonicalWell(
                well_id=new_well.well_id,
                well_name=new_well.well_name,
                operator=new_well.operator,
                field=new_well.field,
                basin=new_well.basin,
                block=new_well.block,
                latitude=new_well.latitude,
                longitude=new_well.longitude,
                spud_date=new_well.spud_date,
                completion_date=new_well.completion_date,
                total_depth=new_well.total_depth,
                well_type=new_well.well_type,
                well_status=new_well.status,
                trajectory_type=new_well.trajectory_type,
            )

    def get_all_markers(self, force_reload: bool = False, include_new_wells: bool = True) -> List[WellMarker]:
        with get_session() as session:
            stmt = select(Well.well_id, Well.well_name, Well.operator, Well.latitude, Well.longitude, Well.basin, Well.field, Well.total_depth)
            if not include_new_wells:
                stmt = stmt.where(Well.is_new_well.is_(False))
            rows = session.execute(stmt).all()
            return [
                WellMarker(
                    id=str(r[0]),
                    well_id=str(r[0]),
                    legacy_id=None,
                    source_id=str(r[0]),
                    identity_status="RESOLVED",
                    gid=0,
                    well_name=str(r[1]),
                    operator=str(r[2] or "Unknown"),
                    latitude=float(r[3]),
                    longitude=float(r[4]),
                    basin=str(r[5]) if r[5] else None,
                    field=str(r[6]) if r[6] else None,
                    total_depth=float(r[7]) if r[7] is not None else None,
                )
                for r in rows
            ]


# ============================================================
# 2. POSTGRES SPATIAL REPOSITORY (PostGIS ST_DWithin + ST_Distance)
# ============================================================
class PostgresSpatialRepository(ISpatialRepository):
    def __init__(self, well_repo: IWellRepository):
        self.well_repo = well_repo

    def get_nearby_wells(self, well_id: str, radius_km: float = 25.0, limit: int = 50) -> List[NearbyWellItem]:
        wid = str(well_id).strip().upper()
        source_well = self.well_repo.get_well(wid)
        if not source_well:
            return []

        with get_session() as session:
            # Check if dialect is PostgreSQL and PostGIS is enabled
            dialect = session.bind.dialect.name if session.bind else "postgresql"
            if dialect == "postgresql":
                try:
                    # PostGIS query using ST_DWithin and ST_DistanceSphere / ST_Distance
                    radius_meters = radius_km * 1000.0
                    sql = text("""
                        SELECT 
                            w.well_id,
                            w.well_name,
                            w.operator,
                            w.field,
                            w.basin,
                            w.block,
                            w.well_type,
                            w.status,
                            w.total_depth,
                            w.latitude,
                            w.longitude,
                            ROUND((ST_Distance(
                                ST_SetSRID(ST_MakePoint(w.longitude, w.latitude), 4326)::geography,
                                ST_SetSRID(ST_MakePoint(:src_lon, :src_lat), 4326)::geography
                            ) / 1000.0)::numeric, 2) AS distance_km
                        FROM wells w
                        WHERE w.well_id != :src_id
                          AND ST_DWithin(
                              ST_SetSRID(ST_MakePoint(w.longitude, w.latitude), 4326)::geography,
                              ST_SetSRID(ST_MakePoint(:src_lon, :src_lat), 4326)::geography,
                              :radius_meters
                          )
                        ORDER BY distance_km ASC
                        LIMIT :limit_val
                    """)
                    res = session.execute(sql, {
                        "src_id": wid,
                        "src_lon": source_well.longitude,
                        "src_lat": source_well.latitude,
                        "radius_meters": radius_meters,
                        "limit_val": limit,
                    }).all()

                    nearby_items = []
                    for row in res:
                        dist_val = float(row[11])
                        # Strict server-side condition (Section 4)
                        if dist_val > radius_km:
                            continue
                        nearby_items.append(NearbyWellItem(
                            well_id=str(row[0]),
                            well_name=str(row[1]),
                            operator=str(row[2] or "Unknown"),
                            field=str(row[3] or "Unknown"),
                            basin=str(row[4] or "Unknown"),
                            block=str(row[5] or "Unknown"),
                            well_type=str(row[6] or "Development"),
                            well_status=str(row[7] or "Active"),
                            total_depth=float(row[8]) if row[8] is not None else None,
                            latitude=float(row[9]),
                            longitude=float(row[10]),
                            distance_km=dist_val,
                            same_field=bool(str(row[3] or "") == source_well.field),
                            same_block=bool(str(row[5] or "") == source_well.block),
                            same_basin=bool(str(row[4] or "") == source_well.basin),
                            proximity_class="Immediate Offset" if dist_val < 5.0 else ("Local Field" if dist_val < 15.0 else ("Regional Block" if dist_val < 30.0 else "Basin Offset")),
                        ))
                    return nearby_items
                except Exception as e:
                    logger.warning(f"PostGIS spatial query failed, falling back to Haversine: {e}")

            # Non-PostGIS or SQLite fallback (using Haversine across all wells)
            stmt = select(Well).where(Well.well_id != wid)
            candidates = session.scalars(stmt).all()
            distances = []
            for w in candidates:
                if w.latitude is None or w.longitude is None:
                    continue
                d = haversine_distance(source_well.latitude, source_well.longitude, w.latitude, w.longitude)
                if d <= radius_km and round(d, 2) <= radius_km:
                    distances.append((d, w))
            distances.sort(key=lambda x: x[0])
            return [
                NearbyWellItem(
                    well_id=w.well_id,
                    well_name=w.well_name,
                    operator=w.operator or "Unknown",
                    field=w.field or "Unknown",
                    basin=w.basin or "Unknown",
                    block=w.block or "Unknown",
                    well_type=w.well_type or "Development",
                    well_status=w.status or "Active",
                    total_depth=w.total_depth,
                    latitude=w.latitude,
                    longitude=w.longitude,
                    distance_km=round(d, 2),
                    same_field=bool(w.field == source_well.field),
                    same_block=bool(w.block == source_well.block),
                    same_basin=bool(w.basin == source_well.basin),
                    proximity_class="Immediate Offset" if d < 5.0 else ("Local Field" if d < 15.0 else ("Regional Block" if d < 30.0 else "Basin Offset")),
                )
                for d, w in distances[:limit]
            ]

    def get_nearest_wells(self, well_id: str, k: int = 10) -> List[NearbyWellItem]:
        return self.get_nearby_wells(well_id=well_id, radius_km=150.0, limit=k)


# ============================================================
# 3. POSTGRES GEOLOGY REPOSITORY
# ============================================================
class PostgresGeologyRepository(IGeologyRepository):
    def get_geology(self, well_id: str) -> List[Dict[str, Any]]:
        wid = str(well_id).strip().upper()
        with get_session() as session:
            stmt = select(WellGeology).where(func.upper(WellGeology.well_id) == wid)
            rows = session.scalars(stmt).all()
            return [
                {
                    "well_id": r.well_id,
                    "formation_name": r.formation_name,
                    "lithology": r.lithology,
                    "depth_from": r.depth_from,
                    "depth_to": r.depth_to,
                    "thickness": r.thickness,
                    "description": r.description,
                    "source": r.source,
                }
                for r in rows
            ]


# ============================================================
# 4. POSTGRES FORMATION REPOSITORY
# ============================================================
class PostgresFormationRepository(IFormationRepository):
    def get_formations(self, well_id: str) -> List[Dict[str, Any]]:
        wid = str(well_id).strip().upper()
        with get_session() as session:
            stmt = select(WellFormation).where(func.upper(WellFormation.well_id) == wid)
            rows = session.scalars(stmt).all()
            return [
                {
                    "well_id": r.well_id,
                    "formation_name": r.formation_name,
                    "top_depth_md": r.top_depth_md,
                    "bottom_depth_md": r.bottom_depth_md,
                    "age_era": r.age_era,
                    "permeability_class": r.permeability_class,
                    "source": r.source,
                }
                for r in rows
            ]

    def get_formation_at_depth(self, well_id: str, depth_md: float) -> Optional[Dict[str, Any]]:
        wid = str(well_id).strip().upper()
        with get_session() as session:
            stmt = select(WellFormation).where(
                and_(
                    func.upper(WellFormation.well_id) == wid,
                    WellFormation.top_depth_md <= depth_md,
                    WellFormation.bottom_depth_md >= depth_md,
                )
            ).order_by(WellFormation.top_depth_md.asc())
            r = session.scalars(stmt).first()
            if r:
                return {
                    "well_id": r.well_id,
                    "formation_name": r.formation_name,
                    "top_depth_md": r.top_depth_md,
                    "bottom_depth_md": r.bottom_depth_md,
                    "age_era": r.age_era,
                    "permeability_class": r.permeability_class,
                    "source": r.source,
                }
            # Fallback to closest
            fallback = session.scalars(select(WellFormation).where(func.upper(WellFormation.well_id) == wid)).first()
            if fallback:
                return {
                    "well_id": fallback.well_id,
                    "formation_name": fallback.formation_name,
                    "top_depth_md": fallback.top_depth_md,
                    "bottom_depth_md": fallback.bottom_depth_md,
                    "age_era": fallback.age_era,
                    "permeability_class": fallback.permeability_class,
                    "source": fallback.source,
                }
            return None


# ============================================================
# 5. POSTGRES DRILLING REPOSITORY
# ============================================================
class PostgresDrillingRepository(IDrillingRepository):
    def get_drilling_parameters(self, well_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        wid = str(well_id).strip().upper()
        with get_session() as session:
            stmt = select(DailyDrillingParameter).where(func.upper(DailyDrillingParameter.well_id) == wid).limit(limit)
            rows = session.scalars(stmt).all()
            return [
                {
                    "well_id": r.well_id,
                    "recorded_date": r.recorded_date,
                    "depth_md": r.depth_md,
                    "progress_m": r.progress_m,
                    "wob_klbf": r.wob_klbf,
                    "rpm": r.rpm,
                    "rop_m_hr": r.rop_m_hr,
                    "torque_kftlb": r.torque_kftlb,
                    "standpipe_pressure_psi": r.standpipe_pressure_psi,
                    "flow_rate_gpm": r.flow_rate_gpm,
                    "mud_weight_ppg": r.mud_weight_ppg,
                    "operation_summary": r.operation_summary,
                }
                for r in rows
            ]


# ============================================================
# 6. POSTGRES MUD LOGGING REPOSITORY (SERVER-SIDE FILTERED)
# ============================================================
class PostgresMudLoggingRepository(IMudLoggingRepository):
    def get_mud_logging(
        self,
        well_id: str,
        depth_from: Optional[float] = None,
        depth_to: Optional[float] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        wid = str(well_id).strip().upper()
        with get_session() as session:
            stmt = select(MudLogging).where(func.upper(MudLogging.well_id) == wid)
            if depth_from is not None:
                stmt = stmt.where(MudLogging.depth_md >= depth_from)
            if depth_to is not None:
                stmt = stmt.where(MudLogging.depth_md <= depth_to)
            stmt = stmt.order_by(MudLogging.depth_md.asc()).limit(limit)
            rows = session.scalars(stmt).all()
            return [
                {
                    "well_id": r.well_id,
                    "depth_md": r.depth_md,
                    "recorded_at": r.recorded_at,
                    "total_gas_units": r.total_gas_units,
                    "c1_methane_ppm": r.c1_methane_ppm,
                    "c2_ethane_ppm": r.c2_ethane_ppm,
                    "c3_propane_ppm": r.c3_propane_ppm,
                    "ic4_isobutane_ppm": r.ic4_isobutane_ppm,
                    "nc4_normalbutane_ppm": r.nc4_normalbutane_ppm,
                    "c5_pentane_ppm": r.c5_pentane_ppm,
                    "flow_show_pct": r.flow_show_pct,
                    "pit_volume_m3": r.pit_volume_m3,
                    "lithology_observed": r.lithology_observed,
                }
                for r in rows
            ]


# ============================================================
# 7. POSTGRES HISTORICAL EVENTS REPOSITORY
# ============================================================
class PostgresEventRepository(IEventRepository):
    def get_historical_events(self, well_id: str, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        wid = str(well_id).strip().upper()
        with get_session() as session:
            stmt = select(HistoricalEvent).where(func.upper(HistoricalEvent.well_id) == wid)
            if event_type:
                stmt = stmt.where(func.lower(HistoricalEvent.event_type) == event_type.lower())
            rows = session.scalars(stmt).all()
            return [
                {
                    "event_id": r.event_id,
                    "well_id": r.well_id,
                    "event_type": r.event_type,
                    "event_subtype": r.event_subtype,
                    "depth_md": r.depth_md,
                    "severity": r.severity,
                    "description": r.description,
                    "source_document_id": r.source_document_id,
                    "event_date": r.event_date,
                }
                for r in rows
            ]


# ============================================================
# 8. POSTGRES COMPLETION WCR REPOSITORY
# ============================================================
class PostgresCompletionRepository(ICompletionRepository):
    def get_completion_wcr(self, well_id: str) -> Optional[Dict[str, Any]]:
        wid = str(well_id).strip().upper()
        with get_session() as session:
            stmt = select(WellCompletionWCR).where(func.upper(WellCompletionWCR.well_id) == wid)
            r = session.scalars(stmt).first()
            if not r:
                return None
            return {
                "well_id": r.well_id,
                "document_id": r.document_id,
                "casing_size_inch": r.casing_size_inch,
                "casing_depth_m": r.casing_depth_m,
                "tubing_size_inch": r.tubing_size_inch,
                "perforation_interval_top_m": r.perforation_interval_top_m,
                "perforation_interval_bottom_m": r.perforation_interval_bottom_m,
                "reservoir_name": r.reservoir_name,
                "initial_production_oil_bopd": r.initial_production_oil_bopd,
                "initial_production_gas_mscfd": r.initial_production_gas_mscfd,
                "initial_reservoir_pressure_psi": r.initial_reservoir_pressure_psi,
                "completion_type": r.completion_type,
                "approval_status": r.approval_status,
            }


# ============================================================
# 9. POSTGRES RISK RECOMMENDATIONS REPOSITORY
# ============================================================
class PostgresRiskRepository(IRiskRepository):
    def get_risk_recommendations(self, well_id: str) -> List[Dict[str, Any]]:
        wid = str(well_id).strip().upper()
        with get_session() as session:
            stmt = select(RiskRecommendation).where(func.upper(RiskRecommendation.well_id) == wid)
            rows = session.scalars(stmt).all()
            return [
                {
                    "risk_id": r.risk_id,
                    "well_id": r.well_id,
                    "hazard_type": r.hazard_type,
                    "risk_score": r.risk_score,
                    "risk_level": r.risk_level,
                    "predicted_event": r.predicted_event,
                    "confidence": r.confidence,
                    "recommended_action": r.recommended_action,
                    "supporting_event_id": r.supporting_event_id,
                    "model_version": r.model_version,
                }
                for r in rows
            ]


# ============================================================
# 10. POSTGRES TELEMETRY REPOSITORY
# ============================================================
class PostgresTelemetryRepository(ITelemetryRepository):
    def record_telemetry(self, record: Dict[str, Any]) -> None:
        try:
            with get_session() as session:
                wid = str(record.get("well_id", "")).strip().upper()
                ts = record.get("timestamp")
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except Exception:
                        ts = datetime.now(timezone.utc)
                elif not isinstance(ts, datetime):
                    ts = datetime.now(timezone.utc)

                entry = TelemetryRecord(
                    well_id=wid,
                    timestamp=ts,
                    depth_md=float(record.get("depth_md", 0.0)),
                    rop=record.get("rop_m_hr"),
                    wob=record.get("wob_klbf"),
                    rpm=record.get("rpm"),
                    torque=record.get("torque_kftlb"),
                    spp=record.get("standpipe_pressure_psi"),
                    mud_flow_in=record.get("mud_flow_in_lpm"),
                    mud_flow_out=record.get("mud_flow_out_lpm"),
                    gas=record.get("gas_units"),
                    source=str(record.get("source", "eRTMAC")),
                    quality_status=str(record.get("quality_status", "GOOD")),
                )
                session.add(entry)

                # Upsert well_live_state
                state = session.get(WellLiveState, wid)
                if not state:
                    state = WellLiveState(
                        well_id=wid,
                        latest_depth_md=float(record.get("depth_md", 0.0)),
                        connection_status="LIVE",
                        last_seen_timestamp=ts,
                        latest_telemetry_json=record,
                    )
                    session.add(state)
                else:
                    state.latest_depth_md = float(record.get("depth_md", 0.0))
                    state.connection_status = "LIVE"
                    state.last_seen_timestamp = ts
                    state.latest_telemetry_json = record

                session.commit()
        except Exception as e:
            logger.warning(f"Telemetry record persistence failed: {e}")

    def get_latest_telemetry(self, well_id: str) -> Optional[Dict[str, Any]]:
        wid = str(well_id).strip().upper()
        with get_session() as session:
            state = session.get(WellLiveState, wid)
            if state and state.latest_telemetry_json:
                return state.latest_telemetry_json
            stmt = select(TelemetryRecord).where(func.upper(TelemetryRecord.well_id) == wid).order_by(TelemetryRecord.timestamp.desc())
            r = session.scalars(stmt).first()
            if r:
                return {
                    "well_id": r.well_id,
                    "timestamp": r.timestamp.isoformat(),
                    "depth_md": r.depth_md,
                    "rop_m_hr": r.rop,
                    "wob_klbf": r.wob,
                    "rpm": r.rpm,
                    "torque_kftlb": r.torque,
                    "standpipe_pressure_psi": r.spp,
                    "mud_flow_in_lpm": r.mud_flow_in,
                    "mud_flow_out_lpm": r.mud_flow_out,
                    "gas_units": r.gas,
                }
            return None

    def get_telemetry_range(
        self,
        well_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        depth_from: Optional[float] = None,
        depth_to: Optional[float] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        wid = str(well_id).strip().upper()
        with get_session() as session:
            stmt = select(TelemetryRecord).where(func.upper(TelemetryRecord.well_id) == wid)
            if start_time:
                stmt = stmt.where(TelemetryRecord.timestamp >= start_time)
            if end_time:
                stmt = stmt.where(TelemetryRecord.timestamp <= end_time)
            if depth_from is not None:
                stmt = stmt.where(TelemetryRecord.depth_md >= depth_from)
            if depth_to is not None:
                stmt = stmt.where(TelemetryRecord.depth_md <= depth_to)
            stmt = stmt.order_by(TelemetryRecord.timestamp.desc()).limit(limit)
            rows = session.scalars(stmt).all()
            return [
                {
                    "well_id": r.well_id,
                    "timestamp": r.timestamp.isoformat(),
                    "depth_md": r.depth_md,
                    "rop_m_hr": r.rop,
                    "wob_klbf": r.wob,
                    "rpm": r.rpm,
                    "torque_kftlb": r.torque,
                    "standpipe_pressure_psi": r.spp,
                    "mud_flow_in_lpm": r.mud_flow_in,
                    "mud_flow_out_lpm": r.mud_flow_out,
                    "gas_units": r.gas,
                }
                for r in rows
            ]


# ============================================================
# 11. POSTGRES ALERT REPOSITORY
# ============================================================
class PostgresAlertRepository(IAlertRepository):
    def create_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        aid = alert_data.get("alert_id")
        wid = str(alert_data.get("well_id", "")).strip().upper()
        try:
            with get_session() as session:
                existing = session.scalars(select(Alert).where(Alert.alert_id == aid)).first()
                if existing:
                    existing.depth_md = float(alert_data.get("depth_md", existing.depth_md))
                    existing.severity = str(alert_data.get("severity", existing.severity))
                    existing.status = str(alert_data.get("status", existing.status))
                    existing.message = str(alert_data.get("message", existing.message))
                else:
                    new_alert = Alert(
                        alert_id=aid,
                        well_id=wid,
                        depth_md=float(alert_data.get("depth_md", 0.0)),
                        alert_type=str(alert_data.get("hazard", alert_data.get("alert_type", "ANOMALY"))),
                        severity=str(alert_data.get("severity", "MEDIUM")),
                        status=str(alert_data.get("status", "ACTIVE")),
                        signal_source=str(alert_data.get("signal_source", "TELEMETRY")),
                        model_source=str(alert_data.get("model_source", "Phase3.1")),
                        message=str(alert_data.get("message", "")),
                        evidence_ids=alert_data.get("evidence_ids", []),
                        live_ids=alert_data.get("live_ids", []),
                    )
                    session.add(new_alert)
                session.commit()
        except Exception as e:
            logger.warning(f"Postgres alert persistence failed: {e}")
        return alert_data

    def get_alert(self, alert_id: str) -> Optional[Dict[str, Any]]:
        with get_session() as session:
            a = session.scalars(select(Alert).where(Alert.alert_id == alert_id)).first()
            if not a:
                return None
            return {
                "alert_id": a.alert_id,
                "well_id": a.well_id,
                "depth_md": a.depth_md,
                "alert_type": a.alert_type,
                "severity": a.severity,
                "status": a.status,
                "message": a.message,
                "detected_at": a.detected_at.isoformat() if a.detected_at else None,
                "acknowledged_by": a.acknowledged_by,
                "closed_by": a.closed_by,
                "evidence_ids": a.evidence_ids,
                "live_ids": a.live_ids,
            }

    def get_active_alerts(self, well_id: Optional[str] = None, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        with get_session() as session:
            stmt = select(Alert).order_by(Alert.created_at.desc())
            if well_id:
                stmt = stmt.where(func.upper(Alert.well_id) == well_id.strip().upper())
            if severity:
                stmt = stmt.where(Alert.severity == severity.strip().upper())
            rows = session.scalars(stmt).all()
            return [
                {
                    "alert_id": a.alert_id,
                    "well_id": a.well_id,
                    "depth_md": a.depth_md,
                    "alert_type": a.alert_type,
                    "hazard": a.alert_type,
                    "severity": a.severity,
                    "status": a.status,
                    "message": a.message,
                    "detected_at": a.detected_at.isoformat() if a.detected_at else None,
                    "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
                    "closed_at": a.closed_at.isoformat() if a.closed_at else None,
                    "acknowledged_by": a.acknowledged_by,
                    "closed_by": a.closed_by,
                    "acknowledgement_note": a.acknowledgement_note,
                    "closure_note": a.closure_note,
                    "evidence_ids": a.evidence_ids or [],
                    "live_ids": a.live_ids or [],
                }
                for a in rows
            ]

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str, note: str = "") -> Optional[Dict[str, Any]]:
        with get_session() as session:
            a = session.scalars(select(Alert).where(Alert.alert_id == alert_id)).first()
            if not a:
                return None
            a.status = "ACKNOWLEDGED"
            a.acknowledged_by = acknowledged_by
            a.acknowledged_at = datetime.now(timezone.utc)
            a.acknowledgement_note = note
            session.commit()
            return {
                "alert_id": a.alert_id,
                "well_id": a.well_id,
                "status": a.status,
                "acknowledged_by": a.acknowledged_by,
                "acknowledged_at": a.acknowledged_at.isoformat(),
            }

    def close_alert(self, alert_id: str, closed_by: str, note: str = "") -> Optional[Dict[str, Any]]:
        with get_session() as session:
            a = session.scalars(select(Alert).where(Alert.alert_id == alert_id)).first()
            if not a:
                return None
            a.status = "CLOSED"
            a.closed_by = closed_by
            a.closed_at = datetime.now(timezone.utc)
            a.closure_note = note
            session.commit()
            return {
                "alert_id": a.alert_id,
                "well_id": a.well_id,
                "status": a.status,
                "closed_by": a.closed_by,
                "closed_at": a.closed_at.isoformat(),
            }


# ============================================================
# 12. POSTGRES AUDIT REPOSITORY
# ============================================================
class PostgresAuditRepository(IAuditRepository):
    def record_audit(
        self,
        username: str,
        role: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        well_id: Optional[str] = None,
        depth_md: Optional[float] = None,
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> None:
        try:
            with get_session() as session:
                log_entry = AuditLog(
                    username=username,
                    user_id=user_id,
                    role=role,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    well_id=well_id,
                    depth_md=depth_md,
                    old_value=old_value,
                    new_value=new_value,
                    reason=reason,
                    ip_address=ip_address,
                    request_id=request_id,
                )
                session.add(log_entry)
                session.commit()
        except Exception as e:
            logger.warning(f"Postgres audit logging failed: {e}")

    def list_audit_logs(self, well_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        with get_session() as session:
            stmt = select(AuditLog).order_by(AuditLog.timestamp.desc())
            if well_id:
                stmt = stmt.where(func.upper(AuditLog.well_id) == well_id.strip().upper())
            stmt = stmt.limit(limit)
            rows = session.scalars(stmt).all()
            return [
                {
                    "id": r.id,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                    "user_id": r.user_id,
                    "username": r.username,
                    "role": r.role,
                    "action": r.action,
                    "resource_type": r.resource_type,
                    "resource_id": r.resource_id,
                    "well_id": r.well_id,
                    "depth_md": r.depth_md,
                    "old_value": r.old_value,
                    "new_value": r.new_value,
                    "reason": r.reason,
                    "ip_address": r.ip_address,
                    "request_id": r.request_id,
                }
                for r in rows
            ]
