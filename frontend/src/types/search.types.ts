export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface TextHighlight {
  text: string;
  startOffset: number;
  endOffset: number;
  boundingBox?: BoundingBox;
}

export interface SearchResult {
  documentId: string;
  documentName: string;
  pageNumber: number;
  snippet: string;
  confidenceScore: number;
  highlights: TextHighlight[];
  scores: {
    fusion: number;
    semantic: number;
    lexical: number;
    triple: number;
  };
}

export interface SearchRequest {
  query: string;
  documentIds?: string[];
  limit?: number;
}

export interface SearchResponse {
  results: SearchResult[];
  totalResults: number;
  searchTime: number;
}

export interface SearchHistoryItem {
  id: string;
  query: string;
  resultCount: number;
  searchedAt: string;
}

export interface SearchHistoryResponse {
  searches: SearchHistoryItem[];
}
