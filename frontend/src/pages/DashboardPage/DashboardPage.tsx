import { useState, useEffect, useCallback, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import { HiSearch, HiDocumentText, HiTrash, HiClock, HiUpload, HiX } from 'react-icons/hi';
import { Header } from '@/components/layout/Header';
import { PageContainer } from '@/components/layout/PageContainer';
import { Button, Loader } from '@/components/common';
import { useAuth } from '@/hooks/useAuth';
import { documentsApi, searchHistoryApi } from '@/api';
import type { SearchHistoryItem } from '@/api';
import { formatFileSize, formatRelativeTime } from '@/utils/formatters';
import { FILE_LIMITS, ROUTES } from '@/utils/constants';
import type { Document } from '@/types';
import styles from './DashboardPage.module.css';

export function DashboardPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  
  // Search state
  const [query, setQuery] = useState('');
  const [searchHistory, setSearchHistory] = useState<SearchHistoryItem[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  
  // Documents state
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoadingDocs, setIsLoadingDocs] = useState(true);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  // Stats
  const stats = [
    { icon: HiDocumentText, label: 'Total Documents', value: documents.length.toString() },
    { icon: HiClock, label: 'Recent Searches', value: searchHistory.length.toString() },
  ];

  // Fetch search history
  const fetchSearchHistory = useCallback(async () => {
    try {
      const response = await searchHistoryApi.getHistory(5);
      setSearchHistory(response.data);
    } catch (error) {
      console.error('Failed to fetch search history:', error);
    } finally {
      setIsLoadingHistory(false);
    }
  }, []);

  // Fetch documents
  const fetchDocuments = useCallback(async () => {
    try {
      const response = await documentsApi.getDocuments();
      setDocuments(response.data.documents);
    } catch (error) {
      console.error('Failed to fetch documents:', error);
    } finally {
      setIsLoadingDocs(false);
    }
  }, []);

  useEffect(() => {
    fetchSearchHistory();
    fetchDocuments();
  }, [fetchSearchHistory, fetchDocuments]);

  // Handle search submit
  const handleSearch = async (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    // Add to search history
    try {
      await searchHistoryApi.addHistory(query.trim());
    } catch (error) {
      console.error('Failed to save search history:', error);
    }

    // Navigate to search results page
    navigate(`${ROUTES.SEARCH}?q=${encodeURIComponent(query.trim())}`);
  };

  // Handle clicking a history item
  const handleHistoryClick = (historyQuery: string) => {
    setQuery(historyQuery);
    navigate(`${ROUTES.SEARCH}?q=${encodeURIComponent(historyQuery)}`);
  };

  // Delete history item
  const handleDeleteHistory = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await searchHistoryApi.deleteHistory(id);
      setSearchHistory(prev => prev.filter(item => item.id !== id));
    } catch (error) {
      console.error('Failed to delete history item:', error);
    }
  };

  // File upload
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

  // Delete document
  const handleDeleteDocument = async (id: string) => {
    if (!confirm('Are you sure you want to delete this document?')) return;

    try {
      await documentsApi.deleteDocument(id);
      setDocuments(prev => prev.filter(doc => doc.id !== id));
    } catch (error) {
      console.error('Failed to delete document:', error);
    }
  };

  const getStatusClass = (status: Document['status']) => {
    return `${styles.statusBadge} ${styles[status]}`;
  };

  return (
    <>
      <Header />
      <PageContainer title={`Hi, ${user?.name?.split(' ')[0] || 'User'}`}>
        {/* Stats */}
        <div className={styles.stats}>
          {stats.map((stat) => (
            <div key={stat.label} className={styles.statCard}>
              <div className={styles.statIcon}>
                <stat.icon size={20} />
              </div>
              <div className={styles.statContent}>
                <p className={styles.statValue}>{stat.value}</p>
                <p className={styles.statLabel}>{stat.label}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Search Section */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Search Documents</h2>
          <form className={styles.searchForm} onSubmit={handleSearch}>
            <div className={styles.searchInputWrapper}>
              <HiSearch className={styles.searchIcon} size={20} />
              <input
                type="text"
                className={styles.searchInput}
                placeholder="Enter a phrase or sentence to search across all PDFs..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <Button type="submit" disabled={!query.trim()}>
              Search
            </Button>
          </form>

          {/* Search History */}
          {!isLoadingHistory && searchHistory.length > 0 && (
            <div className={styles.searchHistory}>
              <p className={styles.historyLabel}>Recent searches:</p>
              <div className={styles.historyList}>
                {searchHistory.map((item) => (
                  <div
                    key={item.id}
                    className={styles.historyItem}
                    onClick={() => handleHistoryClick(item.query)}
                  >
                    <HiClock size={14} />
                    <span className={styles.historyQuery}>{item.query}</span>
                    <button
                      className={styles.historyDelete}
                      onClick={(e) => handleDeleteHistory(item.id, e)}
                      aria-label="Delete"
                    >
                      <HiX size={14} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>

        {/* Documents Section */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Your Documents</h2>
          
          {/* Upload Area */}
          <div
            {...getRootProps()}
            className={`${styles.dropzone} ${isDragActive ? styles.active : ''}`}
          >
            <input {...getInputProps()} />
            <HiUpload size={32} />
            <p className={styles.dropzoneText}>
              {isDragActive
                ? 'Drop your PDF files here'
                : 'Drag & drop PDF files here, or click to select'}
            </p>
            <p className={styles.dropzoneHint}>
              Max file size: {formatFileSize(FILE_LIMITS.MAX_FILE_SIZE)}
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

          {/* Documents List */}
          {isLoadingDocs ? (
            <div className={styles.loading}>
              <Loader text="Loading documents..." />
            </div>
          ) : documents.length === 0 ? (
            <div className={styles.emptyState}>
              <HiDocumentText size={48} />
              <p>No documents uploaded yet</p>
              <p className={styles.emptyHint}>Upload your first PDF to get started</p>
            </div>
          ) : (
            <div className={styles.documentsList}>
              <div className={styles.documentsHeader}>
                <span>Name</span>
                <span>Size</span>
                <span>Status</span>
                <span>Uploaded</span>
                <span></span>
              </div>
              {documents.map((doc) => (
                <div key={doc.id} className={styles.documentRow}>
                  <span className={styles.docName}>
                    <HiDocumentText size={18} />
                    {doc.filename}
                  </span>
                  <span className={styles.docSize}>{formatFileSize(doc.file_size)}</span>
                  <span className={getStatusClass(doc.status)}>{doc.status}</span>
                  <span className={styles.docDate}>{formatRelativeTime(doc.created_at)}</span>
                  <button
                    className={styles.deleteBtn}
                    onClick={() => handleDeleteDocument(doc.id)}
                    aria-label="Delete document"
                  >
                    <HiTrash size={16} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
      </PageContainer>
    </>
  );
}

export default DashboardPage;
