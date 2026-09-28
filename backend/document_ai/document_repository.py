"""
NWIS Phase 4 — Document Intelligence Repository
================================================
Provides a structured repository abstraction for WCR/DDR documents, chunks,
extractions, events, and engineer reviews. Designed so that SQLite or PostgreSQL/PostGIS
can seamlessly replace file-backed storage in production without altering service APIs.
"""

from __future__ import annotations
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple

logger = logging.getLogger("nwis.document_repository")

# Base directory for document storage
DOCUMENTS_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "documents"
UPLOADS_DIR = DOCUMENTS_DATA_DIR / "uploads"
DOCUMENTS_DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


# =====================================================================
# Domain Data Classes
# =====================================================================

@dataclass
class DocumentRecord:
    document_id: str
    filename: str
    file_path: str
    document_type: str  # WCR, DDR, DRILLING_REPORT, MUD_LOG, COMPLETION_REPORT, OTHER
    upload_timestamp: str
    uploaded_by: str
    processing_status: str  # UPLOADED, PROCESSING, EXTRACTED, REVIEW_REQUIRED, APPROVED, REJECTED, FAILED
    checksum: str
    source: str
    file_size_bytes: int = 0
    page_count: int = 0
    well_id: str = "UNMATCHED_WELL"
    matched_well_name: Optional[str] = None
    ocr_applied: bool = False
    rejection_reason: Optional[str] = None
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    classification_confidence: float = 0.95
    well_match_status: str = "UNMATCHED"  # MATCHED, AMBIGUOUS, UNMATCHED
    well_match_method: Optional[str] = None
    well_match_confidence: Optional[float] = None
    ambiguous_candidates: Optional[List[Dict[str, Any]]] = None


@dataclass
class DocumentChunk:
    chunk_id: str
    document_id: str
    well_id: str
    page_number: int
    section: str  # WELL INFORMATION, FORMATION, DRILLING PARAMETERS, MUD PROGRAM, DRILLING EVENTS, etc.
    text: str
    document_type: str
    depth_from: Optional[float] = None
    depth_to: Optional[float] = None
    formation: Optional[str] = None
    is_approved: bool = False


@dataclass
class DocumentExtraction:
    extraction_id: str
    document_id: str
    field: str
    value: Any
    unit: Optional[str]
    confidence: float
    source_text: str
    page_number: int
    status: str = "REVIEW_REQUIRED"  # REVIEW_REQUIRED, APPROVED, REJECTED, EDITED
    edited_value: Optional[Any] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None


@dataclass
class DocumentEvent:
    event_id: str
    document_id: str
    well_id: str
    event_type: str  # mud_loss, stuck_pipe, kick, overpressure, torque_spike, UNKNOWN
    raw_event_text: str
    depth_md: Optional[float]
    source_page: int
    confidence: float
    hazard_assumption: str
    depth_from: Optional[float] = None
    depth_to: Optional[float] = None
    formation: Optional[str] = None
    status: str = "REVIEW_REQUIRED"  # REVIEW_REQUIRED, APPROVED, REJECTED
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None


@dataclass
class DocumentReview:
    review_id: str
    document_id: str
    reviewer: str
    action: str  # APPROVE, REJECT, EDIT, APPROVE_ALL_HIGH
    timestamp: str
    comments: Optional[str] = None


# =====================================================================
# Repository Interface Protocol
# =====================================================================

