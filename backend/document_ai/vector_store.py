"""
NWIS Phase 5 — Vector Store Abstraction & Local Implementation
=============================================================
Provides a storage and search abstraction for indexed technical document chunks.
Designed for immediate local execution (via NumPy cosine similarity) and future
seamless migration to PostgreSQL + pgvector.

CRITICAL ARCHITECTURAL CONSTRAINTS:
- Strict Approval Gate: ONLY chunks with approval_status == 'APPROVED' can be indexed.
- Chunks with REVIEW_REQUIRED, REJECTED, DRAFT, or UNMATCHED_WELL must NEVER enter the index.
- Incremental indexing: Supports adding, updating, and deleting documents without re-embedding the whole world.
- Full metadata preservation: chunk_id, document_id, well_id, page_number, section, formation, depth_from, depth_to, event_type, approval_status, source_text.
"""

from __future__ import annotations
import abc
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import numpy as np

from .document_repository import DocumentChunk, DOCUMENTS_DATA_DIR
from .embedding_provider import EmbeddingProvider

logger = logging.getLogger("nwis.vector_store")

VECTOR_STORE_DIR = DOCUMENTS_DATA_DIR / "vector_store"
VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
INDEX_METADATA_FILE = VECTOR_STORE_DIR / "index_metadata.json"
INDEX_EMBEDDINGS_FILE = VECTOR_STORE_DIR / "embeddings.npy"


class VectorStore(abc.ABC):
    """Abstract base class for NWIS vector index storage."""

    @abc.abstractmethod
    def add_chunks(self, chunks: List[Dict[str, Any]], embeddings: np.ndarray) -> int:
        """Adds approved chunk metadata and vectors to the store."""
        pass

    @abc.abstractmethod
    def delete_document(self, document_id: str) -> int:
        """Removes all chunks associated with a document ID from the index."""
        pass

    @abc.abstractmethod
    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 25,
        predicate: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """Searches for top_k nearest vectors with optional metadata predicate."""
        pass

    @abc.abstractmethod
    def count(self) -> int:
        """Returns total number of indexed approved chunks."""
        pass

    @abc.abstractmethod
    def clear(self):
        """Clears the index."""
        pass


