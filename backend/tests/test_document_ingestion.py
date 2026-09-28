"""
NWIS Phase 4 — Test Document Ingestion
======================================
Tests file upload security, format validation, checksum deduplication,
corrupted file rejection, and document type classification.
"""

import io
import pytest
from pathlib import Path
import pypdf
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.document_ai.document_ingestion import (
    DocumentIngestionEngine,
    IngestionValidationError,
    document_ingestion_engine,
)
from backend.document_ai.document_classifier import document_classifier
from backend.document_ai.document_repository import document_repository

client = TestClient(app)


def create_sample_pdf(text: str) -> bytes:
    """Helper to create minimal valid PDF bytes with text stream."""
    writer = pypdf.PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    # Inject standard text object stream
    writer.add_metadata({"/Title": "WCR Test Report", "/Author": "NWIS"})
    buf = io.BytesIO()
    writer.write(buf)
    # Embed plain text comment stream for extractor simulation
    pdf_bytes = buf.getvalue()
    return pdf_bytes + f"\n% NWIS_TEXT_STREAM: {text}\n".encode("utf-8")


def test_valid_txt_document_ingestion(tmp_path):
    """Verifies successful ingestion of technical plain-text report."""
    txt_content = (
        "WELL INFORMATION\n"
        "Well Name: KK-DW-17-1\n"
        "Well ID: WELL-000050\n"
        "Operator: ONGC\n"
        "Total Depth: 1617.0 m\n"
        "Latitude: 13.525000\n"
        "Longitude: 72.556400\n\n"
        "FORMATION\n"
        "Top Barail Formation reached at 1100 m MD. Lithology: Shale with thin Sandstone streaks.\n\n"
        "DRILLING EVENTS\n"
        "Severe mud loss observed at 1132 m MD. Lost 45 bbls of drilling fluid. Pumped LCM pill."
    ).encode("utf-8")

    doc, extractions, events = document_ingestion_engine.ingest_document(
        filename="well_completion_report_test.txt",
        content=txt_content,
        uploaded_by="Drilling Engineer 1",
    )

    assert doc.document_id.startswith("DOC-")
    assert doc.processing_status == "REVIEW_REQUIRED"
    assert doc.well_id == "WELL-000050"
    assert doc.matched_well_name == "WELL-000050" or doc.matched_well_name is not None
    assert len(extractions) > 0
    assert any(e.field == "well_id" for e in extractions)
    assert any(e.field == "total_depth" and e.value == 1617.0 for e in extractions)
    assert len(events) >= 1
    assert any(ev.event_type == "mud_loss" for ev in events)


def test_duplicate_document_checksum_prevention():
    """Verifies that uploading the exact same document returns existing record."""
    content = b"WELL INFORMATION\nWell ID: WELL-000001\nUnique Checksum Test Sample."
    doc1, _, _ = document_ingestion_engine.ingest_document(
        filename="checksum_test_1.txt",
        content=content,
    )
    doc2, _, _ = document_ingestion_engine.ingest_document(
        filename="checksum_test_2.txt",
        content=content,
    )

    assert doc1.document_id == doc2.document_id
    assert doc1.checksum == doc2.checksum


def test_empty_file_rejection():
    """Assures empty file (0 bytes) raises validation error."""
    with pytest.raises(IngestionValidationError, match="empty"):
        document_ingestion_engine.validate_file("empty.pdf", b"")


def test_path_traversal_filename_sanitization():
    """Assures filename path traversal attacks are rejected."""
    with pytest.raises(IngestionValidationError, match="path traversal"):
        document_ingestion_engine.validate_file("../../../etc/passwd.pdf", b"%PDF-1.4 dummy")


def test_invalid_extension_rejection():
    """Assures unauthorized file types are rejected."""
    with pytest.raises(IngestionValidationError, match="Unsupported file extension"):
        document_ingestion_engine.validate_file("malicious.exe", b"binarycontent")


def test_corrupted_pdf_rejection():
    """Assures invalid PDF lacking %PDF- magic bytes is rejected."""
    with pytest.raises(IngestionValidationError, match="Missing standard %PDF- header"):
        document_ingestion_engine.validate_file("corrupted.pdf", b"not a valid pdf header")


def test_document_classifier_heuristics():
    """Verifies classification into domain categories WCR, DDR, Mud Log."""
    wcr_text = "WELL COMPLETION REPORT\nFinal Well Summary\nSpud Date: 12/01/2021\nRig Release: 05/03/2021"
    doc_type, conf = document_classifier.classify(wcr_text, filename="final_wcr.pdf")
    assert doc_type == "WCR"
    assert conf >= 0.85

    ddr_text = "DAILY DRILLING REPORT\n24 Hour Operations Summary\nMidnight Depth: 2450 m\nBHA Record"
    doc_type, conf = document_classifier.classify(ddr_text, filename="daily_drilling_report_04.pdf")
    assert doc_type == "DDR"
    assert conf >= 0.85


def test_upload_api_endpoint():
    """Verifies POST /api/documents/upload via FastAPI TestClient."""
    content = (
        "WELL INFORMATION\n"
        "Well Name: TEST-EXPLORER-1\n"
        "Total Depth: 3200 m\n"
        "DRILLING EVENTS\n"
        "Pipe stuck at 2850 m due to differential sticking."
    ).encode("utf-8")

    files = {"file": ("test_upload_doc.txt", io.BytesIO(content), "text/plain")}
    response = client.post(
        "/api/documents/upload",
        files=files,
        data={"document_type": "WCR", "uploaded_by": "Senior Petrophysicist"},
    )

    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    assert res_data["document"]["document_id"].startswith("DOC-")
    assert res_data["requires_review"] is True
    assert "review_url" in res_data
