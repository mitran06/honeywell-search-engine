import apiClient from './client';
import type { 
  ApiResponse, 
  Document, 
  DocumentListResponse, 
  DocumentListParams,
  DocumentUploadResponse,
  DocumentStatusResponse 
} from '@/types';

export const documentsApi = {
  getDocuments: async (params?: DocumentListParams): Promise<ApiResponse<DocumentListResponse>> => {
    const response = await apiClient.get<ApiResponse<DocumentListResponse>>('/documents', { params });
    return response.data;
  },

  getDocument: async (id: string): Promise<ApiResponse<Document>> => {
    const response = await apiClient.get<ApiResponse<Document>>(`/documents/${id}`);
    return response.data;
  },

  uploadDocuments: async (
    files: File[],
    onUploadProgress?: (progress: number) => void
  ): Promise<ApiResponse<DocumentUploadResponse>> => {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append('files', file);
    });

    const response = await apiClient.post<ApiResponse<DocumentUploadResponse>>(
      '/documents/upload',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total && onUploadProgress) {
            const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            onUploadProgress(progress);
          }
        },
      }
    );
    return response.data;
  },

  deleteDocument: async (id: string): Promise<ApiResponse<null>> => {
    const response = await apiClient.delete<ApiResponse<null>>(`/documents/${id}`);
    return response.data;
  },

  getDocumentStatus: async (id: string): Promise<ApiResponse<DocumentStatusResponse>> => {
    const response = await apiClient.get<ApiResponse<DocumentStatusResponse>>(`/documents/${id}/status`);
    return response.data;
  },

  getDocumentFile: async (id: string): Promise<Blob> => {
    const response = await apiClient.get(`/documents/${id}/file`, {
      responseType: 'blob',
    });
    return response.data;
  },
};

export default documentsApi;
