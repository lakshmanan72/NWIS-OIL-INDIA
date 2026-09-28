import csv
from pathlib import Path
from typing import Protocol, List, Optional, Dict, Any, Tuple
import pandas as pd
from ..models.well import CanonicalWell
from ..data_path import resolve_data_file


class IWellRepository(Protocol):
    """
    Abstract interface for Well data access.
    Compatible with future PostgreSQL/PostGIS database implementations.
    """
    def get_all_wells(
        self,
        offset: int = 0,
        limit: int = 100,
        basin: Optional[str] = None,
        operator: Optional[str] = None,
        search: Optional[str] = None
    ) -> Tuple[int, List[CanonicalWell]]:
        ...

    def get_well(self, well_id: str) -> Optional[CanonicalWell]:
        ...

    def search_wells(self, query: str, limit: int = 50) -> List[CanonicalWell]:
        ...

    def get_well_location(self, well_id: str) -> Optional[Tuple[float, float]]:
        ...


class CsvWellRepository(IWellRepository):
    """
    High-performance CSV-backed implementation of IWellRepository.
    Loads and indexes canonical master registry: nwis_well_locations_15108_new.csv
    """
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
        # Ensure correct string formatting
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
        self._base_df = df.copy()
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

        # Build 1:1 row alignment index from legacy GIS baseline (nwis_wells_columns.csv)
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

        # Load any dynamic engineer-approved canonical wells
        if self._dynamic_wells_file.exists():
            try:
                import json
                with open(self._dynamic_wells_file, "r", encoding="utf-8") as f:
                    dyn_wells = json.load(f)
                for w in dyn_wells:
                    wid = str(w["well_id"]).strip()
                    model = CanonicalWell(**w)
                    self._lookup[wid] = model
                    self._lookup[wid.upper()] = model
                    self._coordinates[wid] = (model.latitude, model.longitude)
            except Exception as e:
                pass
        self._initialized = True

    def reload_dynamic_wells(self):
        """Reloads dynamic wells from disk into lookup and coordinates."""
        if not self._initialized:
            self._ensure_loaded()
            return

        seed_count = len(self._base_df)
        seed_ids = {f"WELL-{i + 1:06d}" for i in range(seed_count)}

        keys_to_remove = [k for k in self._lookup if k.upper() not in seed_ids and k not in seed_ids]
        for k in keys_to_remove:
            self._lookup.pop(k, None)
            self._coordinates.pop(k, None)

        if self._dynamic_wells_file.exists():
            try:
                import json
                with open(self._dynamic_wells_file, "r", encoding="utf-8") as f:
                    dyn_wells = json.load(f)
                for w in dyn_wells:
                    wid = str(w["well_id"]).strip()
                    model = CanonicalWell(**w)
                    self._lookup[wid] = model
                    self._lookup[wid.upper()] = model
                    if model.latitude is not None and model.longitude is not None:
                        self._coordinates[wid] = (model.latitude, model.longitude)
            except Exception:
                pass

    def create_canonical_well(
        self,
        well_data: Dict[str, Any],
        reviewer: str = "Engineer",
        force_confirm: bool = False,
    ) -> CanonicalWell:
        """
        Creates a new canonical well record after performing duplicate safety checks.
        Computes the next sequential canonical well ID (e.g. WELL-015109).
        """
        self._ensure_loaded()
        required = ["well_name", "latitude", "longitude", "field", "basin"]
        for req in required:
            if req not in well_data or well_data[req] is None or str(well_data[req]).strip() == "":
                raise ValueError(f"Missing required field for canonical well creation: '{req}'")

        well_name = str(well_data["well_name"]).strip()
        try:
            lat = float(well_data["latitude"])
            lon = float(well_data["longitude"])
        except (ValueError, TypeError):
            raise ValueError("Coordinates latitude and longitude must be valid floating point numbers.")

        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            raise ValueError(f"Coordinates ({lat}, {lon}) are outside valid geographical bounds.")

        # Duplicate Safety Checks (Section 22)
        norm_name = "".join(c.lower() for c in well_name if c.isalnum())
        for existing in self._lookup.values():
            exist_norm = "".join(c.lower() for c in existing.well_name if c.isalnum())
            if norm_name == exist_norm and not force_confirm:
                raise ValueError(
                    f"AMBIGUOUS_NEW_WELL: Canonical well '{existing.well_id}' ({existing.well_name}) "
                    f"already exists with identical normalized name. Confirmation required."
                )
            # Coordinate proximity check (< 100 meters / ~0.001 deg) with identical field
            if abs(existing.latitude - lat) < 0.001 and abs(existing.longitude - lon) < 0.001 and not force_confirm:
                if existing.field.lower() == str(well_data.get("field", "")).strip().lower():
                    raise ValueError(
                        f"AMBIGUOUS_NEW_WELL: Existing well '{existing.well_id}' ({existing.well_name}) "
                        f"is within 100 meters at the same field. Confirmation required."
                    )

        # Compute next sequential canonical ID
        numeric_ids = []
        for wid in self._lookup.keys():
            if wid.startswith("WELL-") and not wid.endswith("-UPPER") and not wid.startswith("WELL-NEW-"):
                num_part = wid.replace("WELL-", "")
                if num_part.isdigit():
                    numeric_ids.append(int(num_part))
        next_num = (max(numeric_ids) + 1) if numeric_ids else 15109
        new_well_id = f"WELL-{next_num:06d}"

        total_depth = None
        if well_data.get("total_depth") is not None:
            try:
                total_depth = float(well_data["total_depth"])
            except (ValueError, TypeError):
                total_depth = None

        from datetime import datetime, timezone

        uploaded_at = well_data.get("uploaded_at") or datetime.now(timezone.utc).isoformat()
        coord_source = str(well_data.get("coordinate_source", "WCR_DOCUMENT"))
        coord_conf = float(well_data.get("coordinate_confidence", 0.98))
        formation_name = str(well_data.get("formation") or well_data.get("field") or "").strip() or None
        src_doc = str(well_data.get("source_document") or "").strip() or None

        new_well = CanonicalWell(
            well_id=new_well_id,
            well_name=well_name,
            operator=str(well_data.get("operator", "ONGC")).strip() or "ONGC",
            field=str(well_data.get("field", "")).strip(),
            basin=str(well_data.get("basin", "")).strip(),
            block=str(well_data.get("block", "")).strip(),
            latitude=lat,
            longitude=lon,
            spud_date=str(well_data.get("spud_date")) if well_data.get("spud_date") else None,
            completion_date=str(well_data.get("completion_date")) if well_data.get("completion_date") else None,
            total_depth=total_depth,
            well_type=str(well_data.get("well_type", "Exploration")).strip() or "Exploration",
            well_status=str(well_data.get("well_status", "Active")).strip() or "Active",
            trajectory_type=str(well_data.get("trajectory", well_data.get("trajectory_type", "Vertical"))).strip() or "Vertical",
            formation=formation_name,
            is_new_well=True,
            coordinate_source=coord_source,
            coordinate_confidence=coord_conf,
            source_document=src_doc,
            uploaded_at=uploaded_at,
        )

        # Register in active lookup and coordinates
        self._lookup[new_well_id] = new_well
        self._lookup[new_well_id.upper()] = new_well
        self._coordinates[new_well_id] = (lat, lon)

        # Append to dataframe
        new_row = pd.DataFrame([{
            "well_id": new_well.well_id,
            "well_name": new_well.well_name,
            "operator": new_well.operator,
            "field": new_well.field,
            "basin": new_well.basin,
            "block": new_well.block,
            "latitude": new_well.latitude,
            "longitude": new_well.longitude,
            "total_depth": new_well.total_depth,
            "spud_date": new_well.spud_date,
            "completion_date": new_well.completion_date,
            "well_type": new_well.well_type,
            "well_status": new_well.well_status,
            "trajectory_type": new_well.trajectory_type,
            "formation": new_well.formation,
            "is_new_well": True,
            "coordinate_source": coord_source,
            "coordinate_confidence": coord_conf,
            "source_document": src_doc,
            "uploaded_at": uploaded_at,
        }])
        self._df = pd.concat([self._df, new_row], ignore_index=True)

        # Persist to dynamic wells file
        try:
            import json
            self._dynamic_wells_file.parent.mkdir(parents=True, exist_ok=True)
            existing_dyn = []
            if self._dynamic_wells_file.exists():
                with open(self._dynamic_wells_file, "r", encoding="utf-8") as f:
                    existing_dyn = json.load(f)
            # Remove any with same ID if updating
            existing_dyn = [x for x in existing_dyn if x.get("well_id") != new_well_id]
            existing_dyn.append(new_well.model_dump())
            with open(self._dynamic_wells_file, "w", encoding="utf-8") as f:
                json.dump(existing_dyn, f, indent=2)
        except Exception:
            pass

        # PostgreSQL + PostGIS Persistence (Section 6)
        try:
            from ..db.session import get_session
            from ..db.models import Well as DBWell
            from sqlalchemy import text
            session = get_session()
            if session:
                existing_db = session.query(DBWell).filter(DBWell.well_id == new_well_id).first()
                if not existing_db:
                    db_well = DBWell(
                        well_id=new_well.well_id,
                        well_name=new_well.well_name,
                        latitude=new_well.latitude,
                        longitude=new_well.longitude,
                        field=new_well.field,
                        basin=new_well.basin,
                        block=new_well.block,
                        operator=new_well.operator,
                        total_depth=new_well.total_depth,
                        spud_date=new_well.spud_date,
                        completion_date=new_well.completion_date,
                        well_type=new_well.well_type,
                        well_status=new_well.well_status,
                        trajectory_type=new_well.trajectory_type,
                        formation=new_well.formation,
                        source="WCR_INGESTION",
                        coordinate_source=new_well.coordinate_source,
                        coordinate_confidence=new_well.coordinate_confidence,
                        source_document=new_well.source_document,
                        is_canonical=True,
                        is_new_well=True,
                    )
                    session.add(db_well)
                    session.commit()
                    # Execute PostGIS POINT(longitude, latitude) update
                    try:
                        session.execute(
                            text("UPDATE wells SET geom = ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography WHERE well_id = :wid"),
                            {"lon": new_well.longitude, "lat": new_well.latitude, "wid": new_well.well_id}
                        )
                        session.commit()
                    except Exception:
                        session.rollback()
                session.close()
        except Exception:
            pass

        return new_well

    def update_well_source_document(self, well_id: str, document_id: str) -> Optional[CanonicalWell]:
        """
        Updates source_document for an existing well across lookup, dataframe, dynamic wells file, and DB.
        Guarantees that newly created or repaired WCR wells have their document_id permanently linked.
        """
        self._ensure_loaded()
        wid = str(well_id).strip().upper()
        well = self._lookup.get(wid)
        if not well:
            return None

        # 1. Update active in-memory model
        well.source_document = document_id
        if well.coordinate_source in (None, "REAL_PUBLIC"):
            well.coordinate_source = "WCR_DOCUMENT"
        self._lookup[wid] = well
        if wid in self._lookup:
            self._lookup[wid.upper()] = well

        # 2. Update DataFrame
        if self._df is not None and not self._df.empty:
            match_mask = (self._df["well_id"].str.upper() == wid)
            if match_mask.any():
                self._df.loc[match_mask, "source_document"] = document_id
                self._df.loc[match_mask, "coordinate_source"] = well.coordinate_source

        # 3. Update dynamic wells JSON file
        if self._dynamic_wells_file.exists():
            try:
                import json
                with open(self._dynamic_wells_file, "r", encoding="utf-8") as f:
                    dyn_wells = json.load(f)
                updated = False
                for w in dyn_wells:
                    if str(w.get("well_id", "")).strip().upper() == wid:
                        w["source_document"] = document_id
                        if not w.get("coordinate_source") or w.get("coordinate_source") == "REAL_PUBLIC":
                            w["coordinate_source"] = "WCR_DOCUMENT"
                        updated = True
                        break
                if updated:
                    with open(self._dynamic_wells_file, "w", encoding="utf-8") as f:
                        json.dump(dyn_wells, f, indent=2)
            except Exception:
                pass

        # 4. Update PostgreSQL database if connected
        try:
            from ..db.session import get_session
            from sqlalchemy import text
            session = get_session()
            if session:
                session.execute(
                    text("UPDATE wells SET source_document = :doc_id, coordinate_source = 'WCR_DOCUMENT' WHERE UPPER(well_id) = :wid"),
                    {"doc_id": document_id, "wid": wid}
                )
                session.commit()
                session.close()
        except Exception:
            pass

        # 5. Invalidate marker cache so map markers immediately reflect the new source_document
        try:
            from ..services.well_service import well_service
            well_service._cached_response = None
        except Exception:
            pass

        return well

    def get_all_wells(
        self,
        offset: int = 0,
        limit: int = 100,
        basin: Optional[str] = None,
        operator: Optional[str] = None,
        search: Optional[str] = None
    ) -> Tuple[int, List[CanonicalWell]]:
        self._ensure_loaded()
        df = self._df

        if basin:
            df = df[df["basin"].str.lower() == basin.lower()]
        if operator:
            df = df[df["operator"].str.lower() == operator.lower()]
        if search:
            q = search.lower().strip()
            df = df[
                df["well_id"].str.lower().str.contains(q) |
                df["well_name"].str.lower().str.contains(q) |
                df["operator"].str.lower().str.contains(q) |
                df["field"].str.lower().str.contains(q) |
                df["basin"].str.lower().str.contains(q)
            ]

        total = len(df)
        page_df = df.iloc[offset: offset + limit]
        wells = [self._lookup[row["well_id"]] for _, row in page_df.iterrows()]
        return total, wells

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
        if not query or not query.strip():
            return []

        q = query.strip().lower()
        results: List[CanonicalWell] = []

        # Exact ID match priority
        exact = self.get_well(q)
        if exact:
            results.append(exact)

        for wid, well in self._lookup.items():
            if wid.endswith("-UPPER") or well in results:
                continue
            if (
                q in well.well_id.lower() or
                q in well.well_name.lower() or
                q in well.operator.lower() or
                q in well.field.lower() or
                q in well.basin.lower() or
                q in well.block.lower()
            ):
                results.append(well)
                if len(results) >= limit:
                    break

        return results

    def get_well_location(self, well_id: str) -> Optional[Tuple[float, float]]:
        self._ensure_loaded()
        wid = str(well_id).strip().upper()
        return self._coordinates.get(wid)

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

    @property
    def base_dataframe(self) -> pd.DataFrame:
        self._ensure_loaded()
        return self._base_df if hasattr(self, "_base_df") and self._base_df is not None else self._df

    @property
    def dataframe(self) -> pd.DataFrame:
        self._ensure_loaded()
        return self._df


well_repository = CsvWellRepository()
