export type DocumentStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface Document {
  id: string;
  filename: string;
  file_size: number;
  page_count: number | null;
  status: DocumentStatus;
  created_at: string;
  updated_at?: string;
  error_message?: string | null;
  object_key?: string;
}

export interface UploadedDocument {
  id: string;
  filename: string;
  object_key: string;
  file_size: number;
  status: DocumentStatus;
}

export interface UploadError {
  filename: string;
  error: string;
}

export interface DocumentUploadResponse {
  uploaded: UploadedDocument[];
  errors: UploadError[];
  total_uploaded: number;
  total_errors: number;
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

export interface DocumentListResponse {
  documents: Document[];
  total: number;
}
