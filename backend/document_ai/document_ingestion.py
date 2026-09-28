"""
NWIS Phase 4 — Document Ingestion Engine
========================================
Orchestrates secure file upload, validation, extraction, classification,
chunking, entity/event extraction, and canonical well registry matching.
Enforces strict security checks (MIME type, size, path traversal, checksums).
"""

from __future__ import annotations
import hashlib
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .chunker import document_chunker
from .document_classifier import document_classifier
from .document_repository import (
    UPLOADS_DIR,
    DocumentChunk,
    DocumentEvent,
    DocumentExtraction,
    DocumentRecord,
    document_repository,
)
from .entity_extractor import entity_extractor
from .event_extractor import event_extractor
from .pdf_extractor import PDFExtractorError, pdf_extractor

logger = logging.getLogger("nwis.document_ingestion")

# Maximum upload file size: 50 MB
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".txt"}


class IngestionValidationError(Exception):
    """Raised when uploaded file fails validation checks."""
    pass


class DocumentIngestionEngine:
    """
    End-to-end document processing pipeline.
    """

    def __init__(self, max_file_size: int = MAX_FILE_SIZE_BYTES):
        self.max_file_size = max_file_size

    def validate_file(self, filename: str, content: bytes) -> str:
        """
        Validates file size, extension, contents, and path traversal security.
        Returns the SHA-256 checksum string.
        """
        if not content or len(content) == 0:
            raise IngestionValidationError("Uploaded file is empty (0 bytes).")

        if len(content) > self.max_file_size:
            max_mb = self.max_file_size // (1024 * 1024)
            raise IngestionValidationError(f"File size ({len(content)} bytes) exceeds maximum permitted limit ({max_mb} MB).")

        # Filename path traversal prevention
        if ".." in filename or "/" in filename or "\\" in filename:
            raise IngestionValidationError("Invalid filename: Potential path traversal detected.")

        clean_filename = os.path.basename(filename).strip()
        if not clean_filename:
            raise IngestionValidationError("Invalid filename: Empty filename provided.")

        ext = Path(clean_filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise IngestionValidationError(f"Unsupported file extension '{ext}'. Only .pdf and .txt are permitted.")

        # PDF header magic bytes and structure check
        if ext == ".pdf":
            if not content.startswith(b"%PDF-"):
                raise IngestionValidationError("Invalid PDF file: Missing standard %PDF- header magic bytes.")
            import io
            import pypdf
            try:
                reader = pypdf.PdfReader(io.BytesIO(content))
                if reader.is_encrypted:
                    raise IngestionValidationError("Password-protected PDF files are not supported. Please remove password encryption.")
                if len(reader.pages) == 0:
                    raise IngestionValidationError("Invalid PDF file: Document contains 0 pages.")
            except IngestionValidationError:
                raise
            except Exception as e:
                raise IngestionValidationError(f"Malformed or corrupted PDF file: {e}")

        checksum = hashlib.sha256(content).hexdigest()
        return checksum

    def ingest_document(
        self,
        filename: str,
        content: bytes,
        uploaded_by: str = "Engineer",
        user_specified_type: Optional[str] = None,
        source: str = "Engineer Upload",
    ) -> Tuple[DocumentRecord, List[DocumentExtraction], List[DocumentEvent]]:
        """
        Main ingestion entry point: validates, parses, chunks, extracts entities/events,
        matches canonical well, and registers for engineer review.
        """
        # 1. Validation & Checksum
        checksum = self.validate_file(filename, content)

        # Check for duplicate document
        existing = document_repository.get_document_by_checksum(checksum)
        if existing:
            logger.info(f"Duplicate document uploaded: Checksum {checksum} matches existing {existing.document_id}")
            # If already processed or in review, return existing record
            extractions = document_repository.get_extractions_for_document(existing.document_id)
            events = document_repository.get_events_for_document(existing.document_id)
            return existing, extractions, events

        # 2. Allocate Document ID and save file securely
        doc_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(filename))
        doc_dir = UPLOADS_DIR / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        saved_path = doc_dir / safe_name
        saved_path.write_bytes(content)

        timestamp_now = datetime.now(timezone.utc).isoformat()

        # Initial Document Record
        doc_record = DocumentRecord(
            document_id=doc_id,
            filename=safe_name,
            file_path=str(saved_path),
            document_type=user_specified_type or "OTHER",
            upload_timestamp=timestamp_now,
            uploaded_by=uploaded_by,
            processing_status="PROCESSING",
            checksum=checksum,
            source=source,
            file_size_bytes=len(content),
            well_id="UNMATCHED_WELL",
        )
        document_repository.save_document(doc_record)

        try:
            # 3. Extract Pages / Text
            pages = pdf_extractor.extract_document(saved_path)
            doc_record.page_count = len(pages)
            doc_record.ocr_applied = any(p.get("ocr_applied", False) for p in pages)

            # Combined sample text for classification
            sample_text = "\n".join([p.get("text", "") for p in pages[:5]])

            # 4. Document Classification
            if user_specified_type and user_specified_type != "OTHER":
                doc_record.document_type = user_specified_type
                doc_record.classification_confidence = 0.95
            else:
                detected_type, conf = document_classifier.classify(sample_text, filename=safe_name)
                doc_record.document_type = detected_type
                doc_record.classification_confidence = conf

            # 5. Section-Aware Chunking
            chunks = document_chunker.chunk_document(
                pages=pages,
                document_id=doc_id,
                well_id=doc_record.well_id,
                document_type=doc_record.document_type,
            )
            document_repository.save_chunks(chunks)

            # 6. Entity Extraction
            extractions = entity_extractor.extract_entities_from_chunks(chunks)

            # 7. Event Extraction
            events = event_extractor.extract_events_from_chunks(chunks)

            # 8. Canonical Well Matching
            match_res = self._match_canonical_well(extractions)
            doc_record.well_match_status = match_res.get("well_match_status", "UNMATCHED")
            doc_record.well_match_method = match_res.get("match_method")
            doc_record.well_match_confidence = match_res.get("confidence")
            doc_record.ambiguous_candidates = match_res.get("ambiguous_candidates")

            if match_res.get("well_match_status") == "MATCHED":
                doc_record.well_id = match_res["well_id"]
                doc_record.matched_well_name = match_res.get("matched_well_name")
                # Update well_id on chunks and events
                for chk in chunks:
                    chk.well_id = match_res["well_id"]
                for evt in events:
                    evt.well_id = match_res["well_id"]
                document_repository.save_chunks(chunks)
            else:
                doc_record.well_id = "UNMATCHED_WELL"

            document_repository.save_extractions(extractions)
            document_repository.save_events(events)

            # 9. Set Status to REVIEW_REQUIRED
            doc_record.processing_status = "REVIEW_REQUIRED"
            document_repository.update_document(doc_record)

            logger.info(
                f"Successfully ingested {doc_id} ({safe_name}): "
                f"{len(pages)} pages, {len(chunks)} chunks, {len(extractions)} entities, {len(events)} events, "
                f"Well Match: {doc_record.well_match_status} ({doc_record.well_id})."
            )
            return doc_record, extractions, events

        except Exception as e:
            logger.error(f"Failed to process document {doc_id}: {e}", exc_info=True)
            doc_record.processing_status = "FAILED"
            doc_record.rejection_reason = f"Processing failed: {str(e)}"
            document_repository.update_document(doc_record)
            raise

    def _match_canonical_well(self, extractions: List[DocumentExtraction]) -> Dict[str, Any]:
        """
        Attempts to identify the canonical well using:
        1. Explicit well ID
        2. Well name (exact and normalized)
        3. Coordinate proximity (< 0.5 km)
        4. Fuzzy name matching
        Returns structured matching status: MATCHED, AMBIGUOUS, or UNMATCHED.
        """
        import difflib
        from ..app.repositories.well_repository import well_repository

        extracted_id = None
        extracted_name = None
        extracted_lat = None
        extracted_lon = None
        extracted_field = None
        extracted_basin = None

        for ext in extractions:
            if ext.field == "well_id" and ext.value:
                extracted_id = str(ext.value).strip().upper()
            elif ext.field == "well_name" and ext.value:
                extracted_name = str(ext.value).strip()
            elif ext.field == "latitude" and ext.value is not None:
                try:
                    extracted_lat = float(ext.value)
                except (ValueError, TypeError):
                    pass
            elif ext.field == "longitude" and ext.value is not None:
                try:
                    extracted_lon = float(ext.value)
                except (ValueError, TypeError):
                    pass
            elif ext.field == "field" and ext.value:
                extracted_field = str(ext.value).strip()
            elif ext.field == "basin" and ext.value:
                extracted_basin = str(ext.value).strip()

        # 1. Direct match on well_id (e.g. WELL-000050)
        if extracted_id:
            canonical = well_repository.get_well(extracted_id)
            if canonical:
                return {
                    "well_match_status": "MATCHED",
                    "well_id": canonical.well_id,
                    "matched_well_name": canonical.well_name,
                    "match_method": "explicit_well_id",
                    "confidence": 0.99,
                }

        # 2. Match on well_name (exact / case-insensitive)
        if extracted_name:
            matches = well_repository.search_wells(extracted_name, limit=10)
            exact_matches = [m for m in matches if m.well_name.lower() == extracted_name.lower()]
            if len(exact_matches) == 1:
                m = exact_matches[0]
                conf = 0.96
                if extracted_lat is not None and extracted_lon is not None:
                    # check coordinates
                    if abs(m.latitude - extracted_lat) < 0.05 and abs(m.longitude - extracted_lon) < 0.05:
                        conf = 0.98
                return {
                    "well_match_status": "MATCHED",
                    "well_id": m.well_id,
                    "matched_well_name": m.well_name,
                    "match_method": "well_name",
                    "confidence": conf,
                }
            elif len(exact_matches) > 1:
                return {
                    "well_match_status": "AMBIGUOUS",
                    "well_id": "UNMATCHED_WELL",
                    "match_method": "multiple_name_matches",
                    "confidence": 0.70,
                    "ambiguous_candidates": [
                        {
                            "well_id": m.well_id,
                            "well_name": m.well_name,
                            "operator": m.operator,
                            "field": m.field,
                            "basin": m.basin,
                            "latitude": m.latitude,
                            "longitude": m.longitude,
                        }
                        for m in exact_matches[:5]
                    ],
                }

        # 3. Coordinate proximity matching (if coordinates are extracted)
        if extracted_lat is not None and extracted_lon is not None:
            well_repository._ensure_loaded()
            candidates_near = []
            for wid, (wlat, wlon) in well_repository._coordinates.items():
                if abs(wlat - extracted_lat) < 0.005 and abs(wlon - extracted_lon) < 0.005:  # ~500m
                    well_obj = well_repository.get_well(wid)
                    if well_obj:
                        candidates_near.append(well_obj)

            if len(candidates_near) == 1:
                m = candidates_near[0]
                return {
                    "well_match_status": "MATCHED",
                    "well_id": m.well_id,
                    "matched_well_name": m.well_name,
                    "match_method": "coordinate_proximity",
                    "confidence": 0.92,
                }
            elif len(candidates_near) > 1:
                return {
                    "well_match_status": "AMBIGUOUS",
                    "well_id": "UNMATCHED_WELL",
                    "match_method": "coordinate_cluster",
                    "confidence": 0.65,
                    "ambiguous_candidates": [
                        {
                            "well_id": m.well_id,
                            "well_name": m.well_name,
                            "operator": m.operator,
                            "field": m.field,
                            "basin": m.basin,
                            "latitude": m.latitude,
                            "longitude": m.longitude,
                        }
                        for m in candidates_near[:5]
                    ],
                }

        # 4. Fuzzy well name matching
        if extracted_name and len(extracted_name) >= 3:
            well_repository._ensure_loaded()
            all_names = {w.well_name: w for w in well_repository._lookup.values() if not w.well_id.endswith("-UPPER")}
            close_names = difflib.get_close_matches(extracted_name, list(all_names.keys()), n=3, cutoff=0.82)
            if len(close_names) == 1:
                m = all_names[close_names[0]]
                return {
                    "well_match_status": "MATCHED",
                    "well_id": m.well_id,
                    "matched_well_name": m.well_name,
                    "match_method": "fuzzy_name",
                    "confidence": 0.88,
                }
            elif len(close_names) > 1:
                return {
                    "well_match_status": "AMBIGUOUS",
                    "well_id": "UNMATCHED_WELL",
                    "match_method": "fuzzy_ambiguous",
                    "confidence": 0.60,
                    "ambiguous_candidates": [
                        {
                            "well_id": all_names[name].well_id,
                            "well_name": all_names[name].well_name,
                            "operator": all_names[name].operator,
                            "field": all_names[name].field,
                            "basin": all_names[name].basin,
                            "latitude": all_names[name].latitude,
                            "longitude": all_names[name].longitude,
                        }
                        for name in close_names
                    ],
                }

        # 5. Unmatched
        return {
            "well_match_status": "UNMATCHED",
            "well_id": "UNMATCHED_WELL",
            "matched_well_name": None,
            "match_method": "none",
            "confidence": 0.0,
        }


document_ingestion_engine = DocumentIngestionEngine()
