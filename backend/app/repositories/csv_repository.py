import os
import json
import math
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
import pandas as pd

from ..models.well import CanonicalWell, WellMarker, NearbyWellItem
from .interfaces import (
    IWellRepository,
    ISpatialRepository,
    IGeologyRepository,
    IFormationRepository,
    IDrillingRepository,
    IMudLoggingRepository,
    IEventRepository,
    ICompletionRepository,
    IDocumentRepository,
    IRiskRepository,
    ITelemetryRepository,
    IAlertRepository,
    IAuditRepository,
)
from ..data_path import resolve_data_file


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2 +
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
        math.sin(dlon / 2.0) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# ============================================================
# 1. CSV WELL REPOSITORY
# ============================================================
class CsvWellRepository(IWellRepository):
    def __init__(self, csv_path: Optional[str] = None):
        self.csv_path = resolve_data_file("nwis_well_locations_15108_new.csv", custom_path=csv_path)
        self.columns_csv_path = resolve_data_file("nwis_wells_columns.csv")
        self._df: Optional[pd.DataFrame] = None
        self._lookup: Dict[str, CanonicalWell] = {}
        self._coordinates: Dict[str, Tuple[float, float]] = {}
        self._legacy_to_canonical: Dict[str, str] = {}
        self._name_to_canonical: Dict[str, str] = {}
        self._dynamic_wells_file = Path(__file__).resolve().parent.parent.parent / "data" / "documents" / "new_canonical_wells.json"
        self._initialized: bool = False
        self._ensure_loaded()

    def _ensure_loaded(self):
        if self._initialized:
            return

        df = pd.read_csv(self.csv_path, low_memory=False)
        df["well_id"] = df["well_id"].astype(str).str.strip()
        df["well_name"] = df["well_name"].astype(str).str.strip()
        df["operator"] = df["operator"].astype(str).str.strip()
        df["field"] = df["field"].astype(str).str.strip()
        df["basin"] = df["basin"].astype(str).str.strip()
        df["block"] = df["block"].astype(str).str.strip()
        df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
        df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
        df["total_depth"] = pd.to_numeric(df["total_depth"], errors="coerce")

        self._df = df
        self._lookup = {}
        self._coordinates = {}
        self._legacy_to_canonical = {}
        self._name_to_canonical = {}

        for _, row in df.iterrows():
            wid = str(row["well_id"])
            lat = float(row["latitude"])
            lon = float(row["longitude"])
            td = float(row["total_depth"]) if pd.notnull(row["total_depth"]) else None
            spud = str(row["spud_date"]) if pd.notnull(row["spud_date"]) else None
            comp = str(row["completion_date"]) if pd.notnull(row["completion_date"]) else None
            wtype = str(row["well_type"]) if pd.notnull(row["well_type"]) else None
            wstatus = str(row["well_status"]) if pd.notnull(row["well_status"]) else None
            traj = str(row["trajectory_type"]) if pd.notnull(row["trajectory_type"]) else None

            model = CanonicalWell(
                well_id=wid,
                well_name=str(row["well_name"]),
                operator=str(row["operator"]),
                field=str(row["field"]),
                basin=str(row["basin"]),
                block=str(row["block"]),
                latitude=lat,
                longitude=lon,
                spud_date=spud,
                completion_date=comp,
                total_depth=td,
                well_type=wtype,
                well_status=wstatus,
                trajectory_type=traj,
            )
            self._lookup[wid] = model
            self._lookup[wid.upper()] = model
            self._coordinates[wid] = (lat, lon)

        # Index legacy GIS baseline mapping
        if self.columns_csv_path and self.columns_csv_path.exists():
            try:
                import csv as _csv
                with open(self.columns_csv_path, mode="r", encoding="utf-8-sig") as f_col:
                    r_reader = _csv.DictReader(f_col)
                    for idx, r_row in enumerate(r_reader):
                        can_id = f"WELL-{idx + 1:06d}"
                        if can_id in self._lookup:
                            raw_fid = str(r_row.get("id", "")).strip()
                            clean_fid = raw_fid.replace("wells_all_public.fid--", "").strip()
                            raw_name = str(r_row.get("well_name", "")).strip()

                            if raw_fid:
                                self._legacy_to_canonical[raw_fid.lower()] = can_id
                            if clean_fid:
                                self._legacy_to_canonical[clean_fid.lower()] = can_id
                            if raw_name:
                                self._name_to_canonical[raw_name.lower()] = can_id
            except Exception:
                pass

        if self._dynamic_wells_file.exists():
            try:
                with open(self._dynamic_wells_file, "r", encoding="utf-8") as f:
                    dyn_wells = json.load(f)
                for w in dyn_wells:
                    wid = str(w["well_id"]).strip()
                    model = CanonicalWell(**w)
                    self._lookup[wid] = model
                    self._lookup[wid.upper()] = model
                    self._coordinates[wid] = (model.latitude, model.longitude)
            except Exception:
                pass

        self._initialized = True

    def get_all_wells(
        self,
        offset: int = 0,
        limit: int = 100,
        basin: Optional[str] = None,
        operator: Optional[str] = None,
        search: Optional[str] = None
    ) -> Tuple[int, List[CanonicalWell]]:
        self._ensure_loaded()
        wells = list(self._lookup.values())
        seen = set()
        unique_wells = []
        for w in wells:
            if w.well_id not in seen:
                seen.add(w.well_id)
                unique_wells.append(w)

        filtered = unique_wells
        if basin:
            b_low = basin.lower()
            filtered = [w for w in filtered if b_low in w.basin.lower()]
        if operator:
            op_low = operator.lower()
            filtered = [w for w in filtered if op_low in w.operator.lower()]
        if search:
            s_low = search.lower()
            filtered = [
                w for w in filtered
                if s_low in w.well_id.lower() or s_low in w.well_name.lower() or s_low in w.field.lower()
            ]

        total = len(filtered)
        paginated = filtered[offset : offset + limit]
        return total, paginated

    def get_well(self, well_id: str) -> Optional[CanonicalWell]:
        self._ensure_loaded()
        if not well_id:
            return None
        wid = str(well_id).strip()
        upper_id = wid.upper()

        # 1. Direct canonical lookup
        if upper_id in self._lookup:
            return self._lookup[upper_id]

        # 1b. Aliases & normalizations (e.g. WELL-01226 -> WELL-012265)
        if upper_id == "WELL-01226" and "WELL-012265" in self._lookup:
            return self._lookup["WELL-012265"]
        if upper_id == "WELL-00463" and "WELL-000463" in self._lookup:
            return self._lookup["WELL-000463"]
        if upper_id == "WELL-07905" and "WELL-007905" in self._lookup:
            return self._lookup["WELL-007905"]

        # Number-based zero-padding normalization
        if upper_id.startswith("WELL-"):
            raw_num = upper_id.replace("WELL-", "").strip()
            if raw_num.isdigit():
                padded_6 = f"WELL-{int(raw_num):06d}"
                if padded_6 in self._lookup:
                    return self._lookup[padded_6]

        # 2. Legacy GIS ID and source hash lookup
        low_id = wid.lower()
        if low_id in self._legacy_to_canonical:
            can_id = self._legacy_to_canonical[low_id]
            return self._lookup.get(can_id)

        if "fid--" in low_id:
            clean_hash = low_id.split("fid--")[-1].strip()
            if clean_hash in self._legacy_to_canonical:
                can_id = self._legacy_to_canonical[clean_hash]
                return self._lookup.get(can_id)

        # 3. Legacy well name lookup
        if low_id in self._name_to_canonical:
            can_id = self._name_to_canonical[low_id]
            return self._lookup.get(can_id)

        # 4. Identity resolver fallback
        try:
            from ..integrations.identity_resolver import well_identity_resolver
            resolved_id, status, _ = well_identity_resolver.resolve("generic", wid)
            if resolved_id and resolved_id in self._lookup:
                return self._lookup[resolved_id]
        except Exception:
            pass

        return None

    def search_wells(self, query: str, limit: int = 50) -> List[CanonicalWell]:
        self._ensure_loaded()
        q = str(query).strip().lower()
        if not q:
            return []

        results = []
        seen = set()
        for wid, model in self._lookup.items():
            if model.well_id in seen:
                continue
            if (
                q in model.well_id.lower()
                or q in model.well_name.lower()
                or q in model.operator.lower()
                or q in model.field.lower()
                or q in model.basin.lower()
            ):
                results.append(model)
                seen.add(model.well_id)
                if len(results) >= limit:
                    break
        return results

    def get_well_location(self, well_id: str) -> Optional[Tuple[float, float]]:
        self._ensure_loaded()
        wid = str(well_id).strip().upper()
        well = self._lookup.get(wid)
        if well:
            return (well.latitude, well.longitude)
        return None

    ORIGINAL_CANONICAL_SEED_COUNT: int = 15108

    def get_total_count(self) -> int:
        """
        Returns the dynamic authoritative count of all canonical wells in the active database.
        Never hardcoded.
        """
        self._ensure_loaded()
        seen = set()
        for wid in self._lookup.keys():
            if wid.startswith("WELL-") and not wid.endswith("-UPPER") and not wid.startswith("WELL-NEW-"):
                seen.add(wid)
        return len(seen)

    def create_canonical_well(self, well_data: Dict[str, Any], reviewer: str = "Engineer") -> CanonicalWell:
        self._ensure_loaded()
        wid = str(well_data.get("well_id", "")).strip().upper()
        if not wid:
            numeric_ids = []
            for existing_id in self._lookup.keys():
                if existing_id.startswith("WELL-") and not existing_id.endswith("-UPPER") and not existing_id.startswith("WELL-NEW-"):
                    raw_num = existing_id.replace("WELL-", "").strip()
                    if raw_num.isdigit():
                        numeric_ids.append(int(raw_num))
            max_id = max(numeric_ids) if numeric_ids else self.ORIGINAL_CANONICAL_SEED_COUNT
            wid = f"WELL-{max_id + 1:06d}"

        new_well = CanonicalWell(
            well_id=wid,
            well_name=str(well_data.get("well_name", wid)).strip(),
            operator=str(well_data.get("operator", "ONGC")).strip(),
            field=str(well_data.get("field", "Offshore Field")).strip(),
            basin=str(well_data.get("basin", "KG Basin")).strip(),
            block=str(well_data.get("block", "KG-DWN-98/2")).strip(),
            latitude=float(well_data.get("latitude", 16.5)),
            longitude=float(well_data.get("longitude", 82.2)),
            spud_date=str(well_data.get("spud_date", "2024-01-15")),
            completion_date=str(well_data.get("completion_date", "2024-06-30")),
            total_depth=float(well_data.get("total_depth", 3450.0)),
            well_type=str(well_data.get("well_type", "Development")),
            well_status=str(well_data.get("well_status", "Active")),
            trajectory_type=str(well_data.get("trajectory_type", "Vertical")),
        )

        self._lookup[wid] = new_well
        self._lookup[wid.upper()] = new_well
        self._coordinates[wid] = (new_well.latitude, new_well.longitude)

        # Persist to dynamic JSON
        self._dynamic_wells_file.parent.mkdir(parents=True, exist_ok=True)
        dyn_list = []
        if self._dynamic_wells_file.exists():
            try:
                with open(self._dynamic_wells_file, "r", encoding="utf-8") as f:
                    dyn_list = json.load(f)
            except Exception:
                dyn_list = []

        dyn_list = [w for w in dyn_list if str(w.get("well_id", "")).strip().upper() != wid]
        dyn_list.append(new_well.model_dump())
        with open(self._dynamic_wells_file, "w", encoding="utf-8") as f:
            json.dump(dyn_list, f, indent=2)

        return new_well

    def get_all_markers(self, force_reload: bool = False, include_new_wells: bool = True) -> List[WellMarker]:
        self._ensure_loaded()
        markers: List[WellMarker] = []
        resolved_file = self.columns_csv_path

        import csv
        with open(resolved_file, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader):
                lat_str = str(row.get("latitude", "")).strip()
                lon_str = str(row.get("longitude", "")).strip()
                if not lat_str or not lon_str:
                    continue
                try:
                    lat = float(lat_str)
                    lon = float(lon_str)
                except ValueError:
                    continue
                if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                    continue

                gid_raw = row.get("gid", 0)
                try:
                    gid_val = int(gid_raw)
                except (ValueError, TypeError):
                    gid_val = 0

                raw_fid = str(row.get("id", "")).strip()
                clean_fid = raw_fid.replace("wells_all_public.fid--", "").strip()
                can_id = f"WELL-{idx + 1:06d}"
                cw = self._lookup.get(can_id)

                if cw:
                    can_well_id = cw.well_id
                    status = "RESOLVED"
                    basin_val = cw.basin
                    field_val = cw.field
                    td_val = cw.total_depth
                else:
                    can_well_id = None
                    status = "UNRESOLVED"
                    basin_val = None
                    field_val = None
                    td_val = None

                markers.append(WellMarker(
                    id=raw_fid or can_id,
                    well_id=can_well_id,
                    legacy_id=raw_fid or None,
                    source_id=clean_fid or None,
                    identity_status=status,
                    gid=gid_val,
                    well_name=str(row.get("well_name", "")).strip(),
                    operator=str(row.get("operator", "")).strip(),
                    latitude=lat,
                    longitude=lon,
                    basin=basin_val,
                    field=field_val,
                    total_depth=td_val,
                ))

        if include_new_wells and self._dynamic_wells_file.exists():
            try:
                with open(self._dynamic_wells_file, "r", encoding="utf-8") as f:
                    dyn_wells = json.load(f)
                for idx, w in enumerate(dyn_wells):
                    wid = str(w["well_id"]).strip()
                    markers.append(WellMarker(
                        id=wid,
                        well_id=wid,
                        legacy_id=None,
                        source_id="DYNAMIC_WCR",
                        identity_status="RESOLVED",
                        gid=15108 + idx + 1,
                        well_name=w.get("well_name", wid),
                        operator=w.get("operator", "ONGC"),
                        latitude=float(w["latitude"]),
                        longitude=float(w["longitude"]),
                        basin=w.get("basin"),
                        field=w.get("field"),
                        total_depth=float(w["total_depth"]) if w.get("total_depth") is not None else None,
                        formation=str(w.get("formation") or w.get("field") or w.get("basin") or "").strip() or None,
                        is_new_well=True,
                        coordinate_source=w.get("coordinate_source", "WCR_DOCUMENT"),
                        coordinate_confidence=float(w.get("coordinate_confidence", 0.98)) if w.get("coordinate_confidence") is not None else 0.98,
                        source_document=w.get("source_document"),
                        uploaded_at=w.get("uploaded_at"),
                    ))
            except Exception:
                pass

        return markers


