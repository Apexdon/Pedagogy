"""
Knowledge Service

Business logic for knowledge base management and RAG operations.
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import UploadFile
from datetime import datetime, timezone
from pathlib import Path
import uuid
import aiofiles
import logging

from app.models.knowledge import KnowledgeBase, Document, DocumentChunk
from app.schemas.knowledge import (
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeBaseDetail,
    KnowledgeBaseUpdate,
    DocumentResponse,
    DocumentProcessingResult,
    RAGQueryResponse,
    ChunkResult,
    DeleteKnowledgeBaseResponse,
    ProcessingOptions,
)
from app.config import settings

from rag_system.document_parser import ParserFactory
from rag_system.chunker import InstructionAwareChunker
from rag_system.embedder import Embedder
from rag_system.chroma_store import ChromaStore
from rag_system.retriever import RAGRetriever

logger = logging.getLogger(__name__)


class KnowledgeService:
    """Service for knowledge base and RAG operations."""

    def __init__(self, db: AsyncSession):
        """
        Initialize the knowledge service.

        Args:
            db: Async database session
        """
        self.db = db
        self.embedder = Embedder(settings.EMBEDDING_MODEL)
        self.chroma_store = ChromaStore(settings.CHROMA_PERSIST_DIR)
        self.retriever = RAGRetriever(self.embedder, self.chroma_store)

    # ============================================
    # Knowledge Base CRUD
    # ============================================

    async def create_knowledge_base(
        self,
        org_id: str,
        data: KnowledgeBaseCreate
    ) -> KnowledgeBaseResponse:
        """
        Create a new knowledge base.

        Args:
            org_id: Organisation ID
            data: Knowledge base creation data

        Returns:
            Created knowledge base response
        """
        kb_id = str(uuid.uuid4())

        # Generate ChromaDB collection name
        chroma_collection = self.chroma_store.get_collection_name(org_id, kb_id)

        kb = KnowledgeBase(
            kb_id=kb_id,
            org_id=org_id,
            kb_name=data.kb_name,
            description=data.description,
            chroma_collection=chroma_collection
        )

        self.db.add(kb)
        await self.db.commit()
        await self.db.refresh(kb)

        # Create ChromaDB collection
        self.chroma_store.create_collection(org_id, kb_id)

        logger.info(f"Created knowledge base: {kb_id} for org: {org_id}")

        return KnowledgeBaseResponse(
            kb_id=kb.kb_id,
            org_id=kb.org_id,
            kb_name=kb.kb_name,
            description=kb.description,
            version=kb.version,
            is_active=kb.is_active,
            created_at=kb.created_at,
            updated_at=kb.updated_at,
            document_count=0,
            total_chunks=0
        )

    async def get_knowledge_base(
        self,
        kb_id: str,
        org_id: str
    ) -> Optional[KnowledgeBaseDetail]:
        """
        Get knowledge base with documents.

        Args:
            kb_id: Knowledge base ID
            org_id: Organisation ID (for authorization)

        Returns:
            Knowledge base details or None if not found
        """
        result = await self.db.execute(
            select(KnowledgeBase)
            .options(selectinload(KnowledgeBase.documents))
            .where(
                KnowledgeBase.kb_id == kb_id,
                KnowledgeBase.org_id == org_id
            )
        )
        kb = result.scalar_one_or_none()

        if not kb:
            return None

        # Calculate stats
        doc_count = len(kb.documents)
        total_chunks = sum(doc.total_chunks for doc in kb.documents)

        documents = [
            DocumentResponse(
                doc_id=doc.doc_id,
                doc_name=doc.doc_name,
                doc_type=doc.doc_type,
                file_size_bytes=doc.file_size_bytes,
                total_chunks=doc.total_chunks,
                status=doc.status,
                uploaded_at=doc.uploaded_at,
                processed_at=doc.processed_at
            )
            for doc in kb.documents
        ]

        return KnowledgeBaseDetail(
            kb_id=kb.kb_id,
            org_id=kb.org_id,
            kb_name=kb.kb_name,
            description=kb.description,
            version=kb.version,
            is_active=kb.is_active,
            created_at=kb.created_at,
            updated_at=kb.updated_at,
            document_count=doc_count,
            total_chunks=total_chunks,
            documents=documents
        )

    async def list_knowledge_bases(
        self,
        org_id: str
    ) -> List[KnowledgeBaseResponse]:
        """
        List all knowledge bases for an organisation.

        Args:
            org_id: Organisation ID

        Returns:
            List of knowledge base responses
        """
        result = await self.db.execute(
            select(KnowledgeBase)
            .options(selectinload(KnowledgeBase.documents))
            .where(KnowledgeBase.org_id == org_id)
            .order_by(KnowledgeBase.created_at.desc())
        )
        kbs = result.scalars().all()

        return [
            KnowledgeBaseResponse(
                kb_id=kb.kb_id,
                org_id=kb.org_id,
                kb_name=kb.kb_name,
                description=kb.description,
                version=kb.version,
                is_active=kb.is_active,
                created_at=kb.created_at,
                updated_at=kb.updated_at,
                document_count=len(kb.documents),
                total_chunks=sum(doc.total_chunks for doc in kb.documents)
            )
            for kb in kbs
        ]

    async def update_knowledge_base(
        self,
        kb_id: str,
        org_id: str,
        data: KnowledgeBaseUpdate
    ) -> Optional[KnowledgeBaseResponse]:
        """
        Update a knowledge base.

        Args:
            kb_id: Knowledge base ID
            org_id: Organisation ID
            data: Update data

        Returns:
            Updated knowledge base or None if not found
        """
        result = await self.db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.kb_id == kb_id,
                KnowledgeBase.org_id == org_id
            )
        )
        kb = result.scalar_one_or_none()

        if not kb:
            return None

        if data.kb_name is not None:
            kb.kb_name = data.kb_name
        if data.description is not None:
            kb.description = data.description
        if data.is_active is not None:
            kb.is_active = data.is_active

        await self.db.commit()
        await self.db.refresh(kb)

        return await self.get_knowledge_base(kb_id, org_id)

    async def delete_knowledge_base(
        self,
        kb_id: str,
        org_id: str
    ) -> Optional[DeleteKnowledgeBaseResponse]:
        """
        Delete a knowledge base and all associated data.

        Args:
            kb_id: Knowledge base ID
            org_id: Organisation ID

        Returns:
            Deletion response or None if not found
        """
        # Get KB with documents
        result = await self.db.execute(
            select(KnowledgeBase)
            .options(
                selectinload(KnowledgeBase.documents)
                .selectinload(Document.chunks)
            )
            .where(
                KnowledgeBase.kb_id == kb_id,
                KnowledgeBase.org_id == org_id
            )
        )
        kb = result.scalar_one_or_none()

        if not kb:
            return None

        # Count for response
        doc_count = len(kb.documents)
        chunk_count = sum(len(doc.chunks) for doc in kb.documents)

        # Delete ChromaDB collection
        self.chroma_store.delete_collection(org_id, kb_id)

        # Delete from database (cascade deletes documents and chunks)
        await self.db.delete(kb)
        await self.db.commit()

        logger.info(f"Deleted knowledge base: {kb_id}")

        return DeleteKnowledgeBaseResponse(
            success=True,
            message="Knowledge base deleted successfully",
            kb_id=kb_id,
            documents_deleted=doc_count,
            chunks_deleted=chunk_count
        )

    # ============================================
    # Document Processing
    # ============================================

    async def process_document(
        self,
        kb_id: str,
        org_id: str,
        file: UploadFile,
        options: ProcessingOptions
    ) -> DocumentProcessingResult:
        """
        Process an uploaded document.

        Args:
            kb_id: Knowledge base ID
            org_id: Organisation ID
            file: Uploaded file
            options: Processing options

        Returns:
            Document processing result
        """
        doc_id = str(uuid.uuid4())

        try:
            # Validate file type
            file_ext = Path(file.filename).suffix.lower().lstrip('.')
            if file_ext not in settings.ALLOWED_FILE_TYPES:
                return DocumentProcessingResult(
                    doc_id=doc_id,
                    filename=file.filename,
                    status="failed",
                    chunks_created=0,
                    error_message=f"Unsupported file type: {file_ext}. Allowed: {settings.ALLOWED_FILE_TYPES}"
                )

            # Save file temporarily
            upload_path = Path(settings.UPLOAD_DIR) / org_id / kb_id
            upload_path.mkdir(parents=True, exist_ok=True)
            file_path = upload_path / f"{doc_id}.{file_ext}"

            content = await file.read()

            # Check file size
            if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
                return DocumentProcessingResult(
                    doc_id=doc_id,
                    filename=file.filename,
                    status="failed",
                    chunks_created=0,
                    error_message=f"File too large. Max size: {settings.MAX_FILE_SIZE_MB}MB"
                )

            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(content)

            # Create document record
            doc = Document(
                doc_id=doc_id,
                kb_id=kb_id,
                doc_name=file.filename,
                doc_type=file_ext,
                file_path=str(file_path),
                file_size_bytes=len(content),
                status="processing"
            )
            self.db.add(doc)
            await self.db.commit()

            # Parse document
            parser = ParserFactory.get_parser(str(file_path))
            raw_text = parser.parse(str(file_path))
            doc.content_raw = raw_text

            # Chunk document
            chunker = InstructionAwareChunker(
                chunk_size=options.chunk_size,
                chunk_overlap=options.chunk_overlap,
                min_chunk_size=settings.MIN_CHUNK_SIZE
            )
            chunks = chunker.chunk_text(raw_text, metadata={"doc_id": doc_id})

            if not chunks:
                doc.status = "completed"
                doc.total_chunks = 0
                doc.processed_at = datetime.now(timezone.utc)
                await self.db.commit()

                return DocumentProcessingResult(
                    doc_id=doc_id,
                    filename=file.filename,
                    status="completed",
                    chunks_created=0
                )

            # Generate embeddings
            chunk_texts = [c.content for c in chunks]
            embeddings = self.embedder.embed_batch(chunk_texts)

            # Store in database and ChromaDB
            chunk_ids = []
            chunk_metadatas = []

            for i, chunk in enumerate(chunks):
                chunk_id = str(uuid.uuid4())
                chunk_ids.append(chunk_id)

                # Save to database
                db_chunk = DocumentChunk(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    chunk_index=chunk.chunk_index,
                    chunk_text=chunk.content,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    chunk_metadata=chunk.metadata
                )
                self.db.add(db_chunk)

                # Prepare ChromaDB metadata
                chunk_metadatas.append({
                    "doc_id": doc_id,
                    "doc_name": file.filename,
                    "chunk_index": chunk.chunk_index,
                    **{k: v for k, v in chunk.metadata.items() if isinstance(v, (str, int, float, bool))}
                })

            # Store in ChromaDB
            self.chroma_store.add_chunks(
                org_id=org_id,
                kb_id=kb_id,
                chunk_ids=chunk_ids,
                texts=chunk_texts,
                embeddings=embeddings,
                metadatas=chunk_metadatas
            )

            # Update document status
            doc.status = "completed"
            doc.total_chunks = len(chunks)
            doc.processed_at = datetime.now(timezone.utc)
            await self.db.commit()

            logger.info(f"Processed document {doc_id}: {len(chunks)} chunks created")

            return DocumentProcessingResult(
                doc_id=doc_id,
                filename=file.filename,
                status="completed",
                chunks_created=len(chunks)
            )

        except Exception as e:
            logger.error(f"Error processing document {doc_id}: {e}")

            # Update document with error
            result = await self.db.execute(
                select(Document).where(Document.doc_id == doc_id)
            )
            doc = result.scalar_one_or_none()
            if doc:
                doc.status = "failed"
                doc.error_message = str(e)
                await self.db.commit()

            return DocumentProcessingResult(
                doc_id=doc_id,
                filename=file.filename,
                status="failed",
                chunks_created=0,
                error_message=str(e)
            )

    # ============================================
    # RAG Query
    # ============================================

    async def rag_query(
        self,
        org_id: str,
        query: str,
        kb_id: Optional[str] = None,
        top_k: int = None,
        min_similarity: float = None,
        include_metadata: bool = True
    ) -> RAGQueryResponse:
        """
        Execute RAG query against knowledge base(s).

        Args:
            org_id: Organisation ID
            query: Search query
            kb_id: Specific KB to search (None = all KBs in org)
            top_k: Number of results
            min_similarity: Minimum similarity threshold
            include_metadata: Whether to include metadata in results

        Returns:
            RAG query response
        """
        top_k = top_k or settings.DEFAULT_TOP_K
        min_similarity = min_similarity or settings.DEFAULT_MIN_SIMILARITY

        # Get KB IDs to search
        if kb_id:
            kb_ids = [kb_id]
        else:
            # Get all active KBs for org
            result = await self.db.execute(
                select(KnowledgeBase.kb_id).where(
                    KnowledgeBase.org_id == org_id,
                    KnowledgeBase.is_active == True
                )
            )
            kb_ids = [row[0] for row in result.fetchall()]

        if not kb_ids:
            return RAGQueryResponse(
                success=True,
                query_id=str(uuid.uuid4()),
                query=query,
                results=[],
                total_results=0,
                search_time_ms=0
            )

        # Execute retrieval
        retrieval_result = await self.retriever.retrieve(
            query=query,
            org_id=org_id,
            kb_ids=kb_ids,
            top_k=top_k,
            min_similarity=min_similarity
        )

        # Convert to response format
        results = []
        for r in retrieval_result.results:
            chunk_result = ChunkResult(
                chunk_id=r.chunk_id,
                doc_id=r.doc_id,
                doc_name=r.metadata.get("doc_name", ""),
                chunk_text=r.text,
                similarity=r.similarity,
                metadata=r.metadata if include_metadata else {}
            )
            results.append(chunk_result)

        return RAGQueryResponse(
            success=True,
            query_id=retrieval_result.query_id,
            query=query,
            results=results,
            total_results=len(results),
            search_time_ms=retrieval_result.search_time_ms
        )