class IDocumentRepository(Protocol):
    def save_document(self, doc: DocumentRecord) -> DocumentRecord: ...
    def get_document(self, document_id: str) -> Optional[DocumentRecord]: ...
    def get_document_by_checksum(self, checksum: str) -> Optional[DocumentRecord]: ...
    def list_documents(self, status: Optional[str] = None, document_type: Optional[str] = None, limit: int = 100) -> List[DocumentRecord]: ...
    def update_document(self, doc: DocumentRecord) -> DocumentRecord: ...
    def delete_document(self, document_id: str) -> bool: ...

    def save_chunks(self, chunks: List[DocumentChunk]) -> None: ...
    def get_chunks_for_document(self, document_id: str) -> List[DocumentChunk]: ...
    def get_approved_chunks(self) -> List[DocumentChunk]: ...

    def save_extractions(self, extractions: List[DocumentExtraction]) -> None: ...
    def get_extractions_for_document(self, document_id: str) -> List[DocumentExtraction]: ...
    def update_extraction(self, extraction: DocumentExtraction) -> DocumentExtraction: ...

    def save_events(self, events: List[DocumentEvent]) -> None: ...
    def get_events_for_document(self, document_id: str) -> List[DocumentEvent]: ...
    def get_approved_events(self) -> List[DocumentEvent]: ...
    def update_event(self, event: DocumentEvent) -> DocumentEvent: ...

    def record_review(self, review: DocumentReview) -> None: ...
    def get_reviews_for_document(self, document_id: str) -> List[DocumentReview]: ...


# =====================================================================
# JSON / File-Backed Repository Implementation
# =====================================================================