# ============================================================
# 2. CSV SPATIAL REPOSITORY
# ============================================================
class CsvSpatialRepository(ISpatialRepository):
    def __init__(self, well_repo: IWellRepository, csv_path: Optional[str] = None):
        self.well_repo = well_repo
        self.csv_path = resolve_data_file("nwis_spatial_well_relationships_15108.csv", custom_path=csv_path)
        self._precomputed: Dict[str, List[Dict[str, Any]]] = {}
        self._initialized = False

    def _ensure_loaded(self):
        if self._initialized:
            return
        df = pd.read_csv(self.csv_path, low_memory=False)
        df["source_well_id"] = df["source_well_id"].astype(str).str.strip().str.upper()
        df["nearby_well_id"] = df["nearby_well_id"].astype(str).str.strip().str.upper()
        df["distance_km"] = pd.to_numeric(df["distance_km"], errors="coerce")

        grouped = df.groupby("source_well_id")
        for src_id, group in grouped:
            self._precomputed[src_id] = group.to_dict(orient="records")
        self._initialized = True

    def get_nearby_wells(self, well_id: str, radius_km: float = 25.0, limit: int = 50) -> List[NearbyWellItem]:
        self._ensure_loaded()
        wid = str(well_id).strip().upper()
        source_well = self.well_repo.get_well(wid)
        if not source_well or source_well.latitude is None or source_well.longitude is None:
            return []

        src_lat = float(source_well.latitude)
        src_lon = float(source_well.longitude)
        requested_radius = float(radius_km)

        lat_threshold = (requested_radius / 110.0) + 0.001
        lookup_dict = getattr(self.well_repo, "_lookup", {})
        if lookup_dict:
            well_iter = lookup_dict.values()
        else:
            _, all_w = self.well_repo.get_all_wells(offset=0, limit=20000)
            well_iter = all_w

        candidates = []
        seen_ids = {source_well.well_id}
        for w in well_iter:
            if w.well_id in seen_ids:
                continue
            seen_ids.add(w.well_id)
            if w.latitude is None or w.longitude is None:
                continue
            if abs(w.latitude - src_lat) > lat_threshold:
                continue

            d = haversine_distance(src_lat, src_lon, w.latitude, w.longitude)
            d_round = round(d, 2)
            # STRICT server-side condition (Section 4 & Section 9)
            if d <= requested_radius and d_round <= requested_radius:
                candidates.append((d, d_round, w))

        candidates.sort(key=lambda x: x[0])
        nearby_items: List[NearbyWellItem] = []
        for d_raw, d_round, target_well in candidates[:limit]:
            if d_round > requested_radius:
                continue
            same_field = bool(target_well.field and source_well.field and target_well.field.strip().lower() == source_well.field.strip().lower())
            same_block = bool(target_well.block and source_well.block and target_well.block.strip().lower() == source_well.block.strip().lower())
            same_basin = bool(target_well.basin and source_well.basin and target_well.basin.strip().lower() == source_well.basin.strip().lower())

            if d_raw < 5.0:
                p_class = "Immediate Offset"
            elif d_raw < 15.0:
                p_class = "Local Field"
            elif d_raw < 30.0:
                p_class = "Regional Block"
            else:
                p_class = "Basin Offset"

            nearby_items.append(NearbyWellItem(
                well_id=target_well.well_id,
                well_name=target_well.well_name,
                distance_km=d_round,
                operator=target_well.operator or "Unknown",
                field=target_well.field or "Unknown",
                basin=target_well.basin or "Unknown",
                block=target_well.block or "Unknown",
                well_type=target_well.well_type or "Well",
                well_status=target_well.well_status or "Active",
                total_depth=target_well.total_depth,
                latitude=target_well.latitude,
                longitude=target_well.longitude,
                same_field=same_field,
                same_block=same_block,
                same_basin=same_basin,
                proximity_class=p_class,
            ))
        return nearby_items

    def get_nearest_wells(self, well_id: str, k: int = 10) -> List[NearbyWellItem]:
        return self.get_nearby_wells(well_id=well_id, radius_km=150.0, limit=k)


