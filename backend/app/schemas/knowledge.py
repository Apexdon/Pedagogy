"""
Knowledge Base Schemas

Pydantic models for knowledge base requests and responses.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============================================
# Knowledge Base Schemas
# ============================================

class KnowledgeBaseCreate(BaseModel):
    """Schema for creating a knowledge base."""

    kb_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class KnowledgeBaseUpdate(BaseModel):
    """Schema for updating a knowledge base."""

    kb_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class KnowledgeBaseResponse(BaseModel):
    """Schema for knowledge base response."""

    kb_id: str
    org_id: str
    kb_name: str
    description: Optional[str] = None
    version: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    document_count: int = 0
    total_chunks: int = 0

    class Config:
        from_attributes = True


class KnowledgeBaseListResponse(BaseModel):
    """Schema for list of knowledge bases."""

    knowledge_bases: List[KnowledgeBaseResponse]
    total_count: int


# ============================================
# Document Schemas
# ============================================

class DocumentResponse(BaseModel):
    """Schema for document response."""

    doc_id: str
    doc_name: str
    doc_type: str
    file_size_bytes: Optional[int] = None
    total_chunks: int
    status: str
    uploaded_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentProcessingResult(BaseModel):
    """Schema for document processing result."""

    doc_id: str
    filename: str
    status: str
    chunks_created: int
    error_message: Optional[str] = None


class KnowledgeBaseDetail(KnowledgeBaseResponse):
    """Schema for detailed knowledge base response with documents."""

    documents: List[DocumentResponse] = []


class DeleteKnowledgeBaseResponse(BaseModel):
    """Schema for delete KB response."""

    success: bool = True
    message: str
    kb_id: str
    documents_deleted: int
    chunks_deleted: int


# ============================================
# Document Upload Schemas
# ============================================

class ProcessingOptions(BaseModel):
    """Schema for document processing options."""

    chunk_size: int = Field(500, ge=100, le=2000)
    chunk_overlap: int = Field(50, ge=0, le=200)
    extract_instructions: bool = True


class UploadKnowledgeResponse(BaseModel):
    """Schema for knowledge upload response."""

    success: bool = True
    knowledge_base: KnowledgeBaseResponse
    documents_processed: List[DocumentProcessingResult]
    total_chunks: int
    processing_time_sec: float


# ============================================
# RAG Query Schemas
# ============================================

class RAGQueryRequest(BaseModel):
    """Schema for RAG query request."""

    query: str = Field(..., min_length=1, max_length=1000)
    kb_id: Optional[str] = None  # If None, search all KBs in org
    top_k: int = Field(5, ge=1, le=20)
    min_similarity: float = Field(0.7, ge=0.0, le=1.0)
    include_metadata: bool = True


class ChunkResult(BaseModel):
    """Schema for a single chunk result."""

    chunk_id: str
    doc_id: str
    doc_name: str
    chunk_text: str
    similarity: float
    metadata: Dict[str, Any] = {}


class RAGQueryResponse(BaseModel):
    """Schema for RAG query response."""

    success: bool = True
    query_id: str
    query: str
    results: List[ChunkResult]
    total_results: int
    search_time_ms: float
