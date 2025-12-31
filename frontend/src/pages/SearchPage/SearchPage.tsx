import { useEffect, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { HiArrowLeft, HiSearch } from "react-icons/hi"
import { searchDocuments } from "@/api/search.api"
import type { SearchResult } from "@/types"
import { ROUTES } from "@/utils/constants"

export default function SearchPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const query = searchParams.get("q") || ""

  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [searchTime, setSearchTime] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!query.trim()) {
      navigate(ROUTES.DASHBOARD)
      return
    }

    const runSearch = async () => {
      setLoading(true)
      setError(null)

      try {
        const data = await searchDocuments(query, 20)
        setResults(data.results)
        setSearchTime(data.searchTime)
      } catch {
        setError("Search failed")
        setResults([])
      } finally {
        setLoading(false)
      }
    }

    runSearch()
  }, [query, navigate])

  const openResult = (r: SearchResult) => {
    navigate(
      `/viewer/${r.documentId}?page=${r.pageNumber}&highlight=${encodeURIComponent(
        r.snippet
      )}`
    )
  }

  return (
    <div style={{ padding: 24 }}>
      <button
        onClick={() => navigate(ROUTES.DASHBOARD)}
        style={{
          marginBottom: 16,
          display: "flex",
          alignItems: "center",
          gap: 6,
          border: "none",
          background: "transparent",
          cursor: "pointer",
          color: "var(--panel-text-primary)",
        }}
      >
        <HiArrowLeft size={18} />
        Back
      </button>

      <div style={{ marginBottom: 12 }}>
        <strong>Results for:</strong> "{query}"
      </div>

      {loading && (
        <div style={{ padding: 32, textAlign: "center" }}>
          <HiSearch size={32} />
          <div>Searching…</div>
        </div>
      )}

      {!loading && error && (
        <div style={{ color: "var(--danger)" }}>{error}</div>
      )}

      {!loading && !error && (
        <>
          <div style={{ marginBottom: 12, fontSize: 13 }}>
            {results.length} result{results.length !== 1 ? "s" : ""}
            {searchTime !== null && ` in ${searchTime.toFixed(3)}s`}
          </div>

          {results.length === 0 && (
            <div>No results found. Try a different query.</div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {results.map((r, idx) => (
              <div
                key={`${r.documentId}-${r.pageNumber}-${idx}`}
                onClick={() => openResult(r)}
                style={{
                  padding: 16,
                  borderRadius: 12,
                  background: "var(--panel-bg)",
                  cursor: "pointer",
                  boxShadow: "var(--shadow-sm)",
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: 6 }}>
                  {r.documentName} · Page {r.pageNumber}
                </div>
                <div style={{ fontSize: 14, marginBottom: 8 }}>
                  {r.snippet}
                </div>
                <div style={{ fontSize: 12, opacity: 0.7 }}>
                  Confidence: {Math.round(r.confidenceScore)}%
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
