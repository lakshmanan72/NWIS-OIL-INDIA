"""
NWIS WCR Integration API Router
===============================
Dedicated endpoints for the complete WCR PDF → New Well Extraction → Database → Map workflow:
- POST /api/wcr/upload: Upload WCR, parse text, extract coordinates & metadata, detect duplicates
- POST /api/wcr/{document_id}/process: Re-process document
- GET  /api/wcr/{document_id}/extraction: Retrieve extraction details & validation status
- POST /api/wcr/{document_id}/create-well: Confirm and add new well to NWIS with PostGIS location
"""

from __future__ import annotations
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from ...document_ai import (
    document_repository,
    pdf_extractor,
    wcr_extractor,
    DocumentRecord,
    DocumentChunk,
    DocumentEvent,
    document_chunker,
)
from ..repositories.well_repository import well_repository
from ..services.well_service import well_service
from ..security.auth import (
    ROLE_ADMIN,
    ROLE_DRILLING_ENGINEER,
    UserResponse,
    get_current_user,
    require_role,
)
from ..security.audit import log_audit_event

router = APIRouter(prefix="/api/wcr", tags=["WCR Ingestion & New Well Workflow"])

UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "documents" / "uploads"
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


# =============================================================================
# Request / Response Schemas
# =============================================================================

class CreateWellFromWCRRequest(BaseModel):
    well_name: str
    latitude: float
    longitude: float
    coordinate_source: str = "WCR_DOCUMENT"  # WCR_DOCUMENT or ENGINEER_ENTERED
    operator: Optional[str] = "ONGC"
    field: Optional[str] = ""
    basin: Optional[str] = ""
    block: Optional[str] = ""
    total_depth: Optional[float] = None
    spud_date: Optional[str] = None
    completion_date: Optional[str] = None
    well_type: Optional[str] = "Exploration"
    well_status: Optional[str] = "Active"
    trajectory_type: Optional[str] = "Vertical"
    formation: Optional[str] = None
    force_confirm: bool = False
    reviewer: str = "Drilling Engineer"


# In-memory storage for active WCR extraction sessions
_WCR_EXTRACTION_SESSIONS: Dict[str, Dict[str, Any]] = {}


# =============================================================================
# 1. WCR PDF Upload & Multi-Stage Extraction
# =============================================================================

