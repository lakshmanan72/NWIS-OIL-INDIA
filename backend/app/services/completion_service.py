from typing import Optional, Dict
import pandas as pd
from ..models.completion import WellCompletionRecord, WellCompletionResponse
from .data_path import resolve_data_file


class CompletionService:
    def __init__(self, csv_path: Optional[str] = None):
        self.csv_path = resolve_data_file("nwis_well_completion_wcr_15108.csv", custom_path=csv_path)
        self._df: Optional[pd.DataFrame] = None
        self._cache: Dict[str, WellCompletionRecord] = {}
        self._initialized = False

    def _ensure_loaded(self):
        if self._initialized:
            return

        df = pd.read_csv(self.csv_path, low_memory=False)
        df["well_id"] = df["well_id"].astype(str).str.strip().str.upper()
        self._df = df
        self._initialized = True

    def get_completion_by_well(self, well_id: str) -> WellCompletionResponse:
        self._ensure_loaded()
        wid = str(well_id).strip().upper()

        if wid in self._cache:
            return WellCompletionResponse(well_id=wid, completion=self._cache[wid])

        sub = self._df[self._df["well_id"] == wid]
        if sub.empty:
            # Check dynamic approved WCR documents
            try:
                from ...document_ai.document_repository import document_repository
                approved_docs = document_repository.list_documents(status="APPROVED")
                matched_wcr = next((d for d in approved_docs if d.well_id.upper() == wid and d.document_type == "WCR"), None)
                if matched_wcr:
                    extractions = document_repository.get_extractions_for_document(matched_wcr.document_id)
                    ext_map = {e.field: (e.edited_value if e.edited_value is not None else e.value) for e in extractions}
                    rec = WellCompletionRecord(
                        wcr_id=f"WCR-{matched_wcr.document_id}",
                        well_id=wid,
                        well_name=matched_wcr.matched_well_name or wid,
                        operator=str(ext_map.get("operator", "ONGC")),
                        field=str(ext_map.get("field", "Offshore")),
                        basin=str(ext_map.get("basin", "Western Offshore")),
                        block=str(ext_map.get("block", "")),
                        report_date=matched_wcr.approved_at or "2026-09-27",
                        completion_date=str(ext_map.get("completion_date")) if ext_map.get("completion_date") else "2026-09-27",
                        total_depth_m=float(ext_map.get("total_depth")) if ext_map.get("total_depth") else 3500.0,
                        measured_depth_m=float(ext_map.get("total_depth")) if ext_map.get("total_depth") else 3500.0,
                        true_vertical_depth_m=float(ext_map.get("total_depth")) if ext_map.get("total_depth") else 3500.0,
                        well_type="Exploration",
                        trajectory_type=str(ext_map.get("trajectory", "Vertical")),
                        completion_type="Cased Hole Perforated",
                        reservoir_formation=str(ext_map.get("formation", "Barail")),
                        reservoir_top_depth_m=3100.0,
                        reservoir_bottom_depth_m=3300.0,
                    )
                    self._cache[wid] = rec
                    return WellCompletionResponse(well_id=wid, completion=rec)
            except Exception:
                pass
            return WellCompletionResponse(well_id=wid, completion=None)

        row = sub.iloc[0]
        rec = WellCompletionRecord(
            wcr_id=str(row["wcr_id"]),
            well_id=str(row["well_id"]),
            well_name=str(row["well_name"]),
            operator=str(row["operator"]),
            field=str(row["field"]),
            basin=str(row["basin"]),
            block=str(row["block"]),
            report_date=str(row["report_date"]) if pd.notnull(row["report_date"]) else None,
            completion_date=str(row["completion_date"]) if pd.notnull(row["completion_date"]) else None,
            total_depth_m=float(row["total_depth_m"]) if pd.notnull(row["total_depth_m"]) else None,
            measured_depth_m=float(row["measured_depth_m"]) if pd.notnull(row["measured_depth_m"]) else None,
            true_vertical_depth_m=float(row["true_vertical_depth_m"]) if pd.notnull(row["true_vertical_depth_m"]) else None,
            well_type=str(row["well_type"]) if pd.notnull(row["well_type"]) else None,
            trajectory_type=str(row["trajectory_type"]) if pd.notnull(row["trajectory_type"]) else None,
            completion_type=str(row["completion_type"]) if pd.notnull(row["completion_type"]) else None,
            reservoir_formation=str(row["reservoir_formation"]) if pd.notnull(row["reservoir_formation"]) else None,
            reservoir_top_depth_m=float(row["reservoir_top_depth_m"]) if pd.notnull(row["reservoir_top_depth_m"]) else None,
            reservoir_bottom_depth_m=float(row["reservoir_bottom_depth_m"]) if pd.notnull(row["reservoir_bottom_depth_m"]) else None,
            reservoir_temperature_c=float(row["reservoir_temperature_c"]) if pd.notnull(row["reservoir_temperature_c"]) else None,
            reservoir_pressure_psi=float(row["reservoir_pressure_psi"]) if pd.notnull(row["reservoir_pressure_psi"]) else None,
            porosity_pct=float(row["porosity_pct"]) if pd.notnull(row["porosity_pct"]) else None,
            permeability_md=float(row["permeability_md"]) if pd.notnull(row["permeability_md"]) else None,
            water_saturation_pct=float(row["water_saturation_pct"]) if pd.notnull(row["water_saturation_pct"]) else None,
            oil_saturation_pct=float(row["oil_saturation_pct"]) if pd.notnull(row["oil_saturation_pct"]) else None,
            gas_saturation_pct=float(row["gas_saturation_pct"]) if pd.notnull(row["gas_saturation_pct"]) else None,
            net_pay_m=float(row["net_pay_m"]) if pd.notnull(row["net_pay_m"]) else None,
            gross_pay_m=float(row["gross_pay_m"]) if pd.notnull(row["gross_pay_m"]) else None,
            mud_type=str(row["mud_type"]) if pd.notnull(row["mud_type"]) else None,
            completion_fluid=str(row["completion_fluid"]) if pd.notnull(row["completion_fluid"]) else None,
            casing_size_in=str(row["casing_size_in"]) if pd.notnull(row["casing_size_in"]) else None,
            production_tubing_size_in=str(row["production_tubing_size_in"]) if pd.notnull(row["production_tubing_size_in"]) else None,
            cement_top_depth_m=float(row["cement_top_depth_m"]) if pd.notnull(row["cement_top_depth_m"]) else None,
            cement_bottom_depth_m=float(row["cement_bottom_depth_m"]) if pd.notnull(row["cement_bottom_depth_m"]) else None,
            perforation_top_depth_m=float(row["perforation_top_depth_m"]) if pd.notnull(row["perforation_top_depth_m"]) else None,
            perforation_bottom_depth_m=float(row["perforation_bottom_depth_m"]) if pd.notnull(row["perforation_bottom_depth_m"]) else None,
            perforation_interval_m=float(row["perforation_interval_m"]) if pd.notnull(row["perforation_interval_m"]) else None,
            completion_pressure_psi=float(row["completion_pressure_psi"]) if pd.notnull(row["completion_pressure_psi"]) else None,
            initial_oil_rate_bopd=float(row["initial_oil_rate_bopd"]) if pd.notnull(row["initial_oil_rate_bopd"]) else None,
            initial_gas_rate_mscfd=float(row["initial_gas_rate_mscfd"]) if pd.notnull(row["initial_gas_rate_mscfd"]) else None,
            initial_water_rate_bwpd=float(row["initial_water_rate_bwpd"]) if pd.notnull(row["initial_water_rate_bwpd"]) else None,
            production_test_duration_hr=float(row["production_test_duration_hr"]) if pd.notnull(row["production_test_duration_hr"]) else None,
            well_test_pressure_psi=float(row["well_test_pressure_psi"]) if pd.notnull(row["well_test_pressure_psi"]) else None,
            well_test_temperature_c=float(row["well_test_temperature_c"]) if pd.notnull(row["well_test_temperature_c"]) else None,
            formation_test_result=str(row["formation_test_result"]) if pd.notnull(row["formation_test_result"]) else None,
            completion_status=str(row["completion_status"]) if pd.notnull(row["completion_status"]) else None,
            completion_method=str(row["completion_method"]) if pd.notnull(row["completion_method"]) else None,
            artificial_lift=str(row["artificial_lift"]) if pd.notnull(row["artificial_lift"]) else None,
            wellhead_pressure_psi=float(row["wellhead_pressure_psi"]) if pd.notnull(row["wellhead_pressure_psi"]) else None,
            initial_production_status=str(row["initial_production_status"]) if pd.notnull(row["initial_production_status"]) else None,
            completion_problems=str(row["completion_problems"]) if pd.notnull(row["completion_problems"]) else None,
            workover_required=bool(row["workover_required"]) if pd.notnull(row["workover_required"]) else None,
            workover_type=str(row["workover_type"]) if pd.notnull(row["workover_type"]) else None,
            final_well_status=str(row["final_well_status"]) if pd.notnull(row["final_well_status"]) else None,
            wcr_summary=str(row["wcr_summary"]) if pd.notnull(row["wcr_summary"]) else None,
        )
        self._cache[wid] = rec
        return WellCompletionResponse(well_id=wid, completion=rec)


completion_service = CompletionService()
