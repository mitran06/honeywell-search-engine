import { ResultCard } from "../ResultCard"
import type { SearchResult } from "@/types"

interface Props {
  results: SearchResult[]
  onSelect: (result: SearchResult) => void
}

export function SearchResults({ results, onSelect }: Props) {
  if (!results || results.length === 0) return null

  return (
    <div className="space-y-3">
      {results.map((result, idx) => (
        <ResultCard
          key={`${result.documentId}-${result.pageNumber}-${idx}`}
          result={result}
          onClick={() => onSelect(result)}
        />
      ))}
    </div>
  )
}
