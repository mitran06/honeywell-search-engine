import { useState, useEffect } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { Document, Page, pdfjs } from 'react-pdf';
import { HiArrowLeft, HiChevronLeft, HiChevronRight, HiZoomIn, HiZoomOut, HiExclamation } from 'react-icons/hi';
import { Header } from '@/components/layout/Header';
import { Button, Loader } from '@/components/common';
import { documentsApi } from '@/api';
import { ROUTES } from '@/utils/constants';
import styles from './ViewerPage.module.css';

import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

// Set up pdf.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

export function ViewerPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [numPages, setNumPages] = useState<number>(0);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [scale, setScale] = useState<number>(1.0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [documentName, setDocumentName] = useState<string>('');

  useEffect(() => {
    const loadDocument = async () => {
      if (!documentId) {
        setError('No document ID provided');
        setIsLoading(false);
        return;
      }

      try {
        // Get document metadata
        const metaResponse = await documentsApi.getDocument(documentId);
        setDocumentName(metaResponse.data.filename);

        // Get PDF file
        const blob = await documentsApi.getDocumentFile(documentId);
        const url = URL.createObjectURL(blob);
        setPdfUrl(url);

        // Set initial page from URL params
        const pageParam = searchParams.get('page');
        if (pageParam) {
          setCurrentPage(parseInt(pageParam, 10));
        }
      } catch (err) {
        console.error('Failed to load document:', err);
        setError('Failed to load document');
      } finally {
        setIsLoading(false);
      }
    };

    loadDocument();

    return () => {
      if (pdfUrl) {
        URL.revokeObjectURL(pdfUrl);
      }
    };
  }, [documentId, searchParams]);

  const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
  };

  const goToPage = (page: number) => {
    if (page >= 1 && page <= numPages) {
      setCurrentPage(page);
    }
  };

  const handlePageInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseInt(e.target.value, 10);
    if (!isNaN(value)) {
      goToPage(value);
    }
  };

  const zoomIn = () => setScale((prev) => Math.min(prev + 0.25, 3));
  const zoomOut = () => setScale((prev) => Math.max(prev - 0.25, 0.5));

  return (
    <>
      <Header />
      <div className={styles.container}>
        <div className={styles.toolbar}>
          <div className={styles.toolbarLeft}>
            <Button
              variant="ghost"
              size="sm"
              leftIcon={<HiArrowLeft size={18} />}
              onClick={() => navigate(ROUTES.SEARCH)}
            >
              Back
            </Button>
            <span className={styles.documentTitle}>{documentName}</span>
          </div>

          <div className={styles.toolbarCenter}>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => goToPage(currentPage - 1)}
              disabled={currentPage <= 1}
            >
              <HiChevronLeft size={20} />
            </Button>
            <input
              type="number"
              className={styles.pageInput}
              value={currentPage}
              onChange={handlePageInputChange}
              min={1}
              max={numPages}
            />
            <span className={styles.pageTotal}>of {numPages}</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => goToPage(currentPage + 1)}
              disabled={currentPage >= numPages}
            >
              <HiChevronRight size={20} />
            </Button>
          </div>

          <div className={styles.toolbarRight}>
            <button type="button" className={styles.zoomButton} onClick={zoomOut}>
              <HiZoomOut size={20} />
            </button>
            <span className={styles.zoomLevel}>{Math.round(scale * 100)}%</span>
            <button type="button" className={styles.zoomButton} onClick={zoomIn}>
              <HiZoomIn size={20} />
            </button>
          </div>
        </div>

        <div className={styles.viewer}>
          {isLoading && (
            <div className={styles.loadingContainer}>
              <Loader size="lg" text="Loading document..." />
            </div>
          )}

          {error && (
            <div className={styles.errorContainer}>
              <HiExclamation size={48} className={styles.errorIcon} />
              <p className={styles.errorText}>{error}</p>
              <Button
                variant="secondary"
                className={styles.backButton}
                onClick={() => navigate(ROUTES.DOCUMENTS)}
              >
                Back to Documents
              </Button>
            </div>
          )}

          {pdfUrl && !error && (
            <Document
              file={pdfUrl}
              onLoadSuccess={onDocumentLoadSuccess}
              loading={<Loader size="lg" text="Loading PDF..." />}
              error={
                <div className={styles.errorContainer}>
                  <HiExclamation size={48} className={styles.errorIcon} />
                  <p className={styles.errorText}>Failed to load PDF</p>
                </div>
              }
            >
              <div className={styles.pageContainer}>
                <Page
                  pageNumber={currentPage}
                  scale={scale}
                  loading={<Loader size="md" />}
                />
              </div>
            </Document>
          )}
        </div>
      </div>
    </>
  );
}

export default ViewerPage;
