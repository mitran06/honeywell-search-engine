import { useState, useRef } from "react"
import { HiSearch } from "react-icons/hi"
import { searchDocuments } from "@/api/search.api"
import { SearchResults } from "../search/SearchResults"
import type { SearchResult } from "@/types"

interface Props {
  onOpenResult: (documentId: string, page: number) => void
}

export function RightPanelSearchChat({ onOpenResult }: Props) {
  const [query, setQuery] = useState("")
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<SearchResult[]>([])
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSearch = async () => {
    if (!query.trim()) return

    setLoading(true)
    setError(null)

    try {
      const data = await searchDocuments(query, 5)
      setResults(data.results)
    } catch (err) {
      console.error("Search failed:", err)
      setResults([])
      setError("Search failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* RESULTS */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        <SearchResults
          results={results}
          onSelect={(r) => onOpenResult(r.documentId, r.pageNumber)}
        />
      </div>

      {/* BOTTOM SEARCH BAR — DABBA PRESERVED */}
      <div
        style={{
          padding: 12,
          borderTop: "none",
          background: "var(--panel-bg)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSearch()
            }}
            placeholder="Search documents"
            disabled={loading}
            style={{
              flex: 1,
              height: 44,
              padding: "0 14px",
              borderRadius: 14,
              border: "none",
              background: "var(--accent-gradient)",
              color: "var(--panel-text-primary)",
              outline: "none",
              fontSize: 14,
              boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
            }}
          />

          <button
            type="button"
            onClick={handleSearch}
            disabled={loading}
            style={{
              width: 44,
              height: 44,
              borderRadius: 14,
              border: "none",
              background: "var(--accent-gradient)",
              color: "var(--accent-gradient)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
              flexShrink: 0,
              boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
            }}
          >
            <HiSearch size={20} />
          </button>
        </div>

        {error && (
          <div
            style={{
              marginTop: 6,
              fontSize: 12,
              color: "var(--color-error)",
            }}
          >
            {error}
          </div>
        )}
      </div>
    </div>
  )
}
