"""
NWIS Phase 4 — Document AI & Institutional Memory
=================================================
Automated processing, entity/event extraction, and RAG search
for Well Completion Reports (WCR), Daily Drilling Reports (DDR), and engineering logs.
"""

from .chunker import document_chunker
from .document_classifier import document_classifier
from .document_ingestion import document_ingestion_engine
from .document_repository import (
    DocumentChunk,
    DocumentEvent,
    DocumentExtraction,
    DocumentRecord,
    DocumentReview,
    document_repository,
)
from .document_service import document_intelligence_service
from .entity_extractor import entity_extractor
from .event_extractor import event_extractor
from .ocr_processor import ocr_processor
from .pdf_extractor import pdf_extractor
from .wcr_extractor import wcr_extractor, WCRExtractor
from .embedding_provider import (
    EmbeddingProvider,
    LocalEmbeddingProvider,
    ExternalEmbeddingProvider,
    TFIDFFallbackProvider,
    get_embedding_provider,
)
from .vector_store import VectorStore, LocalVectorStore, local_vector_store
from .reranker import Reranker, RerankedItem, domain_reranker
from .context_builder import ContextBuilder, EvidencePacket, context_builder
from .llm_provider import (
    LLMProvider,
    ExternalLLMProvider,
    DeterministicFallbackProvider,
    get_llm_provider,
)
from .citation_validator import CitationValidator, citation_validator

__all__ = [
    "document_repository",
    "document_ingestion_engine",
    "document_intelligence_service",
    "pdf_extractor",
    "ocr_processor",
    "document_classifier",
    "document_chunker",
    "entity_extractor",
    "event_extractor",
    "DocumentRecord",
    "DocumentChunk",
    "DocumentExtraction",
    "DocumentEvent",
    "DocumentReview",
    "EmbeddingProvider",
    "LocalEmbeddingProvider",
    "ExternalEmbeddingProvider",
    "TFIDFFallbackProvider",
    "get_embedding_provider",
    "VectorStore",
    "LocalVectorStore",
    "local_vector_store",
    "Reranker",
    "RerankedItem",
    "domain_reranker",
    "ContextBuilder",
    "EvidencePacket",
    "context_builder",
    "LLMProvider",
    "ExternalLLMProvider",
    "DeterministicFallbackProvider",
    "get_llm_provider",
    "CitationValidator",
    "citation_validator",
]
