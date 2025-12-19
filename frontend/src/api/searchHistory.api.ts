import client from './client';

export interface SearchHistoryItem {
  id: string;
  query: string;
  created_at: string;
}

export interface SearchHistoryResponse {
  success: boolean;
  data: SearchHistoryItem[];
}

export const searchHistoryApi = {
  getHistory: async (limit = 10): Promise<SearchHistoryResponse> => {
    const response = await client.get(`/search-history?limit=${limit}`);
    return response.data;
  },

  addHistory: async (query: string): Promise<{ success: boolean }> => {
    const response = await client.post('/search-history', { query });
    return response.data;
  },

  deleteHistory: async (id: string): Promise<{ success: boolean }> => {
    const response = await client.delete(`/search-history/${id}`);
    return response.data;
  },

  clearHistory: async (): Promise<{ success: boolean }> => {
    const response = await client.delete('/search-history');
    return response.data;
  },
};

export default searchHistoryApi;