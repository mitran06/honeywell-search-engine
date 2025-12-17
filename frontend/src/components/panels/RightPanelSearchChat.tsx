import React, { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { HiSearch } from "react-icons/hi";
import { searchApi } from "@/api";
import { Loader } from "@/components/common";
import type { SearchResult } from "@/types";

export function RightPanelSearchChat({
  openDocument,
}: {
  openDocument?: (id: string, page?: number) => void;
}) {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const initialQuery = searchParams.get("q") || "";
  const [query, setQuery] = useState(initialQuery);

  const [results, setResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const runSearch = async (text: string) => {
    if (!text.trim()) return;
    setIsLoading(true);
    setHasSearched(true);
    const res = await searchApi.search({ query: text.trim(), limit: 20 });
    setResults(res.data.results);
    setIsLoading(false);
  };

  useEffect(() => {
    if (initialQuery) runSearch(initialQuery);
  }, [initialQuery]);

  return (
    <div
      style={{
        padding: 16,
        height: "100%",
        display: "flex",
        flexDirection: "column",
        background: "var(--panel-bg)",
        color: "var(--panel-text-primary)",
      }}
    >
      {/* Header */}
      <div
        style={{
          borderRadius: 14,
          padding: 14,
          marginBottom: 16,
          background: "var(--accent-gradient)",
          boxShadow: "0 8px 24px rgba(0,0,0,0.35)",
        }}
      >
        <div style={{ fontWeight: 600 }}>Search</div>
        <div style={{ fontSize: 12, color: "var(--panel-text-muted)" }}>
          Find answers across your PDFs
        </div>
      </div>

      {/* Results */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {isLoading && <Loader text="Searching..." />}
        {!isLoading && hasSearched && results.length === 0 && (
          <div style={{ textAlign: "center", color: "var(--panel-text-muted)" }}>
            No results
          </div>
        )}
      </div>

      {/* Input */}
      <div
        style={{
          display: "flex",
          gap: 8,
          marginTop: 12,
        }}
      >
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === "Enter" && runSearch(query)}
          placeholder="Search documents..."
          style={{
            flex: 1,
            padding: "10px 12px",
            background: "var(--accent-gradient)",
            border: "none",
            borderRadius: 8,
            color: "var(--panel-text-primary)",
            boxShadow: "0 8px 24px rgba(0,0,0,0.35)",
          }}
        />

        <button
          onClick={() => runSearch(query)}
          style={{
            background: "var(--cta-gradient)",
            border: "none",
            color: "var(--cta-text)",
            padding: "10px 14px",
            borderRadius: 8,
            cursor: "pointer",
            boxShadow: "0 8px 24px rgba(0,0,0,0.35)",
          }}
        >
          <HiSearch size={18} />
        </button>
      </div>
    </div>
  );
}

export default RightPanelSearchChat;
