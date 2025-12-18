import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { HiUpload, HiX, HiDocumentText } from 'react-icons/hi';
import { Modal, Button, Loader } from '@/components/common';
import { documentsApi } from '@/api';
import { formatFileSize } from '@/utils/formatters';
import styles from './UploadModal.module.css';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

interface UploadFile {
  file: File;
  progress: number;
  status: 'pending' | 'uploading' | 'completed' | 'error';
  error?: string;
}

export function UploadModal({ isOpen, onClose, onSuccess }: UploadModalProps) {
  const [files, setFiles] = useState<UploadFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const newFiles = acceptedFiles.map((file) => ({
      file,
      progress: 0,
      status: 'pending' as const,
    }));
    setFiles((prev) => [...prev, ...newFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
    },
    multiple: true,
  });

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const uploadFiles = async () => {
    if (files.length === 0) return;

    setIsUploading(true);

    for (let i = 0; i < files.length; i++) {
      if (files[i].status !== 'pending') continue;

      setFiles((prev) =>
        prev.map((f, idx) =>
          idx === i ? { ...f, status: 'uploading' as const } : f
        )
      );

      try {
        await documentsApi.uploadDocuments([files[i].file]);
        setFiles((prev) =>
          prev.map((f, idx) =>
            idx === i ? { ...f, status: 'completed' as const, progress: 100 } : f
          )
        );
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Upload failed';
        setFiles((prev) =>
          prev.map((f, idx) =>
            idx === i ? { ...f, status: 'error' as const, error: message } : f
          )
        );
      }
    }

    setIsUploading(false);

    // Check if all uploads succeeded
    const allCompleted = files.every((f) => f.status === 'completed');
    if (allCompleted) {
      onSuccess();
      handleClose();
    }
  };

  const handleClose = () => {
    if (!isUploading) {
      setFiles([]);
      onClose();
    }
  };

  const completedCount = files.filter((f) => f.status === 'completed').length;
  const hasErrors = files.some((f) => f.status === 'error');

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Upload Documents">
      <div className={styles.content}>
        <div
          {...getRootProps()}
          className={`${styles.dropzone} ${isDragActive ? styles.active : ''}`}
        >
          <input {...getInputProps()} />
          <HiUpload size={48} className={styles.dropIcon} />
          <p className={styles.dropText}>
            {isDragActive
              ? 'Drop PDF files here'
              : 'Drag & drop PDF files here, or click to select'}
          </p>
          <span className={styles.dropHint}>Only PDF files are accepted</span>
        </div>

        {files.length > 0 && (
          <div className={styles.fileList}>
            {files.map((uploadFile, index) => (
              <div key={index} className={styles.fileItem}>
                <HiDocumentText size={24} className={styles.fileIcon} />
                <div className={styles.fileInfo}>
                  <span className={styles.fileName}>{uploadFile.file.name}</span>
                  <span className={styles.fileSize}>
                    {formatFileSize(uploadFile.file.size)}
                  </span>
                </div>
                <div className={styles.fileStatus}>
                  {uploadFile.status === 'uploading' && <Loader size="sm" />}
                  {uploadFile.status === 'completed' && (
                    <span className={styles.success}>✓</span>
                  )}
                  {uploadFile.status === 'error' && (
                    <span className={styles.error} title={uploadFile.error}>
                      ✗
                    </span>
                  )}
                  {uploadFile.status === 'pending' && (
                    <button
                      type="button"
                      className={styles.removeButton}
                      onClick={() => removeFile(index)}
                    >
                      <HiX size={18} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        <div className={styles.footer}>
          {hasErrors && (
            <p className={styles.errorMessage}>
              Some files failed to upload. Please try again.
            </p>
          )}
          <div className={styles.actions}>
            <Button variant="secondary" onClick={handleClose} disabled={isUploading}>
              Cancel
            </Button>
            <Button
              onClick={uploadFiles}
              disabled={files.length === 0 || isUploading}
            >
              {isUploading
                ? `Uploading... (${completedCount}/${files.length})`
                : `Upload ${files.length} file${files.length !== 1 ? 's' : ''}`}
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}

export default UploadModal;
