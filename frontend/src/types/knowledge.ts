// Knowledge Base types

export interface KnowledgeBase {
  kb_id: string;
  org_id: string;
  kb_name: string;
  description?: string;
  version: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  document_count: number;
  total_chunks: number;
}

export interface Document {
  doc_id: string;
  doc_name: string;
  doc_type: string;
  file_size_bytes?: number;
  total_chunks: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  uploaded_at: string;
  processed_at?: string;
}

export interface KnowledgeBaseDetail extends KnowledgeBase {
  documents: Document[];
}

export interface DocumentProcessingResult {
  doc_id: string;
  filename: string;
  status: string;
  chunks_created: number;
  error_message?: string;
}

// Request types
export interface CreateKnowledgeBaseRequest {
  kb_name: string;
  description?: string;
}

export interface UpdateKnowledgeBaseRequest {
  kb_name?: string;
  description?: string;
  is_active?: boolean;
}

export interface ProcessingOptions {
  chunk_size?: number;
  chunk_overlap?: number;
  extract_instructions?: boolean;
}

// Response types
export interface KnowledgeBaseListResponse {
  knowledge_bases: KnowledgeBase[];
  total_count: number;
}

export interface UploadKnowledgeResponse {
  success: boolean;
  knowledge_base: KnowledgeBase;
  documents_processed: DocumentProcessingResult[];
  total_chunks: number;
  processing_time_sec: number;
}

export interface DeleteKnowledgeBaseResponse {
  success: boolean;
  message: string;
  kb_id: string;
  documents_deleted: number;
  chunks_deleted: number;
}