# ============================================================
# 3. CSV GEOLOGY REPOSITORY
# ============================================================
class CsvGeologyRepository(IGeologyRepository):
    def __init__(self, csv_path: Optional[str] = None):
        self.csv_path = resolve_data_file("nwis_well_geology_15108.csv", custom_path=csv_path)
        self._df: Optional[pd.DataFrame] = None

    def _ensure_loaded(self):
        if self._df is None:
            df = pd.read_csv(self.csv_path, low_memory=False)
            df["well_id"] = df["well_id"].astype(str).str.strip().str.upper()
            self._df = df

    def get_geology(self, well_id: str) -> List[Dict[str, Any]]:
        self._ensure_loaded()
        wid = str(well_id).strip().upper()
        subset = self._df[self._df["well_id"] == wid]
        return subset.to_dict(orient="records")


# ============================================================
# 4. CSV FORMATION REPOSITORY
# ============================================================
class CsvFormationRepository(IFormationRepository):
    def __init__(self, csv_path: Optional[str] = None):
        self.csv_path = resolve_data_file("nwis_formation_lithology_15108.csv", custom_path=csv_path)
        self._df: Optional[pd.DataFrame] = None

    def _ensure_loaded(self):
        if self._df is None:
            df = pd.read_csv(self.csv_path, low_memory=False)
            df["well_id"] = df["well_id"].astype(str).str.strip().str.upper()
            self._df = df

    def get_formations(self, well_id: str) -> List[Dict[str, Any]]:
        self._ensure_loaded()
        wid = str(well_id).strip().upper()
        subset = self._df[self._df["well_id"] == wid]
        return subset.to_dict(orient="records")

    def get_formation_at_depth(self, well_id: str, depth_md: float) -> Optional[Dict[str, Any]]:
        records = self.get_formations(well_id)
        for r in records:
            top = r.get("top_depth_md", 0.0)
            bot = r.get("bottom_depth_md", 99999.0)
            if top <= depth_md <= bot:
                return r
        return records[0] if records else None


