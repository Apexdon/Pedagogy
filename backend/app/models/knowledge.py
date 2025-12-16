"""
Knowledge Base, Document, and DocumentChunk Models

Models for the RAG knowledge management system.
Embeddings are stored in ChromaDB, not in this database.
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Integer, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.core.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class KnowledgeBase(Base):
    """Knowledge Base model - a collection of documents for an organisation.

    Each knowledge base has its own ChromaDB collection for vector storage.
    The collection is named using the org_id and kb_id for isolation.
    """

    __tablename__ = "knowledge_bases"

    kb_id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(
        String(36),
        ForeignKey("organisations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    kb_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(String(50), default="1.0.0")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # ChromaDB collection name (org-isolated, unique)
    chroma_collection = Column(String(255), nullable=False, unique=True)

    # Relationships
    organisation = relationship("Organisation", backref="knowledge_bases")
    documents = relationship(
        "Document",
        back_populates="knowledge_base",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<KnowledgeBase(kb_id={self.kb_id}, name={self.kb_name})>"


class Document(Base):
    """Document model - uploaded document metadata.

    Stores information about uploaded files. The actual text content
    is parsed and chunked, with chunks stored both here (metadata)
    and in ChromaDB (embeddings).
    """

    __tablename__ = "documents"

    doc_id = Column(String(36), primary_key=True, default=generate_uuid)
    kb_id = Column(
        String(36),
        ForeignKey("knowledge_bases.kb_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    doc_name = Column(String(255), nullable=False)
    doc_type = Column(String(50), nullable=False)  # pdf, docx, md
    file_path = Column(String(500), nullable=True)  # Storage path
    content_raw = Column(Text, nullable=True)  # Extracted raw text
    file_size_bytes = Column(Integer, nullable=True)
    total_chunks = Column(Integer, default=0)
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime, nullable=True)
    doc_metadata = Column(JSON, default=dict)  # Document metadata (author, title, etc.)

    # Relationships
    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Document(doc_id={self.doc_id}, name={self.doc_name}, status={self.status})>"


class DocumentChunk(Base):
    """Document Chunk model - metadata for chunked text.

    The actual embeddings are stored in ChromaDB, not here.
    This table stores chunk metadata for reference and traceability.
    The chunk_id is used as the ID in ChromaDB for linking.
    """

    __tablename__ = "document_chunks"

    chunk_id = Column(String(36), primary_key=True, default=generate_uuid)
    doc_id = Column(
        String(36),
        ForeignKey("documents.doc_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    start_char = Column(Integer, nullable=False)
    end_char = Column(Integer, nullable=False)
    chunk_metadata = Column(JSON, default=dict)  # Extra metadata (is_instruction_step, step_number, etc.)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    document = relationship("Document", back_populates="chunks")

    def __repr__(self):
        return f"<DocumentChunk(chunk_id={self.chunk_id}, doc_id={self.doc_id}, index={self.chunk_index})>"
