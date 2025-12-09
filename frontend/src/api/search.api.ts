import apiClient from './client';
import type { 
  ApiResponse, 
  SearchRequest, 
  SearchResponse, 
  SearchHistoryResponse 
} from '@/types';

export const searchApi = {
  search: async (request: SearchRequest): Promise<ApiResponse<SearchResponse>> => {
    const response = await apiClient.post<ApiResponse<SearchResponse>>('/search', request);
    return response.data;
  },

  getSearchHistory: async (limit?: number): Promise<ApiResponse<SearchHistoryResponse>> => {
    const response = await apiClient.get<ApiResponse<SearchHistoryResponse>>('/search/history', {
      params: { limit },
    });
    return response.data;
  },
};

export default searchApi;