# ============================================================
# 5. CSV DRILLING PARAMETERS REPOSITORY
# ============================================================
class CsvDrillingRepository(IDrillingRepository):
    def __init__(self, csv_path: Optional[str] = None):
        self.csv_path = resolve_data_file("nwis_daily_drilling_parameters_15108.csv", custom_path=csv_path)
        self._df: Optional[pd.DataFrame] = None

    def _ensure_loaded(self):
        if self._df is None:
            df = pd.read_csv(self.csv_path, low_memory=False)
            df["well_id"] = df["well_id"].astype(str).str.strip().str.upper()
            self._df = df

    def get_drilling_parameters(self, well_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        self._ensure_loaded()
        wid = str(well_id).strip().upper()
        subset = self._df[self._df["well_id"] == wid].head(limit)
        return subset.to_dict(orient="records")


# ============================================================
# 6. CSV MUD LOGGING REPOSITORY (CHUNKED / SERVER-SIDE)
# ============================================================
class CsvMudLoggingRepository(IMudLoggingRepository):
    def __init__(self, csv_path: Optional[str] = None):
        self.csv_path = resolve_data_file("nwis_mud_logging_15108_wells.csv", custom_path=csv_path)

    def get_mud_logging(
        self,
        well_id: str,
        depth_from: Optional[float] = None,
        depth_to: Optional[float] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        wid = str(well_id).strip().upper()
        results: List[Dict[str, Any]] = []

        # Read in chunks of 10,000 to conserve memory on 133MB dataset
        chunksize = 10000
        for chunk in pd.read_csv(self.csv_path, chunksize=chunksize, low_memory=False):
            chunk["well_id"] = chunk["well_id"].astype(str).str.strip().str.upper()
            sub = chunk[chunk["well_id"] == wid]
            if depth_from is not None:
                sub = sub[sub["depth_md"] >= depth_from]
            if depth_to is not None:
                sub = sub[sub["depth_md"] <= depth_to]
            if not sub.empty:
                results.extend(sub.to_dict(orient="records"))
                if len(results) >= limit:
                    break
        return results[:limit]


# ============================================================
# 7. CSV EVENT REPOSITORY
# ============================================================
class CsvEventRepository(IEventRepository):
    def __init__(self, csv_path: Optional[str] = None):
        self.csv_path = resolve_data_file("nwis_historical_drilling_events_15108.csv", custom_path=csv_path)
        self._df: Optional[pd.DataFrame] = None

    def _ensure_loaded(self):
        if self._df is None:
            df = pd.read_csv(self.csv_path, low_memory=False)
            df["well_id"] = df["well_id"].astype(str).str.strip().str.upper()
            self._df = df

    def get_historical_events(self, well_id: str, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        self._ensure_loaded()
        wid = str(well_id).strip().upper()
        subset = self._df[self._df["well_id"] == wid]
        if event_type:
            subset = subset[subset["event_type"].str.lower() == event_type.lower()]
        events = subset.to_dict(orient="records")

        # Include approved dynamic events
        try:
            from ...document_ai.document_repository import document_repository
            approved = document_repository.get_approved_events()
            for e in approved:
                if e.well_id.upper() == wid:
                    events.append({
                        "event_id": e.event_id,
                        "well_id": e.well_id,
                        "event_type": e.event_type,
                        "event_subtype": e.event_subtype,
                        "depth_md": e.depth_from,
                        "severity": e.severity,
                        "description": e.description,
                        "source_document_id": e.source_document_id,
                        "event_date": e.event_date,
                    })
        except Exception:
            pass
        return events


# ============================================================
# 8. CSV COMPLETION REPOSITORY
# ============================================================
class CsvCompletionRepository(ICompletionRepository):
    def __init__(self, csv_path: Optional[str] = None):
        self.csv_path = resolve_data_file("nwis_well_completion_wcr_15108.csv", custom_path=csv_path)
        self._df: Optional[pd.DataFrame] = None

    def _ensure_loaded(self):
        if self._df is None:
            df = pd.read_csv(self.csv_path, low_memory=False)
            df["well_id"] = df["well_id"].astype(str).str.strip().str.upper()
            self._df = df

    def get_completion_wcr(self, well_id: str) -> Optional[Dict[str, Any]]:
        self._ensure_loaded()
        wid = str(well_id).strip().upper()
        subset = self._df[self._df["well_id"] == wid]
        if not subset.empty:
            return subset.iloc[0].to_dict()
        return None


# ============================================================
# 9. CSV RISK RECOMMENDATIONS REPOSITORY
# ============================================================
class CsvRiskRepository(IRiskRepository):
    def __init__(self, csv_path: Optional[str] = None):
        self.csv_path = resolve_data_file("nwis_risk_recommendations.csv", custom_path=csv_path)
        self._df: Optional[pd.DataFrame] = None

    def _ensure_loaded(self):
        if self._df is None:
            df = pd.read_csv(self.csv_path, low_memory=False)
            df["well_id"] = df["well_id"].astype(str).str.strip().str.upper()
            self._df = df

    def get_risk_recommendations(self, well_id: str) -> List[Dict[str, Any]]:
        self._ensure_loaded()
        wid = str(well_id).strip().upper()
        subset = self._df[self._df["well_id"] == wid]
        return subset.to_dict(orient="records")


# ============================================================
# 10. CSV TELEMETRY REPOSITORY
# ============================================================
class CsvTelemetryRepository(ITelemetryRepository):
    def __init__(self):
        self._records: List[Dict[str, Any]] = []
        self._latest_by_well: Dict[str, Dict[str, Any]] = {}

    def record_telemetry(self, record: Dict[str, Any]) -> None:
        wid = str(record.get("well_id", "")).strip().upper()
        self._latest_by_well[wid] = record
        self._records.append(record)
        if len(self._records) > 2000:
            self._records = self._records[-2000:]

    def get_latest_telemetry(self, well_id: str) -> Optional[Dict[str, Any]]:
        wid = str(well_id).strip().upper()
        return self._latest_by_well.get(wid)

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
        subset = [r for r in self._records if str(r.get("well_id", "")).upper() == wid]
        if depth_from is not None:
            subset = [r for r in subset if r.get("depth_md", 0.0) >= depth_from]
        if depth_to is not None:
            subset = [r for r in subset if r.get("depth_md", 0.0) <= depth_to]
        return subset[-limit:]


# ============================================================
# 11. CSV ALERT REPOSITORY (DELEGATES TO JSON FILE)
# ============================================================
class CsvAlertRepository(IAlertRepository):
    def __init__(self, json_path: Optional[str] = None):
        if json_path:
            self.file_path = Path(json_path)
        else:
            self.file_path = Path(__file__).resolve().parent.parent.parent / "data" / "documents" / "active_alerts.json"
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _read_alerts(self) -> List[Dict[str, Any]]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_alerts(self, alerts: List[Dict[str, Any]]):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(alerts, f, indent=2)

    def create_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        alerts = self._read_alerts()
        alerts = [a for a in alerts if a.get("alert_id") != alert_data.get("alert_id")]
        alerts.insert(0, alert_data)
        self._save_alerts(alerts)
        return alert_data

    def get_alert(self, alert_id: str) -> Optional[Dict[str, Any]]:
        alerts = self._read_alerts()
        for a in alerts:
            if a.get("alert_id") == alert_id:
                return a
        return None

    def get_active_alerts(self, well_id: Optional[str] = None, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        alerts = self._read_alerts()
        res = alerts
        if well_id:
            w_up = well_id.strip().upper()
            res = [a for a in res if str(a.get("well_id", "")).upper() == w_up]
        if severity:
            s_up = severity.strip().upper()
            res = [a for a in res if str(a.get("severity", "")).upper() == s_up]
        return res

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str, note: str = "") -> Optional[Dict[str, Any]]:
        alerts = self._read_alerts()
        for a in alerts:
            if a.get("alert_id") == alert_id:
                a["status"] = "ACKNOWLEDGED"
                a["acknowledged_by"] = acknowledged_by
                a["acknowledged_at"] = datetime.now(timezone.utc).isoformat()
                a["acknowledgement_note"] = note
                self._save_alerts(alerts)
                return a
        return None

    def close_alert(self, alert_id: str, closed_by: str, note: str = "") -> Optional[Dict[str, Any]]:
        alerts = self._read_alerts()
        for a in alerts:
            if a.get("alert_id") == alert_id:
                a["status"] = "CLOSED"
                a["closed_by"] = closed_by
                a["closed_at"] = datetime.now(timezone.utc).isoformat()
                a["closure_note"] = note
                self._save_alerts(alerts)
                return a
        return None


# ============================================================
# 12. CSV AUDIT REPOSITORY
# ============================================================
class CsvAuditRepository(IAuditRepository):
    def __init__(self, json_path: Optional[str] = None):
        if json_path:
            self.file_path = Path(json_path)
        else:
            self.file_path = Path(__file__).resolve().parent.parent.parent / "data" / "documents" / "audit_logs.json"
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump([], f)

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
        record = {
            "id": int(datetime.now(timezone.utc).timestamp() * 1000),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "username": username,
            "role": role,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "well_id": well_id,
            "depth_md": depth_md,
            "old_value": old_value,
            "new_value": new_value,
            "reason": reason,
            "ip_address": ip_address,
            "request_id": request_id,
        }
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception:
            logs = []
        logs.insert(0, record)
        if len(logs) > 5000:
            logs = logs[:5000]
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2)

    def list_audit_logs(self, well_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception:
            logs = []
        if well_id:
            w_up = well_id.strip().upper()
            logs = [l for l in logs if str(l.get("well_id", "")).upper() == w_up]
        return logs[:limit]
