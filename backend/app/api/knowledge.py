"""
Knowledge Base API Routes

Endpoints for knowledge base management and RAG queries.
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import time

from app.core.database import get_db
from app.core.dependencies import get_current_org_membership, require_role
from app.models.user import UserOrganisation
from app.schemas.knowledge import (
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeBaseDetail,
    KnowledgeBaseUpdate,
    KnowledgeBaseListResponse,
    UploadKnowledgeResponse,
    RAGQueryRequest,
    RAGQueryResponse,
    DeleteKnowledgeBaseResponse,
    ProcessingOptions,
)
from app.services.knowledge_service import KnowledgeService

router = APIRouter()


# ============================================
# Knowledge Base CRUD
# ============================================

@router.get("/knowledge-bases", response_model=KnowledgeBaseListResponse)
async def list_knowledge_bases(
    membership: UserOrganisation = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db)
):
    """
    List all knowledge bases for the current organisation.

    Returns a list of all knowledge bases with document counts.
    """
    service = KnowledgeService(db)
    knowledge_bases = await service.list_knowledge_bases(membership.org_id)

    return KnowledgeBaseListResponse(
        knowledge_bases=knowledge_bases,
        total_count=len(knowledge_bases)
    )


@router.get("/knowledge-bases/{kb_id}", response_model=KnowledgeBaseDetail)
async def get_knowledge_base(
    kb_id: str,
    membership: UserOrganisation = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db)
):
    """
    Get details of a specific knowledge base including its documents.

    - **kb_id**: Knowledge base ID
    """
    service = KnowledgeService(db)
    kb = await service.get_knowledge_base(kb_id, membership.org_id)

    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found"
        )

    return kb


@router.post("/knowledge-bases", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    kb_data: KnowledgeBaseCreate,
    membership: UserOrganisation = Depends(require_role(["org_admin", "manager"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new empty knowledge base.

    Requires org_admin or manager role.

    - **kb_name**: Name of the knowledge base
    - **description**: Optional description
    """
    service = KnowledgeService(db)
    kb = await service.create_knowledge_base(membership.org_id, kb_data)
    return kb


@router.patch("/knowledge-bases/{kb_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge_base(
    kb_id: str,
    kb_update: KnowledgeBaseUpdate,
    membership: UserOrganisation = Depends(require_role(["org_admin", "manager"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a knowledge base.

    Requires org_admin or manager role.

    - **kb_id**: Knowledge base ID
    - **kb_name**: New name (optional)
    - **description**: New description (optional)
    - **is_active**: Activate/deactivate (optional)
    """
    service = KnowledgeService(db)
    kb = await service.update_knowledge_base(kb_id, membership.org_id, kb_update)

    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found"
        )

    return kb


@router.delete("/knowledge-bases/{kb_id}", response_model=DeleteKnowledgeBaseResponse)
async def delete_knowledge_base(
    kb_id: str,
    membership: UserOrganisation = Depends(require_role(["org_admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a knowledge base and all its documents.

    Requires org_admin role. This action is irreversible.

    - **kb_id**: Knowledge base ID to delete
    """
    service = KnowledgeService(db)
    result = await service.delete_knowledge_base(kb_id, membership.org_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found"
        )

    return result


# ============================================
# Document Upload
# ============================================

@router.post("/upload-knowledge", response_model=UploadKnowledgeResponse)
async def upload_knowledge(
    kb_id: Optional[str] = Form(None, description="Existing KB ID, or None to create new"),
    kb_name: Optional[str] = Form(None, description="Name for new KB (required if kb_id is None)"),
    kb_description: Optional[str] = Form(None, description="Description for new KB"),
    files: List[UploadFile] = File(..., description="Documents to upload (PDF, DOCX, MD)"),
    chunk_size: int = Form(500, ge=100, le=2000, description="Chunk size in characters"),
    chunk_overlap: int = Form(50, ge=0, le=200, description="Overlap between chunks"),
    membership: UserOrganisation = Depends(require_role(["org_admin", "manager"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload documents to a knowledge base.

    If kb_id is not provided, creates a new knowledge base first.
    Supports PDF, DOCX, and Markdown files.

    Requires org_admin or manager role.

    - **kb_id**: Optional existing knowledge base ID
    - **kb_name**: Required if creating new KB
    - **kb_description**: Optional description for new KB
    - **files**: One or more files to upload
    - **chunk_size**: Target chunk size (100-2000 characters)
    - **chunk_overlap**: Overlap between chunks (0-200 characters)
    """
    start_time = time.time()

    service = KnowledgeService(db)

    # Create or get knowledge base
    if kb_id:
        kb = await service.get_knowledge_base(kb_id, membership.org_id)
        if not kb:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge base not found"
            )
    else:
        if not kb_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="kb_name is required when creating a new knowledge base"
            )
        kb = await service.create_knowledge_base(
            membership.org_id,
            KnowledgeBaseCreate(kb_name=kb_name, description=kb_description)
        )
        kb_id = kb.kb_id

    # Process each file
    processing_options = ProcessingOptions(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )

    results = []
    total_chunks = 0

    for file in files:
        result = await service.process_document(
            kb_id=kb_id,
            org_id=membership.org_id,
            file=file,
            options=processing_options
        )
        results.append(result)
        total_chunks += result.chunks_created

    processing_time = time.time() - start_time

    # Refresh KB stats
    kb = await service.get_knowledge_base(kb_id, membership.org_id)

    return UploadKnowledgeResponse(
        success=True,
        knowledge_base=kb,
        documents_processed=results,
        total_chunks=total_chunks,
        processing_time_sec=round(processing_time, 2)
    )


# ============================================
# RAG Query
# ============================================

@router.post("/query/rag", response_model=RAGQueryResponse)
async def query_rag(
    request: RAGQueryRequest,
    membership: UserOrganisation = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db)
):
    """
    Query knowledge base using semantic search (RAG).

    If kb_id is not specified, searches all active knowledge bases in the organisation.

    - **query**: Search query text
    - **kb_id**: Optional specific knowledge base to search
    - **top_k**: Number of results to return (1-20)
    - **min_similarity**: Minimum similarity threshold (0.0-1.0)
    - **include_metadata**: Whether to include chunk metadata
    """
    service = KnowledgeService(db)

    result = await service.rag_query(
        org_id=membership.org_id,
        query=request.query,
        kb_id=request.kb_id,
        top_k=request.top_k,
        min_similarity=request.min_similarity,
        include_metadata=request.include_metadata
    )

    return result
