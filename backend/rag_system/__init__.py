"""
RAG System Package

Knowledge base and Retrieval-Augmented Generation system for Pedagogy.
Uses ChromaDB for vector storage and SentenceTransformers for embeddings.
"""

from rag_system.document_parser import ParserFactory, DocumentParser
from rag_system.chunker import TextChunker, InstructionAwareChunker, Chunk
from rag_system.embedder import Embedder
from rag_system.chroma_store import ChromaStore
from rag_system.retriever import RAGRetriever, RetrievalResult
from rag_system.instruction_extractor import InstructionExtractor, InstructionStep

__all__ = [
    # Document Parsing
    "ParserFactory",
    "DocumentParser",
    # Chunking
    "TextChunker",
    "InstructionAwareChunker",
    "Chunk",
    # Embedding
    "Embedder",
    # Vector Store
    "ChromaStore",
    # Retrieval
    "RAGRetriever",
    "RetrievalResult",
    # Instruction Extraction
    "InstructionExtractor",
    "InstructionStep",
]
