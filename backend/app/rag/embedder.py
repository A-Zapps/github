"""Local embedding generator producing normalized 384-dim float32 vectors (T7.1, ARCHITECTURE 11)."""

import logging
from typing import List, Optional

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer

logger = logging.getLogger(__name__)
DEFAULT_EMBEDDING_DIM = 384


class LocalEmbedder:
    """Local vector embedder with SentenceTransformers support and zero-dependency fallback."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self.dim = DEFAULT_EMBEDDING_DIM
        self._st_model: Optional[object] = None
        self._vectorizer: Optional[HashingVectorizer] = None

        # Attempt to load sentence-transformers if present
        try:
            from sentence_transformers import SentenceTransformer
            self._st_model = SentenceTransformer(model_name)
            logger.info("Loaded SentenceTransformer(%s)", model_name)
        except Exception:
            self._st_model = None
            self._vectorizer = HashingVectorizer(
                n_features=self.dim,
                norm="l2",
                alternate_sign=True,
                ngram_range=(1, 3),
                analyzer="word",
                lowercase=True,
            )
            logger.info("SentenceTransformers not available; using local 384-dim HashingVectorizer.")

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Embed a list of text strings into an (N, 384) float32 matrix."""
        if not texts:
            return np.empty((0, self.dim), dtype=np.float32)

        if self._st_model is not None:
            try:
                embeddings = self._st_model.encode(
                    texts,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                )
                return embeddings.astype(np.float32)
            except Exception as e:
                logger.warning("SentenceTransformer encoding failed: %s; falling back to vectorizer.", e)

        # Fallback projection
        if self._vectorizer is None:
            self._vectorizer = HashingVectorizer(
                n_features=self.dim,
                norm="l2",
                alternate_sign=True,
                ngram_range=(1, 3),
                analyzer="word",
                lowercase=True,
            )
        sparse_vecs = self._vectorizer.transform(texts)
        dense = sparse_vecs.toarray().astype(np.float32)
        # Ensure exact L2 normalization
        norms = np.linalg.norm(dense, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        return (dense / norms).astype(np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query into a 1D (384,) float32 vector."""
        res = self.embed_texts([query])
        return res[0]


# Global singleton instance
_embedder_instance: Optional[LocalEmbedder] = None


def get_embedder() -> LocalEmbedder:
    """Retrieve or create singleton local embedder."""
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = LocalEmbedder()
    return _embedder_instance


def vector_to_blob(vec: np.ndarray) -> bytes:
    """Serialize a numpy float32 vector to bytes."""
    return vec.astype(np.float32).tobytes()


def blob_to_vector(blob: bytes) -> np.ndarray:
    """Deserialize bytes to a numpy float32 vector."""
    return np.frombuffer(blob, dtype=np.float32)
