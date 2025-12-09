export type DocumentStatus = 'queued' | 'processing' | 'ready' | 'failed';

export interface Document {
  id: string;
  name: string;
  size: number;
  pageCount: number;
  status: DocumentStatus;
  uploadedAt: string;
  processedAt?: string;
}

export interface DocumentUploadResponse {
  documents: Pick<Document, 'id' | 'name' | 'status'>[];
}

export interface DocumentStatusResponse {
  id: string;
  status: DocumentStatus;
  progress: number;
  message: string;
}

export interface DocumentListParams {
  page?: number;
  limit?: number;
  status?: DocumentStatus;
}

export interface Pagination {
  page: number;
  limit: number;
  total: number;
  totalPages: number;
}

export interface DocumentListResponse {
  documents: Document[];
  pagination: Pagination;
}
