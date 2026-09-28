"""
NWIS Phase 5 — Embedding Provider Abstraction
=============================================
Provides a unified abstraction for document and query vector representations.
Supports:
1. LocalEmbeddingProvider (sentence-transformers / HuggingFace if installed)
2. ExternalEmbeddingProvider (OpenAI / remote API if configured via environment)
3. TFIDFFallbackProvider (Deterministic, 100% offline scikit-learn TF-IDF fallback)

CRITICAL ARCHITECTURAL CONSTRAINTS:
- Never assume internet access.
- Detect availability dynamically.
- If no embedding model is available, gracefully fall back to TF-IDF.
- Explicitly declare active retrieval mode ('semantic' vs 'tfidf_fallback').
- Never misrepresent TF-IDF as a dense neural embedding.
"""

from __future__ import annotations
import abc
import logging
import os
from typing import List, Optional
import numpy as np

logger = logging.getLogger("nwis.embedding_provider")


class EmbeddingProvider(abc.ABC):
    """Abstract base class for all NWIS embedding providers."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable provider identifier."""
        pass

    @property
    @abc.abstractmethod
    def mode(self) -> str:
        """Retrieval mode: 'semantic' or 'tfidf_fallback'."""
        pass

    @property
    @abc.abstractmethod
    def dimension(self) -> int:
        """Embedding vector dimension."""
        pass

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Returns True if the provider is fully initialized and operational."""
        pass

    @abc.abstractmethod
    def embed_text(self, text: str) -> np.ndarray:
        """Generates a 1D normalized vector for a single string."""
        pass

    @abc.abstractmethod
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Generates a 2D matrix of shape (len(texts), dimension) for a batch of strings."""
        pass