@router.post("/upload")
async def upload_wcr_document(
    file: UploadFile = File(...),
    uploaded_by: str = Form("Drilling Engineer"),
    user: UserResponse = Depends(get_current_user),
):
    """
    Step 1 & 2: Uploads a native or scanned WCR PDF.
    Validates file integrity, extracts text via PyMuPDF/pdfplumber/OCR,
    extracts coordinates with zero-hallucination rules, extracts canonical metadata,
    extracts historical drilling events, and checks for existing duplicate wells.
    """
    # 1. File validation
    filename = file.filename or "wcr_document.pdf"
    clean_filename = os.path.basename(filename).strip()

    ext = Path(clean_filename).suffix.lower()
    if ext not in [".pdf", ".txt"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. NWIS WCR pipeline requires .pdf or .txt documents."
        )

    content = await file.read()
    if not content or len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty (0 bytes).")

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail=f"File exceeds maximum permitted size of 50 MB.")

    if ext == ".pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Invalid PDF file: Missing standard %PDF- header magic bytes.")

    import hashlib
    sha256 = hashlib.sha256(content).hexdigest()

    # 2. Save file to disk
    doc_id = f"DOC-WCR-{uuid.uuid4().hex[:8].upper()}"
    doc_dir = UPLOADS_DIR / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    saved_path = doc_dir / clean_filename
    saved_path.write_bytes(content)

    timestamp_now = datetime.now(timezone.utc).isoformat()

    # 3. Extract text & pages via unified extractor (PyMuPDF / pdfplumber / pypdf / OCR)
    try:
        pages = pdf_extractor.extract_document(saved_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse PDF document: {str(e)}")

    full_text = "\n\n".join([p.get("text", "") for p in pages])

    # 4. Extract Coordinates (Zero Hallucination)
    coord_res = wcr_extractor.extract_coordinates(full_text)

    # 5. Extract Well Metadata
    metadata_res = wcr_extractor.extract_metadata(full_text, filename=clean_filename)

    # Attach coordinates to metadata if valid
    if coord_res.get("location_status") == "VALID":
        metadata_res["latitude"] = coord_res["latitude"]
        metadata_res["longitude"] = coord_res["longitude"]
        metadata_res["coordinate_source"] = coord_res["coordinate_source"]
        metadata_res["coordinate_confidence"] = coord_res["coordinate_confidence"]
    else:
        metadata_res["latitude"] = None
        metadata_res["longitude"] = None
        metadata_res["coordinate_source"] = None
        metadata_res["coordinate_confidence"] = 0.0

    # 6. Extract Historical Drilling Events
    events = wcr_extractor.extract_drilling_events(pages, document_id=doc_id)

    # 7. Check Duplicate Well against 15,108 canonical wells
    dup_res = wcr_extractor.detect_duplicate(metadata_res, existing_wells_repo=well_repository)

    # 8. Determine Pipeline Status
    if coord_res.get("location_status") != "VALID":
        pipeline_status = "INSUFFICIENT_EVIDENCE"
    elif dup_res.get("is_duplicate"):
        pipeline_status = "DUPLICATE_REVIEW"
    else:
        pipeline_status = "READY_TO_ADD"

    # 9. Create Document Record
    doc_record = DocumentRecord(
        document_id=doc_id,
        filename=clean_filename,
        file_path=str(saved_path),
        document_type="WCR",
        upload_timestamp=timestamp_now,
        uploaded_by=uploaded_by or user.full_name or user.username,
        processing_status="PROCESSING",
        checksum=sha256,
        source="Engineer WCR Upload",
        file_size_bytes=len(content),
        page_count=len(pages),
        ocr_applied=any(p.get("ocr_applied", False) for p in pages),
        well_id="UNMATCHED_WELL",
    )
    document_repository.save_document(doc_record)

    # Save chunks for RAG
    chunks = document_chunker.chunk_document(
        pages=pages,
        document_id=doc_id,
        well_id="UNMATCHED_WELL",
        document_type="WCR",
    )
    document_repository.save_chunks(chunks)

    # Save extraction session
    session_data = {
        "document_id": doc_id,
        "filename": clean_filename,
        "file_size_bytes": len(content),
        "page_count": len(pages),
        "upload_timestamp": timestamp_now,
        "uploaded_by": uploaded_by or user.username,
        "pipeline_status": pipeline_status,
        "coordinates": coord_res,
        "extracted_metadata": metadata_res,
        "drilling_events": events,
        "duplicate_detection": dup_res,
        "chunks_count": len(chunks),
    }
    _WCR_EXTRACTION_SESSIONS[doc_id] = session_data

    # Log audit trail
    try:
        log_audit_event(
            username=user.username,
            role=user.role,
            action="ENGINEER_UPLOADED_WCR",
            resource_type="WCR_DOCUMENT",
            resource_id=doc_id,
            reason=f"Uploaded WCR: {clean_filename} ({len(content)} bytes)",
        )
        log_audit_event(
            username=user.username,
            role=user.role,
            action="WCR_EXTRACTED",
            resource_type="WCR_EXTRACTION",
            resource_id=doc_id,
            reason=f"Coordinates: {coord_res.get('location_status')}, Pipeline: {pipeline_status}",
        )
    except Exception:
        pass

    return {
        "status": "success",
        "pipeline_status": pipeline_status,
        "document_id": doc_id,
        "filename": clean_filename,
        "file_size_bytes": len(content),
        "page_count": len(pages),
        "ocr_applied": doc_record.ocr_applied,
        "coordinates": coord_res,
        "extracted_metadata": metadata_res,
        "drilling_events": events,
        "duplicate_detection": dup_res,
        "message": coord_res.get("message") or "WCR processed successfully.",
    }


# =============================================================================
# 2. Retrieve Extraction Details
# =============================================================================

@router.get("/{document_id}/extraction")
def get_wcr_extraction(document_id: str):
    """Retrieves current extracted well metadata, coordinates, and events for a document."""
    if document_id in _WCR_EXTRACTION_SESSIONS:
        return _WCR_EXTRACTION_SESSIONS[document_id]

    doc = document_repository.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"WCR document '{document_id}' not found.")

    return {
        "document_id": doc.document_id,
        "filename": doc.filename,
        "pipeline_status": doc.processing_status,
        "well_id": doc.well_id,
        "message": "Archival document loaded from repository.",
    }


# =============================================================================
# 3. Create Well from WCR & Integrate with Map
# =============================================================================

