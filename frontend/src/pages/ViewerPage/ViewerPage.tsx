import { useEffect, useState } from "react"
import { useParams, useSearchParams, useNavigate } from "react-router-dom"
import { HiArrowLeft } from "react-icons/hi"
import PdfJsViewer from "@/components/viewer/PdfJsViewer"
import { documentsApi } from "@/api"
import { ROUTES } from "@/utils/constants"

export default function ViewerPage() {
  const { documentId } = useParams<{ documentId: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  const pageParam = searchParams.get("page")
  const highlightParam = searchParams.get("highlight")

  const [docName, setDocName] = useState("")
  const [error, setError] = useState<string | null>(null)

  const page = pageParam ? Number(pageParam) : 1
  const highlightText =
    typeof highlightParam === "string" && highlightParam.trim()
      ? highlightParam
      : null

  useEffect(() => {
    if (!documentId) return

    const loadMeta = async () => {
      try {
        const meta = await documentsApi.getDocument(documentId)
        setDocName(meta.data.filename)
      } catch {
        setError("Failed to load document metadata")
      }
    }

    loadMeta()
  }, [documentId])

  if (!documentId) {
    return <div style={{ padding: 24 }}>Invalid document</div>
  }

  if (error) {
    return <div style={{ padding: 24, color: "var(--danger)" }}>{error}</div>
  }

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "12px 16px",
          borderBottom: "1px solid var(--panel-border)",
          background: "var(--panel-bg)",
        }}
      >
        <button
          onClick={() => navigate(ROUTES.DASHBOARD)}
          style={{
            border: "none",
            background: "transparent",
            cursor: "pointer",
            color: "var(--panel-text-primary)",
          }}
        >
          <HiArrowLeft size={18} />
        </button>

        <span
          style={{
            fontWeight: 600,
            fontSize: 14,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
          title={docName}
        >
          {docName}
        </span>
      </div>

      <div style={{ flex: 1 }}>
        <PdfJsViewer
          documentId={documentId}
          page={page}
          highlightText={highlightText}
        />
      </div>
    </div>
  )
}