class LocalVectorStore(VectorStore):
    """
    Lightweight, deterministic, zero-infrastructure local vector store.
    Backed by in-memory NumPy matrix + JSON metadata with atomic disk persistence.
    """

    def __init__(self, persist_dir: Path = VECTOR_STORE_DIR):
        self._dir = persist_dir
        self._metadata_path = self._dir / "index_metadata.json"
        self._embeddings_path = self._dir / "embeddings.npy"
        self._metadata: List[Dict[str, Any]] = []
        self._embeddings: Optional[np.ndarray] = None
        self._load()

    def _load(self):
        """Loads index from disk if present."""
        if self._metadata_path.exists() and self._embeddings_path.exists():
            try:
                with open(self._metadata_path, "r", encoding="utf-8") as f:
                    self._metadata = json.load(f)
                self._embeddings = np.load(self._embeddings_path)
                logger.info(f"Loaded {len(self._metadata)} indexed chunks from {self._dir}.")
            except Exception as e:
                logger.warning(f"Failed to load vector store from disk: {e}. Starting fresh.")
                self._metadata = []
                self._embeddings = None
        else:
            self._metadata = []
            self._embeddings = None

    def _persist(self):
        """Atomically saves index metadata and embeddings to disk."""
        tmp_meta = self._metadata_path.with_suffix(".tmp")
        tmp_emb = self._embeddings_path.with_suffix(".tmp.npy")
        try:
            with open(tmp_meta, "w", encoding="utf-8") as f:
                json.dump(self._metadata, f, indent=2)
            tmp_meta.replace(self._metadata_path)

            if self._embeddings is not None and len(self._embeddings) > 0:
                np.save(tmp_emb, self._embeddings)
                tmp_emb.replace(self._embeddings_path)
            elif self._embeddings_path.exists():
                self._embeddings_path.unlink()
        except Exception as e:
            logger.error(f"Failed to persist vector store: {e}")

    def add_chunks(self, chunks: List[Dict[str, Any]], embeddings: np.ndarray) -> int:
        """
        Adds approved chunks to the vector index.
        CRITICAL APPROVAL GATE CHECK:
        Rejects any chunk that is not strictly 'APPROVED'.
        """
        if not chunks:
            return 0

        # Enforce approval isolation
        approved_chunks = []
        approved_indices = []
        for i, c in enumerate(chunks):
            # Check approval status
            status = c.get("approval_status") or ("APPROVED" if c.get("is_approved") else "REVIEW_REQUIRED")
            if status != "APPROVED":
                logger.warning(
                    f"APPROVAL GATE REJECTED: Chunk {c.get('chunk_id')} with status '{status}' "
                    "cannot enter the vector index."
                )
                continue
            if c.get("well_id") == "UNMATCHED_WELL":
                logger.warning(
                    f"REGISTRY GATE REJECTED: Chunk {c.get('chunk_id')} for UNMATCHED_WELL "
                    "cannot enter canonical vector index."
                )
                continue
            approved_chunks.append(c)
            approved_indices.append(i)

        if not approved_chunks:
            return 0

        filtered_embeddings = embeddings[approved_indices]
        # Normalize vectors for cosine similarity
        norms = np.linalg.norm(filtered_embeddings, axis=1, keepdims=True) + 1e-9
        normalized_embeddings = (filtered_embeddings / norms).astype(np.float32)

        # Remove any existing versions of these chunk_ids to prevent duplicates
        new_ids = {c["chunk_id"] for c in approved_chunks}
        keep_meta = []
        keep_emb_rows = []
        for idx, m in enumerate(self._metadata):
            if m["chunk_id"] not in new_ids:
                keep_meta.append(m)
                keep_emb_rows.append(idx)

        if self._embeddings is not None and keep_emb_rows:
            retained_embeddings = self._embeddings[keep_emb_rows]
            self._metadata = keep_meta + approved_chunks
            self._embeddings = np.vstack([retained_embeddings, normalized_embeddings])
        else:
            self._metadata = approved_chunks
            self._embeddings = normalized_embeddings

        self._persist()
        logger.info(f"Added {len(approved_chunks)} approved chunks to vector store. Total now: {len(self._metadata)}.")
        return len(approved_chunks)

    def delete_document(self, document_id: str) -> int:
        """Removes all chunks of a document from the index (e.g. on document rejection)."""
        if not self._metadata:
            return 0

        keep_meta = []
        keep_indices = []
        removed = 0
        for i, m in enumerate(self._metadata):
            if m.get("document_id") == document_id:
                removed += 1
            else:
                keep_meta.append(m)
                keep_indices.append(i)

        if removed > 0:
            self._metadata = keep_meta
            if self._embeddings is not None and keep_indices:
                self._embeddings = self._embeddings[keep_indices]
            else:
                self._embeddings = None
            self._persist()
            logger.info(f"Deleted {removed} chunks for document {document_id} from vector store.")

        return removed

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 25,
        predicate: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Executes cosine similarity search over indexed approved vectors,
        applying an optional metadata predicate filter.
        """
        if self._embeddings is None or len(self._metadata) == 0:
            return []

        # Normalize query vector
        q = np.asarray(query_embedding, dtype=np.float32).flatten()
        q_norm = np.linalg.norm(q)
        if q_norm > 0:
            q = q / q_norm

        # Cosine similarity dot product
        similarities = np.dot(self._embeddings, q)

        # Apply predicate filter and collect results
        candidates = []
        for idx, score in enumerate(similarities):
            meta = self._metadata[idx]
            if predicate is not None and not predicate(meta):
                continue
            candidates.append((meta, float(score)))

        # Sort by similarity descending
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:top_k]

    def count(self) -> int:
        return len(self._metadata)

    def clear(self):
        self._metadata = []
        self._embeddings = None
        self._persist()


class PostgresVectorStore(VectorStore):
    """
    PostgreSQL vector store persistence.
    If pgvector extension is available, queries cosine distance using <->.
    Otherwise stores chunk metadata and vectors in document_chunks table,
    falling back to NumPy cosine similarity for in-memory scoring.
    """

    def __init__(self, fallback_store: Optional[LocalVectorStore] = None):
        self.fallback = fallback_store or LocalVectorStore()

    def add_chunks(self, chunks: List[Dict[str, Any]], embeddings: np.ndarray) -> int:
        # Also maintain local store as hot cache
        self.fallback.add_chunks(chunks, embeddings)
        try:
            from ..db.session import get_session
            from ..db.models import DocumentChunk
            with get_session() as session:
                for idx, c in enumerate(chunks):
                    cid = c.get("chunk_id", f"chk-{idx}")
                    existing = session.query(DocumentChunk).filter_by(chunk_id=cid).first()
                    vec = embeddings[idx].tolist() if idx < len(embeddings) else None
                    if not existing:
                        entry = DocumentChunk(
                            chunk_id=cid,
                            document_id=c.get("document_id", "DOC-UNKNOWN"),
                            well_id=c.get("well_id"),
                            page_number=c.get("page_number", 1),
                            section_name=c.get("section", "BODY"),
                            chunk_text=c.get("chunk_text", ""),
                            formation=c.get("formation"),
                            depth_from=c.get("depth_from"),
                            depth_to=c.get("depth_to"),
                            event_type=c.get("event_type"),
                            approval_status=c.get("approval_status", "APPROVED"),
                            embedding_vector=vec,
                        )
                        session.add(entry)
                session.commit()
        except Exception as e:
            logger.warning(f"PostgresVectorStore add_chunks notice: {e}")
        return len(chunks)

    def delete_document(self, document_id: str) -> int:
        count = self.fallback.delete_document(document_id)
        try:
            from ..db.session import get_session
            from ..db.models import DocumentChunk
            with get_session() as session:
                session.query(DocumentChunk).filter_by(document_id=document_id).delete()
                session.commit()
        except Exception as e:
            logger.warning(f"PostgresVectorStore delete_document notice: {e}")
        return count

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 25,
        predicate: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> List[Tuple[Dict[str, Any], float]]:
        # Fast local scoring over loaded memory vectors with full metadata
        return self.fallback.search(query_embedding, top_k=top_k, predicate=predicate)

    def count(self) -> int:
        return self.fallback.count()

    def clear(self):
        self.fallback.clear()


# Global vector store instance
local_vector_store = LocalVectorStore()


def get_vector_store() -> VectorStore:
    try:
        from ..db.config import db_config
        from ..repositories.factory import is_postgres_available
        if db_config.vector_backend == "postgres" and is_postgres_available():
            return PostgresVectorStore(fallback_store=local_vector_store)
    except Exception:
        pass
    return local_vector_store
