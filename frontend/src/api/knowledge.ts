import apiClient from './client';
import type {
  KnowledgeBase,
  KnowledgeBaseDetail,
  KnowledgeBaseListResponse,
  CreateKnowledgeBaseRequest,
  UpdateKnowledgeBaseRequest,
  UploadKnowledgeResponse,
  DeleteKnowledgeBaseResponse,
} from '@/types';

/**
 * List all knowledge bases for the organisation
 */
export const listKnowledgeBases = async (): Promise<KnowledgeBaseListResponse> => {
  const response = await apiClient.get<KnowledgeBaseListResponse>('/org/knowledge-bases');
  return response.data;
};

/**
 * Get a specific knowledge base with its documents
 */
export const getKnowledgeBase = async (kbId: string): Promise<KnowledgeBaseDetail> => {
  const response = await apiClient.get<KnowledgeBaseDetail>(`/org/knowledge-bases/${kbId}`);
  return response.data;
};

/**
 * Create a new knowledge base
 */
export const createKnowledgeBase = async (
  data: CreateKnowledgeBaseRequest
): Promise<KnowledgeBase> => {
  const response = await apiClient.post<KnowledgeBase>('/org/knowledge-bases', data);
  return response.data;
};

/**
 * Update a knowledge base
 */
export const updateKnowledgeBase = async (
  kbId: string,
  data: UpdateKnowledgeBaseRequest
): Promise<KnowledgeBase> => {
  const response = await apiClient.patch<KnowledgeBase>(`/org/knowledge-bases/${kbId}`, data);
  return response.data;
};

/**
 * Delete a knowledge base
 */
export const deleteKnowledgeBase = async (kbId: string): Promise<DeleteKnowledgeBaseResponse> => {
  const response = await apiClient.delete<DeleteKnowledgeBaseResponse>(
    `/org/knowledge-bases/${kbId}`
  );
  return response.data;
};

/**
 * Upload documents to a knowledge base
 * If kbId is provided, uploads to existing KB; otherwise creates new KB with kb_name
 */
export const uploadDocuments = async (
  files: File[],
  options: {
    kb_id?: string;
    kb_name?: string;
    description?: string;
    chunk_size?: number;
    chunk_overlap?: number;
  }
): Promise<UploadKnowledgeResponse> => {
  const formData = new FormData();

  // Add files
  files.forEach((file) => {
    formData.append('files', file);
  });

  // Add optional parameters
  if (options.kb_id) {
    formData.append('kb_id', options.kb_id);
  }
  if (options.kb_name) {
    formData.append('kb_name', options.kb_name);
  }
  if (options.description) {
    formData.append('description', options.description);
  }
  if (options.chunk_size !== undefined) {
    formData.append('chunk_size', options.chunk_size.toString());
  }
  if (options.chunk_overlap !== undefined) {
    formData.append('chunk_overlap', options.chunk_overlap.toString());
  }

  const response = await apiClient.post<UploadKnowledgeResponse>(
    '/org/upload-knowledge',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  );
  return response.data;
};
