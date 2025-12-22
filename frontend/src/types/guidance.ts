// Guidance types for RAG-based Q&A

export interface RAGQueryRequest {
  query: string;
  kb_id?: string;
  top_k?: number;
  min_similarity?: number;
  include_metadata?: boolean;
}

export interface ChunkResult {
  chunk_id: string;
  doc_id: string;
  doc_name: string;
  chunk_text: string;
  similarity: number;
  metadata: Record<string, unknown>;
}

export interface RAGQueryResponse {
  success: boolean;
  query_id: string;
  query: string;
  results: ChunkResult[];
  total_results: number;
  search_time_ms: number;
}

// Local chat message type (for frontend state only)
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: ChunkResult[];
  timestamp: Date;
  isLoading?: boolean;
}
