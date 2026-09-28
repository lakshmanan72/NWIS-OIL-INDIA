from typing import Optional, List, Dict, Any
from ..models.offset_intelligence import OffsetHistoricalEvidence, OffsetIntelligenceResponse
from ..repositories.well_repository import well_repository
from .spatial_service import spatial_service
from .historical_event_service import historical_event_service
from .formation_service import formation_service
from .drilling_service import drilling_service


class OffsetIntelligenceService:
    def get_offset_intelligence(
        self,
        well_id: str,
        current_depth: Optional[float] = None,
        current_formation: Optional[str] = None,
        radius_km: float = 25.0,
        depth_window_m: float = 200.0
    ) -> OffsetIntelligenceResponse:
        wid = str(well_id).strip().upper()
        current_well = well_repository.get_well(wid)
        if not current_well:
            raise ValueError(f"Well '{well_id}' does not exist in canonical registry.")

        # Determine reference depth if not provided
        if current_depth is None or current_depth <= 0:
            # Check drilling parameters
            drill_resp = drilling_service.get_drilling_parameters_by_well(wid)
            if drill_resp.records:
                current_depth = round(float(drill_resp.records[-1].depth_md), 1)
            elif current_well.total_depth and current_well.total_depth > 0:
                current_depth = round(float(current_well.total_depth * 0.75), 1)
            else:
                current_depth = 2500.0

        # Determine reference formation if not provided
        if not current_formation or not current_formation.strip():
            form_resp = formation_service.get_formations_by_well(wid)
            for f in form_resp.formations:
                if f.depth_from_md <= current_depth <= f.depth_to_md:
                    current_formation = f.formation_name
                    break
            if not current_formation and form_resp.formations:
                current_formation = form_resp.formations[0].formation_name

        # Find nearby wells
        nearby_resp = spatial_service.get_nearby_wells(wid, radius_km=radius_km, limit=25)
        nearby_wells = nearby_resp.nearby_wells

        # Retrieve and correlate historical drilling events from offset wells
        all_correlated_events: List[OffsetHistoricalEvidence] = []
        formation_matches: List[OffsetHistoricalEvidence] = []
        depth_matches: List[OffsetHistoricalEvidence] = []
        event_type_counts: Dict[str, int] = {}
        supporting_well_ids = set()

        norm_target_formation = current_formation.strip().lower() if current_formation else ""

        for offset in nearby_wells:
            offset_events_resp = historical_event_service.get_events_by_well(offset.well_id)
            for evt in offset_events_resp.events:
                depth_diff = round(abs(evt.depth_md - current_depth), 1)
                is_depth_match = (depth_diff <= depth_window_m)
                norm_evt_formation = evt.formation.strip().lower()
                is_form_match = bool(norm_target_formation and norm_target_formation in norm_evt_formation or norm_evt_formation in norm_target_formation)

                # Keep if matches depth window or formation
                if is_depth_match or is_form_match:
                    evidence = OffsetHistoricalEvidence(
                        event_id=evt.event_id,
                        well_id=offset.well_id,
                        well_name=offset.well_name,
                        distance_km=offset.distance_km,
                        event_type=evt.event_type,
                        severity=evt.severity,
                        depth_md=evt.depth_md,
                        depth_difference_m=depth_diff,
                        formation=evt.formation,
                        formation_match=is_form_match,
                        description=evt.description,
                        action_taken=evt.action_taken,
                        outcome=evt.outcome,
                        npt_hours=evt.npt_hours,
                        source_document=evt.source_document,
                        page_number=evt.page_number,
                        source_dataset="nwis_historical_drilling_events_15108.csv"
                    )
                    all_correlated_events.append(evidence)
                    supporting_well_ids.add(offset.well_id)

                    event_type_counts[evt.event_type] = event_type_counts.get(evt.event_type, 0) + 1

                    if is_depth_match:
                        depth_matches.append(evidence)
                    if is_form_match:
                        formation_matches.append(evidence)

        # Sort correlated events by composite relevance: formation match first, then depth difference, then distance
        all_correlated_events.sort(key=lambda e: (not e.formation_match, e.depth_difference_m, e.distance_km or 999.0))
        depth_matches.sort(key=lambda e: e.depth_difference_m)
        formation_matches.sort(key=lambda e: (e.depth_difference_m, e.distance_km or 999.0))

        # Calculate historical interval
        if all_correlated_events:
            min_d = min(e.depth_md for e in all_correlated_events)
            max_d = max(e.depth_md for e in all_correlated_events)
            interval_str = f"{min_d:.0f} m – {max_d:.0f} m"
            hazard_list = ", ".join(list(event_type_counts.keys())[:3])
            alert_str = (
                f"⚠ Historical events ({hazard_list}) detected near current depth ({current_depth:.0f} m) "
                f"across {len(supporting_well_ids)} offset wells."
            )
        else:
            interval_str = "None"
            alert_str = f"No historical hazard events detected within ±{depth_window_m:.0f} m or {current_formation}."

        return OffsetIntelligenceResponse(
            current_well=current_well,
            current_depth=current_depth,
            current_formation=current_formation,
            historical_event_interval=interval_str,
            nearby_wells_count=len(nearby_wells),
            nearby_wells=nearby_wells,
            historical_events_count=len(all_correlated_events),
            historical_events=all_correlated_events,
            formation_matches=formation_matches,
            depth_matches=depth_matches,
            event_matches=event_type_counts,
            supporting_wells=sorted(list(supporting_well_ids)),
            alert_summary=alert_str
        )


offset_intelligence_service = OffsetIntelligenceService()
