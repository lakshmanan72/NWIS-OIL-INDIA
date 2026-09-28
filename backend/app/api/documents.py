"""
NWIS Phase 4 — Document Intelligence & Review API Router
========================================================
Exposes endpoints for document upload, review cockpit, canonical well matching,
document search, and grounded RAG query intelligence.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field

from ...document_ai import (
    document_ingestion_engine,
    document_intelligence_service,
    document_repository,
)
from ...document_ai.document_ingestion import IngestionValidationError
from ..security.auth import (
    ROLE_ADMIN,
    ROLE_DRILLING_ENGINEER,
    UserResponse,
    require_role,
)
from ..security.audit import log_audit_event

router = APIRouter(tags=["Documents & Institutional Memory"])


# =====================================================================
# Request / Response Schemas
# =====================================================================

class EditExtractionRequest(BaseModel):
    edited_value: Any
    reviewer: str = "Engineer"
    comments: Optional[str] = None


class ExtractionActionRequest(BaseModel):
    reviewer: str = "Engineer"
    comments: Optional[str] = None


class DocumentApproveRequest(BaseModel):
    reviewer: str = "Engineer"
    comments: Optional[str] = None


class DocumentRejectRequest(BaseModel):
    reviewer: str = "Engineer"
    reason: str = "Quality or verification criteria not met."


class LinkWellRequest(BaseModel):
    well_id: str
    reviewer: str = "Engineer"


class CreateWellRequest(BaseModel):
    well_name: str
    latitude: float
    longitude: float
    field: str
    basin: str
    block: Optional[str] = ""
    trajectory: Optional[str] = "Vertical"
    operator: Optional[str] = "ONGC"
    spud_date: Optional[str] = None
    completion_date: Optional[str] = None
    total_depth: Optional[float] = None
    force_confirm: bool = False
    reviewer: str = "Engineer"


class EditEventRequest(BaseModel):
    event_type: Optional[str] = None
    depth_md: Optional[float] = None
    hazard_assumption: Optional[str] = None
    raw_event_text: Optional[str] = None
    reviewer: str = "Engineer"
    comments: Optional[str] = None


class OverrideClassificationRequest(BaseModel):
    document_type: str
    reviewer: str = "Engineer"
    comments: Optional[str] = None


class EventActionRequest(BaseModel):
    reviewer: str = "Engineer"
    comments: Optional[str] = None


class RAGQueryRequest(BaseModel):
    query: str
    well_id: Optional[str] = None
    depth_md: Optional[float] = None
    formation: Optional[str] = None
    radius_km: float = Field(25.0, ge=1.0, le=200.0)


from ..core.observability import metrics_collector


# =====================================================================
# 1. Document Upload
# =====================================================================

@router.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    document_type: Optional[str] = Form(None),
    uploaded_by: str = Form("Drilling Engineer"),
    source: str = Form("Engineer Upload - WCR/DDR"),
):
    """
    Upload and ingest technical drilling documentation (PDF/TXT).
    Performs security validation, classification, chunking, and entity extraction.
    """
    try:
        content = await file.read()
        doc_record, extractions, events = document_ingestion_engine.ingest_document(
            filename=file.filename or "unknown.pdf",
            content=content,
            uploaded_by=uploaded_by,
            user_specified_type=document_type,
            source=source,
        )

        metrics_collector.inc_document_upload()

        return {
            "status": "success",
            "document": doc_record,
            "extractions_count": len(extractions),
            "events_count": len(events),
            "requires_review": True,
            "review_url": f"/documents/{doc_record.document_id}/review",
        }
    except IngestionValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Document processing failed: {str(e)}")


# =====================================================================
# 2. Document Registry & Review Cockpit
# =====================================================================

@router.get("/api/documents")
def list_documents(
    status: Optional[str] = Query(None, description="Filter by status: REVIEW_REQUIRED, APPROVED, REJECTED, PROCESSING"),
    document_type: Optional[str] = Query(None, description="Filter by type: WCR, DDR, MUD_LOG, etc."),
    limit: int = Query(100, ge=1, le=500),
):
    """Returns document registry list with aggregate status statistics."""
    return document_intelligence_service.list_documents_summary(
        status=status,
        doc_type=document_type,
        limit=limit,
    )


@router.get("/api/documents/search")
def search_documents(
    q: str = Query(..., min_length=1, description="Search query across approved documents"),
    well_id: Optional[str] = Query(None, description="Active well ID for distance calculation"),
    limit: int = Query(15, ge=1, le=50),
):
    """
    GET /api/documents/search?q=
    Returns approved chunks and historical events with distance to active well if supplied.
    """
    return document_intelligence_service.search_documents(
        q=q,
        active_well_id=well_id,
        limit=limit,
    )


@router.get("/api/documents/{document_id}")
def get_document_review(document_id: str):
    """Returns review cockpit payload: document, extractions, events, and audit reviews."""
    clean_id = str(document_id).strip()

    # If well_id was passed instead of document_id, resolve canonical relationship
    if clean_id.startswith("WELL-"):
        from ..services.document_service import document_service
        linked = document_service.get_linked_wcr_document(clean_id)
        if not linked:
            raise HTTPException(
                status_code=404,
                detail=f"No WCR document available for well '{clean_id}'."
            )
        data = document_intelligence_service.get_document_details(linked["document_id"])
        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"Document '{linked['document_id']}' not found."
            )
        data["resolved_from_well_id"] = clean_id
        return data

    data = document_intelligence_service.get_document_details(clean_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Document '{clean_id}' not found.")
    return data


# =====================================================================
# 3. Engineer Review Actions
# =====================================================================

@router.post("/api/documents/{document_id}/extractions/{extraction_id}/approve")
def approve_extraction(
    document_id: str,
    extraction_id: str,
    req: ExtractionActionRequest = ExtractionActionRequest(),
    user: UserResponse = Depends(require_role(ROLE_ADMIN, ROLE_DRILLING_ENGINEER)),
):
    """Approves an individual extracted fact."""
    reviewer_name = req.reviewer or user.full_name or user.username
    ext = document_intelligence_service.approve_extraction(
        extraction_id=extraction_id,
        reviewer=reviewer_name,
        comments=req.comments,
    )
    if not ext:
        raise HTTPException(status_code=404, detail=f"Extraction '{extraction_id}' not found.")
    return {"status": "approved", "extraction": ext}


@router.post("/api/documents/{document_id}/extractions/{extraction_id}/edit")
def edit_extraction(
    document_id: str,
    extraction_id: str,
    req: EditExtractionRequest,
    user: UserResponse = Depends(require_role(ROLE_ADMIN, ROLE_DRILLING_ENGINEER)),
):
    """Corrects an extracted value before approval."""
    reviewer_name = req.reviewer or user.full_name or user.username
    ext = document_intelligence_service.edit_extraction(
        extraction_id=extraction_id,
        edited_value=req.edited_value,
        reviewer=reviewer_name,
        comments=req.comments,
    )
    if not ext:
        raise HTTPException(status_code=404, detail=f"Extraction '{extraction_id}' not found.")
    return {"status": "edited", "extraction": ext}


@router.post("/api/documents/{document_id}/extractions/{extraction_id}/reject")
def reject_extraction(
    document_id: str,
    extraction_id: str,
    req: ExtractionActionRequest = ExtractionActionRequest(),
    user: UserResponse = Depends(require_role(ROLE_ADMIN, ROLE_DRILLING_ENGINEER)),
):
    """Rejects an individual extracted fact."""
    reviewer_name = req.reviewer or user.full_name or user.username
    ext = document_intelligence_service.reject_extraction(
        extraction_id=extraction_id,
        reviewer=reviewer_name,
        comments=req.comments,
    )
    if not ext:
        raise HTTPException(status_code=404, detail=f"Extraction '{extraction_id}' not found.")
    return {"status": "rejected", "extraction": ext}


@router.post("/api/documents/{document_id}/events/{event_id}/approve")
def approve_event(
    document_id: str,
    event_id: str,
    req: EventActionRequest = EventActionRequest(),
    user: UserResponse = Depends(require_role(ROLE_ADMIN, ROLE_DRILLING_ENGINEER)),
):
    """Approves an individual extracted drilling event."""
    reviewer_name = req.reviewer or user.full_name or user.username
    evt = document_intelligence_service.approve_event(
        event_id=event_id,
        reviewer=reviewer_name,
        comments=req.comments,
    )
    if not evt:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found.")
    return {"status": "approved", "event": evt}


@router.post("/api/documents/{document_id}/events/{event_id}/edit")
def edit_event(
    document_id: str,
    event_id: str,
    req: EditEventRequest,
    user: UserResponse = Depends(require_role(ROLE_ADMIN, ROLE_DRILLING_ENGINEER)),
):
    """Corrects an extracted event attributes before approval."""
    reviewer_name = req.reviewer or user.full_name or user.username
    evt = document_intelligence_service.edit_event(
        event_id=event_id,
        event_type=req.event_type,
        depth_md=req.depth_md,
        hazard_assumption=req.hazard_assumption,
        raw_event_text=req.raw_event_text,
        reviewer=reviewer_name,
        comments=req.comments,
    )
    if not evt:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found.")
    return {"status": "edited", "event": evt}


@router.post("/api/documents/{document_id}/events/{event_id}/reject")
def reject_event(
    document_id: str,
    event_id: str,
    req: EventActionRequest = EventActionRequest(),
    user: UserResponse = Depends(require_role(ROLE_ADMIN, ROLE_DRILLING_ENGINEER)),
):
    """Rejects an individual drilling event."""
    reviewer_name = req.reviewer or user.full_name or user.username
    evt = document_intelligence_service.reject_event(
        event_id=event_id,
        reviewer=reviewer_name,
        comments=req.comments,
    )
    if not evt:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found.")
    return {"status": "rejected", "event": evt}


@router.post("/api/documents/{document_id}/classify")
def override_classification(
    document_id: str,
    req: OverrideClassificationRequest,
    user: UserResponse = Depends(require_role(ROLE_ADMIN, ROLE_DRILLING_ENGINEER)),
):
    """Allows engineer to override document classification type."""
    try:
        reviewer_name = req.reviewer or user.full_name or user.username
        doc = document_intelligence_service.update_document_classification(
            document_id=document_id,
            document_type=req.document_type,
            reviewer=reviewer_name,
            comments=req.comments,
        )
        return {"status": "updated", "document": doc}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/documents/{document_id}/approve-all-high")
def approve_all_high_confidence(
    document_id: str,
    min_confidence: float = Query(0.85, ge=0.5, le=1.0),
    reviewer: str = Query("Engineer"),
    user: UserResponse = Depends(require_role(ROLE_ADMIN, ROLE_DRILLING_ENGINEER)),
):
    """Batch-approves all entities and events with confidence >= min_confidence."""
    doc = document_repository.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")
    reviewer_name = reviewer or user.full_name or user.username
    res = document_intelligence_service.approve_all_high_confidence(
        document_id=document_id,
        min_confidence=min_confidence,
        reviewer=reviewer_name,
    )
    return {"status": "success", "batch_approval": res}


@router.post("/api/documents/{document_id}/approve")
def approve_document(
    document_id: str,
    req: DocumentApproveRequest = DocumentApproveRequest(),
    user: UserResponse = Depends(require_role(ROLE_ADMIN, ROLE_DRILLING_ENGINEER)),
):
    """
    CRITICAL APPROVAL GATE:
    Promotes document from REVIEW_REQUIRED to APPROVED.
    Vectorizes chunks into RAG index and syncs approved events into institutional memory.
    """
    try:
        reviewer_name = req.reviewer or user.full_name or user.username
        doc = document_intelligence_service.approve_document(
            document_id=document_id,
            reviewer=reviewer_name,
            comments=req.comments,
        )
        try:
            log_audit_event(
                username=user.username,
                role=user.role,
                action="DOCUMENT_APPROVED",
                resource_type="DOCUMENT",
                resource_id=document_id,
                well_id=doc.well_id,
                reason=req.comments,
            )
        except Exception:
            pass
        metrics_collector.inc_wcr_approval()
        return {"status": "approved", "document": doc}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/documents/{document_id}/reject")
def reject_document(
    document_id: str,
    req: DocumentRejectRequest = DocumentRejectRequest(),
    user: UserResponse = Depends(require_role(ROLE_ADMIN, ROLE_DRILLING_ENGINEER)),
):
    """Rejects document: rejected facts are isolated and never indexed."""
    try:
        reviewer_name = req.reviewer or user.full_name or user.username
        doc = document_intelligence_service.reject_document(
            document_id=document_id,
            reviewer=reviewer_name,
            reason=req.reason,
        )
        try:
            log_audit_event(
                username=user.username,
                role=user.role,
                action="DOCUMENT_REJECTED",
                resource_type="DOCUMENT",
                resource_id=document_id,
                well_id=doc.well_id,
                reason=req.reason,
            )
        except Exception:
            pass
        return {"status": "rejected", "document": doc}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =====================================================================
# 4. Canonical Well Matching & New Well Creation
# =====================================================================

@router.post("/api/documents/{document_id}/match-well")
def link_document_to_well(
    document_id: str,
    req: LinkWellRequest,
    user: UserResponse = Depends(require_role(ROLE_ADMIN, ROLE_DRILLING_ENGINEER)),
):
    """Explicitly attaches an unmatched document to an existing canonical well."""
    try:
        reviewer_name = req.reviewer or user.full_name or user.username
        doc = document_intelligence_service.link_document_to_well(
            document_id=document_id,
            well_id=req.well_id,
            reviewer=reviewer_name,
        )
        return {"status": "linked", "document": doc}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/documents/{document_id}/create-well")
def create_new_well_candidate(
    document_id: str,
    req: CreateWellRequest,
    user: UserResponse = Depends(require_role(ROLE_ADMIN, ROLE_DRILLING_ENGINEER)),
):
    """Controlled new well workflow requiring engineer confirmation."""
    try:
        reviewer_name = req.reviewer or user.full_name or user.username
        new_well = document_intelligence_service.create_new_well_candidate(
            document_id=document_id,
            well_data=req.model_dump(),
            reviewer=reviewer_name,
            force_confirm=req.force_confirm,
        )
        return {"status": "created", "well": new_well}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =====================================================================
# 5. Document Search & Grounded RAG Query
# =====================================================================



@router.post("/api/intelligence/query")
def query_intelligence(req: RAGQueryRequest):
    """
    POST /api/intelligence/query
    Answers technical drilling questions grounded strictly in verified evidence
    from approved WCR/DDR documents and offset wells.
    """
    metrics_collector.inc_rag_query()
    return document_intelligence_service.query_intelligence(
        query=req.query,
        well_id=req.well_id,
        depth_md=req.depth_md,
        formation=req.formation,
        radius_km=req.radius_km,
    )


@router.get("/api/intelligence/context")
def get_intelligence_context(
    query: str = Query(..., description="Technical query string"),
    well_id: Optional[str] = Query(None, description="Active canonical well ID"),
    depth_md: Optional[float] = Query(None, description="Bit measured depth in meters"),
    formation: Optional[str] = Query(None, description="Target formation"),
    radius_km: float = Query(25.0, ge=1.0, le=200.0, description="Spatial offset radius in km"),
):
    """
    GET /api/intelligence/context
    Returns the deterministic Evidence Packet without LLM synthesis.
    """
    return document_intelligence_service.get_context(
        query=query,
        well_id=well_id,
        depth_md=depth_md,
        formation=formation,
        radius_km=radius_km,
    )


@router.get("/api/intelligence/status")
def get_intelligence_status():
    """
    GET /api/intelligence/status
    Returns operational status of the semantic vector store, embedding provider,
    retrieval mode, and approved indexed chunk counts.
    """
    return document_intelligence_service.get_intelligence_status()


@router.post("/api/intelligence/reindex")
def reindex_intelligence():
    """
    POST /api/intelligence/reindex
    Rebuilds the semantic vector store and TF-IDF fallback from APPROVED documents only.
    """
    return document_intelligence_service.reindex_all_documents()
