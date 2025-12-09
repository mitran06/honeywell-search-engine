import { useState, useEffect, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { HiUpload, HiDocumentText, HiTrash, HiRefresh } from 'react-icons/hi';
import { Header } from '@/components/layout/Header';
import { PageContainer } from '@/components/layout/PageContainer';
import { Button, Loader } from '@/components/common';
import { documentsApi } from '@/api';
import { formatFileSize, formatRelativeTime } from '@/utils/formatters';
import { FILE_LIMITS } from '@/utils/constants';
import type { Document } from '@/types';
import styles from './DocumentsPage.module.css';

export function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const fetchDocuments = useCallback(async () => {
    try {
      const response = await documentsApi.getDocuments();
      setDocuments(response.data.documents);
    } catch (error) {
      console.error('Failed to fetch documents:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;

    setIsUploading(true);
    setUploadProgress(0);

    try {
      await documentsApi.uploadDocuments(acceptedFiles, (progress) => {
        setUploadProgress(progress);
      });
      await fetchDocuments();
    } catch (error) {
      console.error('Upload failed:', error);
    } finally {
      setIsUploading(false);
      setUploadProgress(null);
    }
  }, [fetchDocuments]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: FILE_LIMITS.ACCEPTED_TYPES,
    maxSize: FILE_LIMITS.MAX_FILE_SIZE,
    disabled: isUploading,
  });

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this document?')) return;

    try {
      await documentsApi.deleteDocument(id);
      setDocuments((prev) => prev.filter((doc) => doc.id !== id));
    } catch (error) {
      console.error('Failed to delete document:', error);
    }
  };

  const getStatusBadgeClass = (status: Document['status']) => {
    return `${styles.statusBadge} ${styles[status]}`;
  };

  return (
    <>
      <Header />
      <PageContainer
        title="Documents"
        description="Upload and manage your PDF documents"
        action={
          <Button
            variant="secondary"
            leftIcon={<HiRefresh size={18} />}
            onClick={fetchDocuments}
          >
            Refresh
          </Button>
        }
      >
        <div className={styles.uploadSection}>
          <div
            {...getRootProps()}
            className={`${styles.dropzone} ${isDragActive ? styles.active : ''}`}
          >
            <input {...getInputProps()} />
            <HiUpload size={48} className={styles.dropzoneIcon} />
            <p className={styles.dropzoneText}>
              {isDragActive
                ? 'Drop your PDF files here'
                : 'Drag & drop PDF files here, or click to select'}
            </p>
            <p className={styles.dropzoneHint}>
              Maximum file size: {formatFileSize(FILE_LIMITS.MAX_FILE_SIZE)}
            </p>
          </div>

          {isUploading && uploadProgress !== null && (
            <div className={styles.uploadProgress}>
              <div className={styles.progressBar}>
                <div
                  className={styles.progressFill}
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              <p className={styles.progressText}>Uploading... {uploadProgress}%</p>
            </div>
          )}
        </div>

        {isLoading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 'var(--spacing-2xl)' }}>
            <Loader size="lg" text="Loading documents..." />
          </div>
        ) : documents.length > 0 ? (
          <div className={styles.documentsGrid}>
            {documents.map((doc) => (
              <div key={doc.id} className={styles.documentCard}>
                <div className={styles.documentHeader}>
                  <HiDocumentText size={24} className={styles.documentIcon} />
                  <span className={styles.documentName} title={doc.name}>
                    {doc.name}
                  </span>
                </div>
                <div className={styles.documentBody}>
                  <div className={styles.documentMeta}>
                    <span>{formatFileSize(doc.size)}</span>
                    <span>{doc.pageCount} pages</span>
                    <span>Uploaded {formatRelativeTime(doc.uploadedAt)}</span>
                  </div>
                </div>
                <div className={styles.documentFooter}>
                  <span className={getStatusBadgeClass(doc.status)}>
                    {doc.status.charAt(0).toUpperCase() + doc.status.slice(1)}
                  </span>
                  <button
                    type="button"
                    className={styles.deleteButton}
                    onClick={() => handleDelete(doc.id)}
                    aria-label="Delete document"
                  >
                    <HiTrash size={18} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className={styles.emptyState}>
            <HiDocumentText size={48} className={styles.emptyIcon} />
            <h3 className={styles.emptyTitle}>No documents yet</h3>
            <p className={styles.emptyDescription}>
              Upload your first PDF to get started
            </p>
          </div>
        )}
      </PageContainer>
    </>
  );
}

export default DocumentsPage;
