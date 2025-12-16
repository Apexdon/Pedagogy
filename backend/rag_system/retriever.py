"""
RAG Retriever Module

Combines embedding generation and ChromaDB search for semantic retrieval.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import time
import uuid
import logging

from rag_system.embedder import Embedder
from rag_system.chroma_store import ChromaStore

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Represents a single retrieval result."""

    chunk_id: str
    kb_id: str
    doc_id: str
    text: str
    similarity: float
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class RetrievalResponse:
    """Full retrieval response with metadata."""

    query_id: str
    query: str
    results: List[RetrievalResult]
    total_results: int
    search_time_ms: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "query_id": self.query_id,
            "query": self.query,
            "results": [r.to_dict() for r in self.results],
            "total_results": self.total_results,
            "search_time_ms": self.search_time_ms
        }


class RAGRetriever:
    """
    Retrieval-Augmented Generation retriever.

    Combines embedding generation and vector search for semantic retrieval.
    """

    def __init__(
        self,
        embedder: Optional[Embedder] = None,
        chroma_store: Optional[ChromaStore] = None
    ):
        """
        Initialize the RAG retriever.

        Args:
            embedder: Embedder instance (creates default if None)
            chroma_store: ChromaStore instance (creates default if None)
        """
        self.embedder = embedder or Embedder()
        self.chroma_store = chroma_store or ChromaStore()

    async def retrieve(
        self,
        query: str,
        org_id: str,
        kb_ids: Optional[List[str]] = None,
        top_k: int = 5,
        min_similarity: float = 0.7
    ) -> RetrievalResponse:
        """
        Retrieve relevant chunks for a query.

        Args:
            query: Search query text
            org_id: Organisation ID
            kb_ids: List of KB IDs to search (required)
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold (0.0 to 1.0)

        Returns:
            RetrievalResponse with results and timing info
        """
        start_time = time.time()
        query_id = str(uuid.uuid4())

        if not kb_ids:
            return RetrievalResponse(
                query_id=query_id,
                query=query,
                results=[],
                total_results=0,
                search_time_ms=0
            )

        # Generate query embedding
        query_embedding = self.embedder.embed_text(query)

        # Search ChromaDB
        if len(kb_ids) == 1:
            # Single KB search
            raw_results = self.chroma_store.query(
                org_id=org_id,
                kb_id=kb_ids[0],
                query_embedding=query_embedding,
                top_k=top_k
            )
            results = self._process_single_kb_results(
                kb_ids[0], raw_results, min_similarity
            )
        else:
            # Multi-KB search
            raw_results = self.chroma_store.query_multiple_collections(
                org_id=org_id,
                kb_ids=kb_ids,
                query_embedding=query_embedding,
                top_k=top_k
            )
            results = self._process_multi_kb_results(raw_results, min_similarity)

        search_time_ms = (time.time() - start_time) * 1000

        logger.debug(f"RAG query returned {len(results)} results in {search_time_ms:.2f}ms")

        return RetrievalResponse(
            query_id=query_id,
            query=query,
            results=results,
            total_results=len(results),
            search_time_ms=round(search_time_ms, 2)
        )

    def retrieve_sync(
        self,
        query: str,
        org_id: str,
        kb_ids: Optional[List[str]] = None,
        top_k: int = 5,
        min_similarity: float = 0.7
    ) -> RetrievalResponse:
        """
        Synchronous version of retrieve for non-async contexts.

        Same parameters as retrieve().
        """
        start_time = time.time()
        query_id = str(uuid.uuid4())

        if not kb_ids:
            return RetrievalResponse(
                query_id=query_id,
                query=query,
                results=[],
                total_results=0,
                search_time_ms=0
            )

        # Generate query embedding
        query_embedding = self.embedder.embed_text(query)

        # Search ChromaDB
        if len(kb_ids) == 1:
            raw_results = self.chroma_store.query(
                org_id=org_id,
                kb_id=kb_ids[0],
                query_embedding=query_embedding,
                top_k=top_k
            )
            results = self._process_single_kb_results(
                kb_ids[0], raw_results, min_similarity
            )
        else:
            raw_results = self.chroma_store.query_multiple_collections(
                org_id=org_id,
                kb_ids=kb_ids,
                query_embedding=query_embedding,
                top_k=top_k
            )
            results = self._process_multi_kb_results(raw_results, min_similarity)

        search_time_ms = (time.time() - start_time) * 1000

        return RetrievalResponse(
            query_id=query_id,
            query=query,
            results=results,
            total_results=len(results),
            search_time_ms=round(search_time_ms, 2)
        )

    def _process_single_kb_results(
        self,
        kb_id: str,
        raw_results: Dict[str, Any],
        min_similarity: float
    ) -> List[RetrievalResult]:
        """Process results from single KB query."""
        results = []

        if not raw_results.get("ids") or not raw_results["ids"][0]:
            return results

        for i, chunk_id in enumerate(raw_results["ids"][0]):
            # Convert distance to similarity
            distance = raw_results["distances"][0][i] if raw_results.get("distances") else 0
            # Assuming L2 distance on normalized vectors: sim = 1 - (dist/2)
            similarity = max(0, 1 - (distance / 2))

            if similarity >= min_similarity:
                metadata = raw_results["metadatas"][0][i] if raw_results.get("metadatas") else {}
                text = raw_results["documents"][0][i] if raw_results.get("documents") else ""

                results.append(RetrievalResult(
                    chunk_id=chunk_id,
                    kb_id=kb_id,
                    doc_id=metadata.get("doc_id", ""),
                    text=text,
                    similarity=round(similarity, 4),
                    metadata=metadata
                ))

        return results

    def _process_multi_kb_results(
        self,
        raw_results: List[tuple],
        min_similarity: float
    ) -> List[RetrievalResult]:
        """Process results from multi-KB query."""
        results = []

        for kb_id, chunk_id, text, similarity, metadata in raw_results:
            if similarity >= min_similarity:
                results.append(RetrievalResult(
                    chunk_id=chunk_id,
                    kb_id=kb_id,
                    doc_id=metadata.get("doc_id", ""),
                    text=text,
                    similarity=round(similarity, 4),
                    metadata=metadata
                ))

        return results


async def retrieve(
    query: str,
    org_id: str,
    kb_ids: List[str],
    top_k: int = 5,
    min_similarity: float = 0.7
) -> RetrievalResponse:
    """
    Convenience function to perform RAG retrieval.

    Args:
        query: Search query text
        org_id: Organisation ID
        kb_ids: List of Knowledge Base IDs to search
        top_k: Number of results to return
        min_similarity: Minimum similarity threshold

    Returns:
        RetrievalResponse with results
    """
    retriever = RAGRetriever()
    return await retriever.retrieve(
        query=query,
        org_id=org_id,
        kb_ids=kb_ids,
        top_k=top_k,
        min_similarity=min_similarity
    )