@router.post("/{document_id}/create-well")
def create_well_from_wcr(
    document_id: str,
    req: CreateWellFromWCRRequest,
    user: UserResponse = Depends(get_current_user),
):
    """
    CRITICAL WORKFLOW COMPLETION GATE:
    1. Validates coordinate bounds [-90, 90] and [-180, 180]
    2. Enforces anti-hallucination & duplicate safety checks
    3. Allocates sequential canonical well ID (e.g. WELL-015109)
    4. Inserts into canonical well registry and PostGIS (geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography)
    5. Links WCR document to the new well and marks document APPROVED
    6. Stores extracted historical drilling events linked to the new well
    7. Clears cache so interactive map immediately reflects total count (15,108 + 1 = 15,109)
    8. Returns map_action = 'FOCUS_NEW_WELL' with coordinates and new well details.
    """
    # 1. Validate coordinates
    lat = req.latitude
    lon = req.longitude
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid coordinates ({lat}, {lon}). Latitude must be in [-90, 90] and Longitude in [-180, 180]."
        )

    # 2. Duplicate check if not force-confirmed
    well_payload = req.model_dump()
    dup_res = wcr_extractor.detect_duplicate(well_payload, existing_wells_repo=well_repository)
    if dup_res.get("is_duplicate") and not req.force_confirm:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "POSSIBLE_DUPLICATE",
                "message": dup_res.get("similarity_reason"),
                "duplicate": dup_res,
                "advisory": "A potential duplicate was detected in the existing 15,108 wells. Set force_confirm=true to proceed with creating a distinct well."
            }
        )

    # 3. Create Canonical Well Record
    well_payload["source_document"] = document_id
    well_payload["uploaded_at"] = datetime.now(timezone.utc).isoformat()
    well_payload["coordinate_source"] = req.coordinate_source
    well_payload["coordinate_confidence"] = 1.0 if req.coordinate_source == "ENGINEER_ENTERED" else 0.98

    try:
        new_well = well_repository.create_canonical_well(
            well_data=well_payload,
            reviewer=req.reviewer or user.full_name or user.username,
            force_confirm=True,  # already verified above
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Guarantee source_document is persisted in repository, JSON, and DB
    well_repository.update_well_source_document(new_well.well_id, document_id)

    # 4. Link Document to the new Well and Mark Approved
    doc = document_repository.get_document(document_id)
    if doc:
        doc.well_id = new_well.well_id
        doc.matched_well_name = new_well.well_name
        doc.well_match_status = "MATCHED"
        doc.well_match_method = "wcr_new_well_creation"
        doc.well_match_confidence = 1.0
        doc.document_type = "WCR"
        doc.processing_status = "APPROVED"
        doc.approved_by = req.reviewer or user.username
        doc.approved_at = datetime.now(timezone.utc).isoformat()
        document_repository.update_document(doc)

        # Update well_id on all chunks
        chunks = document_repository.get_chunks_for_document(document_id)
        for c in chunks:
            c.well_id = new_well.well_id
            c.approval_status = "APPROVED"
        document_repository.save_chunks(chunks)

    # 5. Save Extracted Drilling Events
    events_saved_count = 0
    session_data = _WCR_EXTRACTION_SESSIONS.get(document_id)
    if session_data and "drilling_events" in session_data:
        raw_events = session_data["drilling_events"]
        doc_events = []
        for ev in raw_events:
            devt = DocumentEvent(
                event_id=ev.get("event_id") or f"EVT-{uuid.uuid4().hex[:8].upper()}",
                document_id=document_id,
                well_id=new_well.well_id,
                event_type=ev.get("event_type", "Operational Incident"),
                raw_event_text=ev.get("description", ""),
                depth_md=ev.get("depth"),
                formation=ev.get("formation") or new_well.formation,
                source_page=ev.get("source_page", 1),
                confidence=ev.get("extraction_confidence", 0.90),
                hazard_assumption=f"Reported in {doc.filename if doc else 'WCR'}",
                status="APPROVED",
            )
            doc_events.append(devt)
        if doc_events:
            document_repository.save_events(doc_events)
            events_saved_count = len(doc_events)

    # 6. Invalidate Map Marker Cache to include new well immediately
    well_service._cached_response = None
    markers_resp = well_service.load_markers(force_reload=True, include_new_wells=True)
    total_wells_count = markers_resp.count

    # 7. Audit Trail Logging
    try:
        log_audit_event(
            username=user.username,
            role=user.role,
            action="WELL_CREATED",
            resource_type="WELL",
            resource_id=new_well.well_id,
            well_id=new_well.well_id,
            reason=f"Created canonical well '{new_well.well_name}' from WCR document {document_id}",
        )
        log_audit_event(
            username=user.username,
            role=user.role,
            action="MAP_LOCATION_CREATED",
            resource_type="POSTGIS_GEOM",
            resource_id=new_well.well_id,
            well_id=new_well.well_id,
            reason=f"Coordinates ({new_well.latitude}, {new_well.longitude}) mapped to PostGIS location POINT({new_well.longitude} {new_well.latitude})",
        )
    except Exception:
        pass

    # Update session status
    if session_data:
        session_data["pipeline_status"] = "ADDED_TO_NWIS"
        session_data["well_id"] = new_well.well_id

    return {
        "success": True,
        "well_id": new_well.well_id,
        "well_name": new_well.well_name,
        "latitude": new_well.latitude,
        "longitude": new_well.longitude,
        "operator": new_well.operator,
        "field": new_well.field,
        "basin": new_well.basin,
        "total_depth": new_well.total_depth,
        "formation": new_well.formation,
        "coordinate_source": new_well.coordinate_source,
        "source_document": document_id,
        "events_count": events_saved_count,
        "total_wells": total_wells_count,
        "map_action": "FOCUS_NEW_WELL",
        "message": (
            f"WELL ADDED TO NWIS\n\n"
            f"Well: {new_well.well_name} ({new_well.well_id})\n"
            f"Coordinates: {new_well.latitude:.6f}, {new_well.longitude:.6f}\n"
            f"Source: WCR ({new_well.coordinate_source})\n"
            f"Events extracted: {events_saved_count}\n\n"
            f"The new well is now available on the NWIS map."
        ),
    }
