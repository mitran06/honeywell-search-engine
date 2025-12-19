import { apiClient } from "@/api"

export interface SearchScores {
  fusion: number
  semantic: number
  lexical: number
  triple: number
}

export interface SearchResult {
  documentId: string
  documentName: string
  pageNumber: number
  snippet: string
  confidenceScore: number
  scores: SearchScores
}

export interface SearchResponse {
  results: SearchResult[]
  totalResults: number
  searchTime: number
}

export async function searchDocuments(
  query: string,
  limit: number = 5
): Promise<SearchResponse> {
  const res = await apiClient.post("/search", {
    query,
    limit,
  })

  // Backend returns ApiResponse { success, data, message }
  // Correct unwrap:
  return res.data.data
}
