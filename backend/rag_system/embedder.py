"""
Embedding Generator Module

Generates text embeddings using SentenceTransformers.
Supports batching for efficiency and caches the model for reuse.
"""

from typing import List, Optional, Union
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Lazy import to avoid loading the model at module import time
_model_cache = {}


def _get_model(model_name: str):
    """Get or create a cached SentenceTransformer model."""
    if model_name not in _model_cache:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading embedding model: {model_name}")
        _model_cache[model_name] = SentenceTransformer(model_name)
    return _model_cache[model_name]


class Embedder:
    """
    Generates embeddings using SentenceTransformers.

    Default model: all-MiniLM-L6-v2 (384 dimensions, fast, good quality)

    The model is cached globally to avoid reloading on each instantiation.
    """

    DEFAULT_MODEL = "all-MiniLM-L6-v2"

    def __init__(self, model_name: str = None):
        """
        Initialize the embedder.

        Args:
            model_name: Name of the SentenceTransformer model to use.
                       Defaults to 'all-MiniLM-L6-v2'
        """
        self.model_name = model_name or self.DEFAULT_MODEL
        self._dimension: Optional[int] = None

    @property
    def model(self):
        """Get the underlying SentenceTransformer model (lazy loaded)."""
        return _get_model(self.model_name)

    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        if self._dimension is None:
            self._dimension = self.model.get_sentence_embedding_dimension()
        return self._dimension

    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        if not text or not text.strip():
            # Return zero vector for empty text
            return [0.0] * self.dimension

        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = False
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per batch (for memory management)
            show_progress: Show progress bar during embedding

        Returns:
            List of embeddings (each embedding is a list of floats)
        """
        if not texts:
            return []

        # Filter out empty texts but track indices
        non_empty_indices = []
        non_empty_texts = []
        for i, text in enumerate(texts):
            if text and text.strip():
                non_empty_indices.append(i)
                non_empty_texts.append(text)

        if not non_empty_texts:
            # All texts were empty
            return [[0.0] * self.dimension for _ in texts]

        # Generate embeddings for non-empty texts
        embeddings = self.model.encode(
            non_empty_texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True
        )

        # Build result with zero vectors for empty texts
        result = [[0.0] * self.dimension for _ in texts]
        for i, embedding in zip(non_empty_indices, embeddings):
            result[i] = embedding.tolist()

        logger.debug(f"Generated {len(non_empty_texts)} embeddings from {len(texts)} texts")
        return result

    def similarity(
        self,
        embedding1: Union[List[float], np.ndarray],
        embedding2: Union[List[float], np.ndarray]
    ) -> float:
        """
        Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Similarity score between -1 and 1 (typically 0 to 1 for normalized embeddings)
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        # Handle zero vectors
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(np.dot(vec1, vec2) / (norm1 * norm2))

    def similarity_batch(
        self,
        query_embedding: Union[List[float], np.ndarray],
        embeddings: List[Union[List[float], np.ndarray]]
    ) -> List[float]:
        """
        Calculate cosine similarity between a query and multiple embeddings.

        Args:
            query_embedding: Query embedding vector
            embeddings: List of embedding vectors to compare against

        Returns:
            List of similarity scores
        """
        query_vec = np.array(query_embedding)
        query_norm = np.linalg.norm(query_vec)

        if query_norm == 0:
            return [0.0] * len(embeddings)

        similarities = []
        for emb in embeddings:
            emb_vec = np.array(emb)
            emb_norm = np.linalg.norm(emb_vec)

            if emb_norm == 0:
                similarities.append(0.0)
            else:
                sim = np.dot(query_vec, emb_vec) / (query_norm * emb_norm)
                similarities.append(float(sim))

        return similarities


def embed_text(text: str, model_name: str = None) -> List[float]:
    """
    Convenience function to embed a single text.

    Args:
        text: Text to embed
        model_name: Optional model name (defaults to all-MiniLM-L6-v2)

    Returns:
        Embedding vector as list of floats
    """
    embedder = Embedder(model_name)
    return embedder.embed_text(text)


def embed_texts(texts: List[str], model_name: str = None) -> List[List[float]]:
    """
    Convenience function to embed multiple texts.

    Args:
        texts: List of texts to embed
        model_name: Optional model name (defaults to all-MiniLM-L6-v2)

    Returns:
        List of embedding vectors
    """
    embedder = Embedder(model_name)
    return embedder.embed_batch(texts)