class JsonDocumentRepository(IDocumentRepository):
    """
    Thread-safe file-backed repository using atomic JSON persistence.
    Provides complete institutional memory and review state tracking.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or DOCUMENTS_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.docs_file = self.data_dir / "documents_registry.json"
        self.chunks_file = self.data_dir / "chunks_registry.json"
        self.extractions_file = self.data_dir / "extractions_registry.json"
        self.events_file = self.data_dir / "events_registry.json"
        self.reviews_file = self.data_dir / "reviews_audit.json"
        self.approved_events_file = self.data_dir / "approved_document_events.json"

        self._init_files()

    def _init_files(self):
        for path in [
            self.docs_file,
            self.chunks_file,
            self.extractions_file,
            self.events_file,
            self.reviews_file,
            self.approved_events_file,
        ]:
            if not path.exists():
                path.write_text("{}", encoding="utf-8")

    def _read_json(self, path: Path) -> Dict[str, Any]:
        try:
            if not path.exists():
                return {}
            content = path.read_text(encoding="utf-8").strip()
            return json.loads(content) if content else {}
        except Exception as e:
            logger.error(f"Error reading JSON from {path}: {e}")
            return {}

    def _write_json(self, path: Path, data: Dict[str, Any]):
        content = json.dumps(data, indent=2)
        try:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(content, encoding="utf-8")
            try:
                tmp.replace(path)
            except OSError:
                import time
                time.sleep(0.05)
                try:
                    tmp.replace(path)
                except OSError:
                    path.write_text(content, encoding="utf-8")
        except Exception as e:
            logger.error(f"Error writing JSON to {path}: {e}")

    # Document Operations
    def save_document(self, doc: DocumentRecord) -> DocumentRecord:
        data = self._read_json(self.docs_file)
        data[doc.document_id] = asdict(doc)
        self._write_json(self.docs_file, data)
        return doc

    def get_document(self, document_id: str) -> Optional[DocumentRecord]:
        data = self._read_json(self.docs_file)
        raw = data.get(document_id)
        if not raw:
            for k, v in data.items():
                if k.upper() == document_id.upper():
                    raw = v
                    break
        if not raw:
            if document_id.startswith("DOC-WCR-"):
                raw = data.get("DOC-" + document_id[8:])
            elif document_id.startswith("DOC-"):
                raw = data.get("DOC-WCR-" + document_id[4:])
        return DocumentRecord(**raw) if raw else None

    def get_document_by_checksum(self, checksum: str) -> Optional[DocumentRecord]:
        data = self._read_json(self.docs_file)
        for raw in data.values():
            if raw.get("checksum") == checksum:
                return DocumentRecord(**raw)
        return None

    def list_documents(
        self,
        status: Optional[str] = None,
        document_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[DocumentRecord]:
        data = self._read_json(self.docs_file)
        docs = [DocumentRecord(**v) for v in data.values()]
        if status:
            docs = [d for d in docs if d.processing_status == status]
        if document_type:
            docs = [d for d in docs if d.document_type == document_type]
        docs.sort(key=lambda d: d.upload_timestamp, reverse=True)
        return docs[:limit]

    def update_document(self, doc: DocumentRecord) -> DocumentRecord:
        return self.save_document(doc)

    def delete_document(self, document_id: str) -> bool:
        data = self._read_json(self.docs_file)
        if document_id in data:
            del data[document_id]
            self._write_json(self.docs_file, data)
            return True
        return False

    # Chunks Operations
    def save_chunks(self, chunks: List[DocumentChunk]) -> None:
        data = self._read_json(self.chunks_file)
        for chk in chunks:
            data[chk.chunk_id] = asdict(chk)
        self._write_json(self.chunks_file, data)

    def _get_target_ids(self, document_id: str) -> set:
        target_ids = {document_id, document_id.upper()}
        if document_id.startswith("DOC-WCR-"):
            short = "DOC-" + document_id[8:]
            target_ids.add(short)
            target_ids.add(short.upper())
        elif document_id.startswith("DOC-"):
            wcr = "DOC-WCR-" + document_id[4:]
            target_ids.add(wcr)
            target_ids.add(wcr.upper())
        return target_ids

    def get_chunks_for_document(self, document_id: str) -> List[DocumentChunk]:
        data = self._read_json(self.chunks_file)
        target_ids = self._get_target_ids(document_id)
        return [
            DocumentChunk(**v)
            for v in data.values()
            if v.get("document_id") in target_ids
        ]

    def get_approved_chunks(self) -> List[DocumentChunk]:
        data = self._read_json(self.chunks_file)
        return [DocumentChunk(**v) for v in data.values() if v.get("is_approved")]

    # Extractions Operations
    def save_extractions(self, extractions: List[DocumentExtraction]) -> None:
        data = self._read_json(self.extractions_file)
        for ext in extractions:
            data[ext.extraction_id] = asdict(ext)
        self._write_json(self.extractions_file, data)

    def get_extractions_for_document(self, document_id: str) -> List[DocumentExtraction]:
        data = self._read_json(self.extractions_file)
        target_ids = self._get_target_ids(document_id)
        return [
            DocumentExtraction(**v)
            for v in data.values()
            if v.get("document_id") in target_ids
        ]

    def update_extraction(self, extraction: DocumentExtraction) -> DocumentExtraction:
        data = self._read_json(self.extractions_file)
        data[extraction.extraction_id] = asdict(extraction)
        self._write_json(self.extractions_file, data)
        return extraction

    # Events Operations
    def save_events(self, events: List[DocumentEvent]) -> None:
        data = self._read_json(self.events_file)
        for evt in events:
            data[evt.event_id] = asdict(evt)
        self._write_json(self.events_file, data)

    def get_events_for_document(self, document_id: str) -> List[DocumentEvent]:
        data = self._read_json(self.events_file)
        target_ids = self._get_target_ids(document_id)
        return [
            DocumentEvent(**v)
            for v in data.values()
            if v.get("document_id") in target_ids
        ]

    def get_approved_events(self) -> List[DocumentEvent]:
        data = self._read_json(self.events_file)
        return [
            DocumentEvent(**v)
            for v in data.values()
            if v.get("status") == "APPROVED"
        ]

    def update_event(self, event: DocumentEvent) -> DocumentEvent:
        data = self._read_json(self.events_file)
        data[event.event_id] = asdict(event)
        self._write_json(self.events_file, data)

        # Synchronize approved events store
        if event.status == "APPROVED":
            self._sync_approved_event(event)
        return event

    def _sync_approved_event(self, event: DocumentEvent):
        approved_data = self._read_json(self.approved_events_file)
        approved_data[event.event_id] = asdict(event)
        self._write_json(self.approved_events_file, approved_data)

    # Reviews Operations
    def record_review(self, review: DocumentReview) -> None:
        data = self._read_json(self.reviews_file)
        data[review.review_id] = asdict(review)
        self._write_json(self.reviews_file, data)

    def get_reviews_for_document(self, document_id: str) -> List[DocumentReview]:
        data = self._read_json(self.reviews_file)
        target_ids = self._get_target_ids(document_id)
        return [
            DocumentReview(**v)
            for v in data.values()
            if v.get("document_id") in target_ids
        ]


# Singleton repository instance
document_repository = JsonDocumentRepository()