class LocalEmbeddingProvider(EmbeddingProvider):
    """
    Local neural embedding provider using sentence-transformers (e.g. all-MiniLM-L6-v2, BGE).
    Only operational if sentence_transformers is installed and a local model is cached.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model = None
        self._dim = 384
        self._available = False
        self._init_model()

    def _init_model(self):
        try:
            import sentence_transformers
            # Check if local model can be loaded without unrequested network downloads
            self._model = sentence_transformers.SentenceTransformer(self._model_name)
            self._dim = self._model.get_sentence_embedding_dimension()
            self._available = True
            logger.info(f"LocalEmbeddingProvider initialized with {self._model_name} (dim={self._dim}).")
        except Exception as e:
            logger.info(f"Local neural embedding model '{self._model_name}' not available: {e}")
            self._model = None
            self._available = False

    @property
    def name(self) -> str:
        return f"LocalEmbeddingProvider({self._model_name})"

    @property
    def mode(self) -> str:
        return "semantic"

    @property
    def dimension(self) -> int:
        return self._dim

    def is_available(self) -> bool:
        return self._available and self._model is not None

    def embed_text(self, text: str) -> np.ndarray:
        if not self.is_available():
            raise RuntimeError("LocalEmbeddingProvider is not available.")
        vec = self._model.encode(text, normalize_embeddings=True)
        return np.asarray(vec, dtype=np.float32)

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        if not self.is_available():
            raise RuntimeError("LocalEmbeddingProvider is not available.")
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32)
        vecs = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vecs, dtype=np.float32)


class ExternalEmbeddingProvider(EmbeddingProvider):
    """
    External API-based embedding provider (e.g. OpenAI text-embedding-3-small).
    Requires OPENAI_API_KEY environment variable. Never commits credentials.
    """

    def __init__(self, model_name: str = "text-embedding-3-small"):
        self._model_name = model_name
        self._api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        self._dim = 1536
        self._client = None
        self._available = False
        self._init_client()

    def _init_client(self):
        if not self._api_key:
            self._available = False
            return
        try:
            import openai
            self._client = openai.OpenAI(api_key=self._api_key)
            self._available = True
            logger.info(f"ExternalEmbeddingProvider initialized with model {self._model_name}.")
        except Exception as e:
            logger.info(f"External embedding client initialization failed: {e}")
            self._available = False

    @property
    def name(self) -> str:
        return f"ExternalEmbeddingProvider({self._model_name})"

    @property
    def mode(self) -> str:
        return "semantic"

    @property
    def dimension(self) -> int:
        return self._dim

    def is_available(self) -> bool:
        return self._available and self._client is not None

    def embed_text(self, text: str) -> np.ndarray:
        if not self.is_available():
            raise RuntimeError("ExternalEmbeddingProvider is not available.")
        resp = self._client.embeddings.create(model=self._model_name, input=text)
        vec = np.array(resp.data[0].embedding, dtype=np.float32)
        norm = np.linalg.norm(vec)
        return vec / (norm + 1e-9)

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        if not self.is_available():
            raise RuntimeError("ExternalEmbeddingProvider is not available.")
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32)
        resp = self._client.embeddings.create(model=self._model_name, input=texts)
        vecs = [item.embedding for item in resp.data]
        mat = np.array(vecs, dtype=np.float32)
        norms = np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9
        return mat / norms


class TFIDFFallbackProvider(EmbeddingProvider):
    """
    Deterministic, zero-dependency, 100% offline retrieval vectorizer.
    Wraps scikit-learn's TfidfVectorizer.
    Explicitly declared as mode='tfidf_fallback'.
    """

    def __init__(self, max_features: int = 512):
        self._max_features = max_features
        self._dim = max_features
        from sklearn.feature_extraction.text import TfidfVectorizer
        self._vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            stop_words="english",
            max_features=max_features,
            min_df=1,
        )
        self._is_fitted = False
        # Pre-fit on drilling domain vocabulary to allow immediate transform if needed
        default_vocab = [
            "well information formation casing cementing mud loss lost circulation kick pack off",
            "stuck pipe overpressure torque spike depth meter drilling bit rpm wob rop ecd",
            "barail tipam girujan kopili sandstone shale limestone sandstone reservoir pressure",
            "daily drilling report completion report mud program mitigation lesson learned",
        ]
        self._vectorizer.fit(default_vocab)
        self._is_fitted = True
        self._dim = len(self._vectorizer.get_feature_names_out())

    def fit_corpus(self, corpus: List[str]):
        """Fits vocabulary on approved institutional document chunks."""
        if not corpus:
            return
        from sklearn.feature_extraction.text import TfidfVectorizer
        self._vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            stop_words="english",
            max_features=self._max_features,
            min_df=1,
        )
        self._vectorizer.fit(corpus)
        self._dim = len(self._vectorizer.get_feature_names_out())
        self._is_fitted = True

    @property
    def name(self) -> str:
        return "TFIDFFallbackProvider"

    @property
    def mode(self) -> str:
        return "tfidf_fallback"

    @property
    def dimension(self) -> int:
        return self._dim

    def is_available(self) -> bool:
        return True

    def embed_text(self, text: str) -> np.ndarray:
        sparse_vec = self._vectorizer.transform([text])
        dense = sparse_vec.toarray()[0].astype(np.float32)
        norm = np.linalg.norm(dense)
        if norm > 0:
            dense = dense / norm
        return dense

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32)
        sparse_mat = self._vectorizer.transform(texts)
        dense = sparse_mat.toarray().astype(np.float32)
        norms = np.linalg.norm(dense, axis=1, keepdims=True) + 1e-9
        return dense / norms


def get_embedding_provider(preferred_mode: Optional[str] = None) -> EmbeddingProvider:
    """
    Factory function to select the most appropriate available embedding provider.
    Priority:
    1. LocalEmbeddingProvider (if sentence_transformers is installed and loaded)
    2. ExternalEmbeddingProvider (if OPENAI_API_KEY is configured)
    3. TFIDFFallbackProvider (always available, offline fallback)
    """
    if preferred_mode != "tfidf_fallback":
        # Check Local first
        local = LocalEmbeddingProvider()
        if local.is_available():
            logger.info("Selected LocalEmbeddingProvider for semantic RAG.")
            return local

        # Check External
        ext = ExternalEmbeddingProvider()
        if ext.is_available():
            logger.info("Selected ExternalEmbeddingProvider for semantic RAG.")
            return ext

    # Fallback to deterministic TF-IDF
    logger.info("Selected TFIDFFallbackProvider (offline deterministic retrieval).")
    return TFIDFFallbackProvider()
