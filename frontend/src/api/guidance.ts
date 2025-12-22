import apiClient from './client';
import type { RAGQueryRequest, RAGQueryResponse } from '@/types';

/**
 * Query the RAG system for guidance
 * Uses the existing /org/query/rag endpoint
 */
export const queryRAG = async (request: RAGQueryRequest): Promise<RAGQueryResponse> => {
  const response = await apiClient.post<RAGQueryResponse>('/org/query/rag', request);
  return response.data;
};
