from typing import List, Optional, Dict, Any
import pandas as pd
from ..models.document import DocumentMetadataRecord, DocumentMetadataResponse
from .data_path import resolve_data_file


class DocumentService:
    def __init__(self, csv_path: Optional[str] = None):
        self.csv_path = resolve_data_file("nwis_document_metadata_15108.csv", custom_path=csv_path)
        self._df: Optional[pd.DataFrame] = None
        self._cache: Dict[str, List[DocumentMetadataRecord]] = {}
        self._initialized = False

    def _ensure_loaded(self):
        if self._initialized:
            return

        df = pd.read_csv(self.csv_path, low_memory=False)
        df["well_id"] = df["well_id"].astype(str).str.strip().str.upper()
        self._df = df
        self._initialized = True

    def get_documents_by_well(self, well_id: str) -> DocumentMetadataResponse:
        self._ensure_loaded()
        wid = str(well_id).strip().upper()

        if wid in self._cache:
            docs = self._cache[wid]
            return DocumentMetadataResponse(well_id=wid, count=len(docs), documents=docs)

        sub_df = self._df[self._df["well_id"] == wid].sort_values("document_date", ascending=False)
        docs: List[DocumentMetadataRecord] = []

        for _, row in sub_df.iterrows():
            item = DocumentMetadataRecord(
                document_id=str(row["document_id"]),
                well_id=str(row["well_id"]),
                document_type=str(row["document_type"]),
                document_title=str(row["document_title"]),
                document_date=str(row["document_date"]),
                source_file=str(row["source_file"]),
                page_count=int(row["page_count"]),
                file_path=str(row["file_path"]),
                language=str(row["language"]),
                ocr_status=str(row["ocr_status"]),
                extraction_status=str(row["extraction_status"]),
            )
            docs.append(item)

        # Also check dynamic technical documents from repository (all statuses)
        try:
            from ...document_ai.document_repository import document_repository
            all_user_docs = document_repository.list_documents(limit=1000)
            for ud in all_user_docs:
                if ud.well_id and ud.well_id.upper() == wid and not any(d.document_id == ud.document_id for d in docs):
                    docs.append(DocumentMetadataRecord(
                        document_id=ud.document_id,
                        well_id=ud.well_id,
                        document_type=ud.document_type,
                        document_title=f"{ud.document_type} - {ud.filename}",
                        document_date=ud.approved_at or (ud.upload_timestamp[:10] if ud.upload_timestamp else "2026-09-27"),
                        source_file=ud.filename,
                        page_count=ud.page_count,
                        file_path=ud.file_path,
                        language="en",
                        ocr_status="COMPLETED" if ud.ocr_applied else "NOT_REQUIRED",
                        extraction_status=ud.processing_status or "REVIEW_REQUIRED",
                    ))
        except Exception:
            pass

        self._cache[wid] = docs
        return DocumentMetadataResponse(well_id=wid, count=len(docs), documents=docs)

    def get_linked_wcr_document(self, well_id: str) -> Optional[Dict[str, Any]]:
        """
        Resolves well_id -> canonical well -> linked WCR document -> actual document metadata.
        Returns None if no WCR document exists for the well.
        """
        self._ensure_loaded()
        wid = str(well_id).strip().upper()

        # 1. Check well object directly for source_document
        from .well_service import well_service
        canonical_well = well_service.get_well_by_id(wid)
        if not canonical_well:
            return None

        source_doc_id = getattr(canonical_well, "source_document", None)
        if source_doc_id and str(source_doc_id).startswith("DOC-"):
            try:
                from ...document_ai.document_repository import document_repository
                doc_rec = document_repository.get_document(source_doc_id)
                if doc_rec:
                    return {
                        "well_id": wid,
                        "document_id": doc_rec.document_id,
                        "document_type": doc_rec.document_type or "WCR",
                        "file_name": doc_rec.filename,
                        "status": doc_rec.processing_status or "VERIFIED",
                        "has_document": True,
                        "review_url": f"/documents/{doc_rec.document_id}/review",
                        "source": doc_rec.source or "WCR Extraction Pipeline",
                        "upload_timestamp": doc_rec.upload_timestamp,
                    }
            except Exception:
                pass

            # Check historical catalog for source_doc_id
            if source_doc_id in self._lookup:
                meta = self._lookup[source_doc_id]
                return {
                    "well_id": wid,
                    "document_id": meta.document_id,
                    "document_type": meta.document_type,
                    "file_name": meta.file_name,
                    "status": "VERIFIED",
                    "has_document": True,
                    "review_url": f"/documents/{meta.document_id}/review",
                    "source": "Historical NWIS Document Catalog",
                    "upload_timestamp": "2024-01-01T00:00:00Z",
                }

        # 2. Check dynamic documents in document_repository (strictly WCR)
        try:
            from ...document_ai.document_repository import document_repository
            all_user_docs = document_repository.list_documents(limit=1000)
            wcr_docs = [
                d for d in all_user_docs
                if d.well_id and d.well_id.upper() == wid and (d.document_type == "WCR" or d.document_id.startswith("DOC-WCR-"))
            ]
            if wcr_docs:
                best_doc = wcr_docs[0]
                try:
                    from ..repositories.well_repository import well_repository
                    well_repository.update_well_source_document(wid, best_doc.document_id)
                except Exception:
                    pass
                return {
                    "well_id": wid,
                    "document_id": best_doc.document_id,
                    "document_type": "WCR",
                    "file_name": best_doc.filename,
                    "status": best_doc.processing_status or "VERIFIED",
                    "has_document": True,
                    "review_url": f"/documents/{best_doc.document_id}/review",
                    "source": best_doc.source or "WCR Extraction Pipeline",
                    "upload_timestamp": best_doc.upload_timestamp,
                }
        except Exception:
            pass

        # 3. Check historical documents in nwis_document_metadata_15108.csv (strictly WCR)
        sub_df = self._df[self._df["well_id"] == wid]
        if not sub_df.empty:
            wcr_sub = sub_df[sub_df["document_type"] == "WCR"]
            if not wcr_sub.empty:
                row = wcr_sub.iloc[0]
                doc_id = str(row["document_id"])
                return {
                    "well_id": wid,
                    "document_id": doc_id,
                    "document_type": "WCR",
                    "file_name": str(row.get("source_file") or f"{wid}_WCR.pdf"),
                    "status": str(row.get("extraction_status", "VERIFIED")),
                    "has_document": True,
                    "review_url": f"/documents/{doc_id}/review",
                    "source": "Historical NWIS Document Catalog",
                    "upload_timestamp": str(row["document_date"]) if pd.notnull(row["document_date"]) else None,
                }

        return None


document_service = DocumentService()
