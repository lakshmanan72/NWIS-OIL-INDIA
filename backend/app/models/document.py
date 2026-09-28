from pydantic import BaseModel, Field
from typing import List, Optional


class DocumentMetadataRecord(BaseModel):
    document_id: str
    well_id: str
    document_type: str
    document_title: str
    document_date: str
    source_file: str
    page_count: int
    file_path: str
    language: str
    ocr_status: str
    extraction_status: str


class DocumentMetadataResponse(BaseModel):
    well_id: str
    count: int
    documents: List[DocumentMetadataRecord]


class WellLinkedDocumentResponse(BaseModel):
    well_id: str
    document_id: str
    document_type: str = "WCR"
    file_name: str
    status: str = "VERIFIED"
    has_document: bool = True
    review_url: str
    source: Optional[str] = None
    upload_timestamp: Optional[str] = None
