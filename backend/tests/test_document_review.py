"""
NWIS Phase 4 — Test Document Review & Approval Gate
===================================================
Tests engineer review workflow, approval gate isolation, editing, batch approval,
canonical well matching, and the controlled new well candidate creation workflow.
"""

import uuid
import pytest
from backend.document_ai.document_ingestion import document_ingestion_engine
from backend.document_ai.document_service import document_intelligence_service
from backend.document_ai.document_repository import document_repository


def test_review_workflow_and_approval_gate():
    """Verifies that chunks and events are only approved and indexed after engineer approval."""
    run_id = uuid.uuid4().hex[:8]
    content = (
        f"WELL INFORMATION [Run: {run_id}]\n"
        "Well Name: KK-DW-17-1\n"
        "Well ID: WELL-000050\n"
        "Total Depth: 1617.0 m\n"
        "DRILLING EVENTS\n"
        "Lost circulation observed at 1132 m."
    ).encode("utf-8")

    doc, extractions, events = document_ingestion_engine.ingest_document(
        filename=f"review_flow_test_{run_id}.txt",
        content=content,
        uploaded_by="Rig Geologist",
    )

    doc_id = doc.document_id

    # 1. State must be REVIEW_REQUIRED initially
    assert doc.processing_status == "REVIEW_REQUIRED"
    chunks_before = document_repository.get_chunks_for_document(doc_id)
    assert all(not chk.is_approved for chk in chunks_before), "Chunks were pre-maturely marked approved!"

    # 2. Test individual edit of an extraction
    td_ext = next(e for e in extractions if e.field == "total_depth")
    edited = document_intelligence_service.edit_extraction(
        extraction_id=td_ext.extraction_id,
        edited_value=1620.0,
        reviewer="Lead Engineer",
    )
    assert edited.status == "EDITED"
    assert edited.edited_value == 1620.0

    # 3. Test batch approval of high confidence items
    batch_res = document_intelligence_service.approve_all_high_confidence(
        document_id=doc_id,
        min_confidence=0.85,
        reviewer="Lead Engineer",
    )
    assert batch_res["approved_extractions"] > 0

    # 4. Formally approve document (Approval Gate)
    approved_doc = document_intelligence_service.approve_document(
        document_id=doc_id,
        reviewer="Supervising Drilling Engineer",
        comments="All technical parameters verified against operational log.",
    )

    assert approved_doc.processing_status == "APPROVED"
    assert approved_doc.approved_by == "Supervising Drilling Engineer"

    # Chunks must now be approved for RAG
    chunks_after = document_repository.get_chunks_for_document(doc_id)
    assert all(chk.is_approved for chk in chunks_after)

    # Approved events must be in approved store
    approved_events = document_repository.get_approved_events()
    assert any(ev.document_id == doc_id and ev.status == "APPROVED" for ev in approved_events)


def test_rejection_isolation():
    """Confirms rejected documents and facts NEVER enter approved stores or RAG index."""
    run_id = uuid.uuid4().hex[:8]
    content = f"WELL INFORMATION [Run: {run_id}]\nUnverified operational claims from unknown source.".encode("utf-8")
    doc, _, _ = document_ingestion_engine.ingest_document(
        filename=f"rejected_sample_{run_id}.txt",
        content=content,
    )

    doc_id = doc.document_id
    rejected_doc = document_intelligence_service.reject_document(
        document_id=doc_id,
        reviewer="QA Manager",
        reason="Fails source verification checklist.",
    )

    assert rejected_doc.processing_status == "REJECTED"
    chunks = document_repository.get_chunks_for_document(doc_id)
    assert all(not chk.is_approved for chk in chunks)

    approved_chunks = document_repository.get_approved_chunks()
    assert not any(c.document_id == doc_id for c in approved_chunks)


def test_canonical_well_matching_and_linking():
    """Tests automatic well matching and explicit linking of unmatched documents."""
    run_id = uuid.uuid4().hex[:8]
    # 1. Unmatched document
    unmatched_content = (
        f"WELL INFORMATION [Run: {run_id}]\n"
        f"Well Name: RANDOM-EXPLORATION-{run_id}\n"
        "Total Depth: 4000 m\n"
    ).encode("utf-8")

    doc_unmatched, _, _ = document_ingestion_engine.ingest_document(
        filename=f"unmatched_test_{run_id}.txt",
        content=unmatched_content,
    )

    assert doc_unmatched.well_id == "UNMATCHED_WELL"

    # 2. Explicit engineer linking to canonical well WELL-000050
    linked_doc = document_intelligence_service.link_document_to_well(
        document_id=doc_unmatched.document_id,
        well_id="WELL-000050",
        reviewer="Subsurface Data Manager",
    )

    assert linked_doc.well_id == "WELL-000050"
    chunks = document_repository.get_chunks_for_document(linked_doc.document_id)
    assert all(c.well_id == "WELL-000050" for c in chunks)


def test_new_well_workflow_confirmation():
    """Verifies controlled new well candidate creation with coordinate validation."""
    run_id = uuid.uuid4().hex[:8]
    content = f"WELL INFORMATION [Run: {run_id}]\nNew discovery well report.".encode("utf-8")
    doc, _, _ = document_ingestion_engine.ingest_document(
        filename=f"new_discovery_{run_id}.txt",
        content=content,
    )

    test_lat = round(14.0 + (int(run_id, 16) % 1000) * 0.01, 6)
    test_lon = round(73.0 + (int(run_id, 16) % 500) * 0.01, 6)
    well_data = {
        "well_name": f"DISCOVERY-{run_id}",
        "latitude": test_lat,
        "longitude": test_lon,
        "field": f"Offshore Block {run_id}",
        "basin": "Kerala-Konkan",
        "block": f"KK-OS-{run_id}",
        "trajectory": "Directional",
    }

    new_well = document_intelligence_service.create_new_well_candidate(
        document_id=doc.document_id,
        well_data=well_data,
        reviewer="Chief Geologist",
    )

    assert new_well["well_id"].startswith(("WELL-0", "WELL-NEW-", "WELL-"))
    assert new_well["well_name"] == f"DISCOVERY-{run_id}"
    assert new_well["latitude"] == test_lat
    assert new_well["source_document"] == doc.document_id

    # Verify invalid coordinates rejected
    with pytest.raises(ValueError, match="geographical bounds"):
        document_intelligence_service.create_new_well_candidate(
            document_id=doc.document_id,
            well_data={**well_data, "latitude": 195.0},
        )
