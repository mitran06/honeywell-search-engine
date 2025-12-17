import { apiClient } from "@/api";
import type { ApiResponse, Document } from "@/types";

/**
 * Authorization headers helper
 */
function authHeaders() {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export const documentsApi = {
  // ------------------------------------------------------------------
  // List PDFs
  // ------------------------------------------------------------------
  getDocuments: () =>
    apiClient.get<ApiResponse<{ documents: Document[]; total: number }>>(
      "/documents"
    ),

  // ------------------------------------------------------------------
  // Get single PDF metadata
  // ------------------------------------------------------------------
  getDocument: (id: string) =>
    apiClient.get<ApiResponse<Document>>(`/documents/${id}`),

  // ------------------------------------------------------------------
  // Fetch raw PDF blob (viewer)
  // ------------------------------------------------------------------
  getDocumentFile: (id: string) =>
    apiClient
      .get<Blob>(`/documents/${id}/file`, {
        responseType: "blob",
        headers: authHeaders(),
      })
      .then(res => res.data),

  // ------------------------------------------------------------------
  // Upload PDFs
  // ------------------------------------------------------------------
  uploadDocuments: (files: File[], onProgress?: (p: number) => void) => {
    const formData = new FormData();
    files.forEach(file => formData.append("files", file));

    return apiClient.post<ApiResponse>(
      "/documents/upload",
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
          ...authHeaders(),
        },
        onUploadProgress: evt => {
          if (onProgress && evt.total) {
            onProgress(Math.round((evt.loaded * 100) / evt.total));
          }
        },
      }
    );
  },

  // ------------------------------------------------------------------
  // Delete single PDF
  // ------------------------------------------------------------------
  deleteDocument: (id: string) =>
    apiClient.delete<ApiResponse>(`/documents/${id}`),

  // ------------------------------------------------------------------
  // Delete ALL PDFs (user scoped)
  // ------------------------------------------------------------------
  deleteAllDocuments: () =>
    apiClient.delete<ApiResponse>("/documents"),
};
