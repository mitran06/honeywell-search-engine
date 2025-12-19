import { useState, useEffect } from "react"
import { useParams, useSearchParams, useNavigate } from "react-router-dom"
import { Document, Page, pdfjs } from "react-pdf"
import {
  HiArrowLeft,
  HiChevronLeft,
  HiChevronRight,
  HiZoomIn,
  HiZoomOut,
  HiExclamation,
} from "react-icons/hi"
import { Button, Loader } from "@/components/common"
import { documentsApi } from "@/api"
import { ROUTES } from "@/utils/constants"
import styles from "./ViewerPage.module.css"

import "react-pdf/dist/Page/AnnotationLayer.css"
import "react-pdf/dist/Page/TextLayer.css"

// FIXED WORKER SETUP FOR VITE
import workerSrc from "pdfjs-dist/build/pdf.worker.mjs?url"
pdfjs.GlobalWorkerOptions.workerSrc = workerSrc

export function ViewerPage({
  documentIdOverride,
  pageOverride,
}: {
  documentIdOverride?: string
  pageOverride?: number
}) {
  const params = useParams<{ documentId: string }>()
  const urlId = params.documentId
  const documentId = documentIdOverride || urlId

  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  const [pdfBlob, setPdfBlob] = useState<Blob | null>(null)
  const [numPages, setNumPages] = useState(0)
  const [currentPage, setCurrentPage] = useState(pageOverride || 1)
  const [scale, setScale] = useState(1.0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [documentName, setDocumentName] = useState("")

  useEffect(() => {
    const loadDocument = async () => {
      if (!documentId) {
        setError("No document ID provided")
        setIsLoading(false)
        return
      }

      try {
        setIsLoading(true)
        setError(null)

        const meta = await documentsApi.getDocument(documentId)
        setDocumentName(meta.data.filename)

        // 🔑 KEY FIX: keep blob, do NOT convert to object URL
        const blob = await documentsApi.getDocumentFile(documentId)
        setPdfBlob(blob)

        if (pageOverride) {
          setCurrentPage(pageOverride)
        } else {
          const pageFromUrl = searchParams.get("page")
          if (pageFromUrl) setCurrentPage(parseInt(pageFromUrl, 10))
        }
      } catch (err) {
        console.error("Failed to load PDF:", err)
        setError("Failed to load PDF file")
      } finally {
        setIsLoading(false)
      }
    }

    loadDocument()
  }, [documentId, pageOverride])

  const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages)
  }

  const goToPage = (page: number) => {
    if (page >= 1 && page <= numPages) setCurrentPage(page)
  }

  const zoomIn = () => setScale((s) => Math.min(s + 0.25, 3))
  const zoomOut = () => setScale((s) => Math.max(s - 0.25, 0.5))

  return (
    <div className={styles.container}>
      {/* Toolbar */}
      <div className={styles.toolbar}>
        <div className={styles.toolbarLeft}>
          <Button
            variant="ghost"
            size="sm"
            leftIcon={<HiArrowLeft size={18} />}
            onClick={() => navigate(ROUTES.DASHBOARD)}
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
            onChange={(e) => goToPage(parseInt(e.target.value, 10))}
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
          <button className={styles.zoomButton} onClick={zoomOut}>
            <HiZoomOut size={20} />
          </button>
          <span className={styles.zoomLevel}>
            {Math.round(scale * 100)}%
          </span>
          <button className={styles.zoomButton} onClick={zoomIn}>
            <HiZoomIn size={20} />
          </button>
        </div>
      </div>

      {/* Viewer */}
      <div className={styles.viewer}>
        {isLoading && (
          <div className={styles.loadingContainer}>
            <Loader size="lg" text="Loading PDF..." />
          </div>
        )}

        {error && (
          <div className={styles.errorContainer}>
            <HiExclamation size={48} className={styles.errorIcon} />
            <p className={styles.errorText}>{error}</p>
          </div>
        )}

        {pdfBlob && !error && (
          <Document
            file={pdfBlob}   // 🔑 THIS FIXES IT
            onLoadSuccess={onDocumentLoadSuccess}
            loading={<Loader size="lg" text="Loading PDF..." />}
          >
            <div className={styles.pageContainer}>
              <Page pageNumber={currentPage} scale={scale} />
            </div>
          </Document>
        )}
      </div>
    </div>
  )
}

export default ViewerPage
