"""
ChromaDB Vector Store Module

Handles all ChromaDB operations for storing and querying embeddings.
Implements organisation-isolated collections.
"""

from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Lazy import and client caching
_chroma_client = None


def _get_client(persist_directory: str):
    """Get or create the ChromaDB client (singleton pattern)."""
    global _chroma_client

    if _chroma_client is None:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        Path(persist_directory).mkdir(parents=True, exist_ok=True)

        _chroma_client = chromadb.PersistentClient(
            path=persist_directory,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        logger.info(f"ChromaDB client initialized at {persist_directory}")

    return _chroma_client


class ChromaStore:
    """
    ChromaDB vector store for RAG embeddings.

    Each organisation's knowledge base gets its own collection for isolation.
    Collection naming format: org_{org_id_short}_kb_{kb_id_short}
    """

    DEFAULT_PERSIST_DIR = "./chroma_data"

    def __init__(self, persist_directory: str = None):
        """
        Initialize ChromaDB store.

        Args:
            persist_directory: Directory for ChromaDB persistence.
                             Defaults to './chroma_data'
        """
        self.persist_directory = persist_directory or self.DEFAULT_PERSIST_DIR

    @property
    def client(self):
        """Get the ChromaDB client (lazy initialization)."""
        return _get_client(self.persist_directory)

    def get_collection_name(self, org_id: str, kb_id: str) -> str:
        """
        Generate collection name for organisation isolation.

        Format: org_{org_id_short}_kb_{kb_id_short}
        ChromaDB collection names must be 3-63 chars, start/end with alphanumeric.

        Args:
            org_id: Organisation UUID
            kb_id: Knowledge Base UUID

        Returns:
            Valid ChromaDB collection name
        """
        # Use shortened UUIDs (remove hyphens and take first 12 chars)
        org_short = org_id.replace('-', '')[:12]
        kb_short = kb_id.replace('-', '')[:12]
        return f"org_{org_short}_kb_{kb_short}"

    def create_collection(
        self,
        org_id: str,
        kb_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Create or get a collection for a knowledge base.

        Args:
            org_id: Organisation ID
            kb_id: Knowledge Base ID
            metadata: Optional collection metadata

        Returns:
            ChromaDB Collection object
        """
        collection_name = self.get_collection_name(org_id, kb_id)

        collection_metadata = metadata.copy() if metadata else {}
        collection_metadata.update({
            "org_id": org_id,
            "kb_id": kb_id,
        })

        collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata=collection_metadata
        )

        logger.debug(f"Got/created collection: {collection_name}")
        return collection

    def get_collection(self, org_id: str, kb_id: str):
        """
        Get an existing collection.

        Args:
            org_id: Organisation ID
            kb_id: Knowledge Base ID

        Returns:
            ChromaDB Collection or None if not found
        """
        collection_name = self.get_collection_name(org_id, kb_id)
        try:
            return self.client.get_collection(name=collection_name)
        except Exception:
            logger.debug(f"Collection not found: {collection_name}")
            return None

    def add_chunks(
        self,
        org_id: str,
        kb_id: str,
        chunk_ids: List[str],
        texts: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> int:
        """
        Add document chunks to ChromaDB.

        Args:
            org_id: Organisation ID
            kb_id: Knowledge Base ID
            chunk_ids: List of unique chunk IDs (same as in SQL database)
            texts: List of chunk texts
            embeddings: List of embedding vectors
            metadatas: Optional list of metadata dicts

        Returns:
            Number of chunks added
        """
        if not chunk_ids:
            return 0

        collection = self.create_collection(org_id, kb_id)

        # Prepare metadata - ensure all values are valid types
        if metadatas is None:
            metadatas = [{}] * len(chunk_ids)
        else:
            # ChromaDB only accepts str, int, float, bool for metadata values
            clean_metadatas = []
            for meta in metadatas:
                clean_meta = {}
                for k, v in meta.items():
                    if isinstance(v, (str, int, float, bool)):
                        clean_meta[k] = v
                    elif v is None:
                        clean_meta[k] = ""
                    else:
                        clean_meta[k] = str(v)
                clean_metadatas.append(clean_meta)
            metadatas = clean_metadatas

        # Add to collection
        collection.add(
            ids=chunk_ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )

        logger.info(f"Added {len(chunk_ids)} chunks to collection {collection.name}")
        return len(chunk_ids)

    def query(
        self,
        org_id: str,
        kb_id: str,
        query_embedding: List[float],
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
        include: List[str] = None
    ) -> Dict[str, Any]:
        """
        Query ChromaDB for similar chunks.

        Args:
            org_id: Organisation ID
            kb_id: Knowledge Base ID
            query_embedding: Query embedding vector
            top_k: Number of results to return
            where: Optional filter conditions
            include: Fields to include in results

        Returns:
            Query results dict with ids, documents, metadatas, distances
        """
        if include is None:
            include = ["documents", "metadatas", "distances"]

        collection = self.get_collection(org_id, kb_id)

        if collection is None:
            return {
                "ids": [[]],
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]]
            }

        # Don't query more than what exists
        actual_top_k = min(top_k, collection.count())
        if actual_top_k == 0:
            return {
                "ids": [[]],
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]]
            }

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=actual_top_k,
            where=where,
            include=include
        )

        return results

    def query_multiple_collections(
        self,
        org_id: str,
        kb_ids: List[str],
        query_embedding: List[float],
        top_k: int = 5
    ) -> List[Tuple[str, str, str, float, Dict]]:
        """
        Query multiple knowledge bases and merge results.

        Args:
            org_id: Organisation ID
            kb_ids: List of Knowledge Base IDs to search
            query_embedding: Query embedding vector
            top_k: Total number of results to return

        Returns:
            List of tuples: (kb_id, chunk_id, text, similarity, metadata)
            Sorted by similarity (highest first)
        """
        all_results = []

        for kb_id in kb_ids:
            results = self.query(
                org_id=org_id,
                kb_id=kb_id,
                query_embedding=query_embedding,
                top_k=top_k  # Get top_k from each, then merge
            )

            if results["ids"] and results["ids"][0]:
                for i, chunk_id in enumerate(results["ids"][0]):
                    # ChromaDB returns L2 distances, convert to similarity
                    # For normalized embeddings: similarity = 1 - (distance / 2)
                    # For cosine distance: similarity = 1 - distance
                    distance = results["distances"][0][i] if results.get("distances") else 0
                    # Assuming cosine distance (0-2 range for normalized vectors)
                    similarity = max(0, 1 - (distance / 2))

                    all_results.append((
                        kb_id,
                        chunk_id,
                        results["documents"][0][i] if results.get("documents") else "",
                        similarity,
                        results["metadatas"][0][i] if results.get("metadatas") else {}
                    ))

        # Sort by similarity (descending) and take top_k
        all_results.sort(key=lambda x: x[3], reverse=True)
        return all_results[:top_k]

    def delete_collection(self, org_id: str, kb_id: str) -> bool:
        """
        Delete a collection (when KB is deleted).

        Args:
            org_id: Organisation ID
            kb_id: Knowledge Base ID

        Returns:
            True if deleted, False if not found
        """
        collection_name = self.get_collection_name(org_id, kb_id)
        try:
            self.client.delete_collection(name=collection_name)
            logger.info(f"Deleted collection: {collection_name}")
            return True
        except Exception as e:
            logger.warning(f"Failed to delete collection {collection_name}: {e}")
            return False

    def delete_chunks(
        self,
        org_id: str,
        kb_id: str,
        chunk_ids: List[str]
    ) -> int:
        """
        Delete specific chunks from a collection.

        Args:
            org_id: Organisation ID
            kb_id: Knowledge Base ID
            chunk_ids: List of chunk IDs to delete

        Returns:
            Number of chunks deleted
        """
        collection = self.get_collection(org_id, kb_id)
        if collection is None:
            return 0

        collection.delete(ids=chunk_ids)
        logger.debug(f"Deleted {len(chunk_ids)} chunks from collection")
        return len(chunk_ids)

    def get_collection_stats(self, org_id: str, kb_id: str) -> Dict[str, Any]:
        """
        Get statistics for a collection.

        Args:
            org_id: Organisation ID
            kb_id: Knowledge Base ID

        Returns:
            Dictionary with collection stats
        """
        collection = self.get_collection(org_id, kb_id)
        if collection is None:
            return {
                "exists": False,
                "count": 0
            }

        return {
            "exists": True,
            "name": collection.name,
            "count": collection.count(),
            "metadata": collection.metadata
        }

    def list_collections(self) -> List[Dict[str, Any]]:
        """
        List all collections in the ChromaDB instance.

        Returns:
            List of collection info dictionaries
        """
        collections = self.client.list_collections()
        return [
            {
                "name": col.name,
                "count": col.count(),
                "metadata": col.metadata
            }
            for col in collections
        ]


def reset_client():
    """Reset the global ChromaDB client (useful for testing)."""
    global _chroma_client
    _chroma_client = None
