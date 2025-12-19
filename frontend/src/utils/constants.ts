export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

export const APP_NAME =
  import.meta.env.VITE_APP_NAME || 'PDF Search Engine';

export const STORAGE_KEYS = {
  ACCESS_TOKEN: 'accessToken',
  REFRESH_TOKEN: 'refreshToken',
  USER: 'user',
} as const;

export const ROUTES = {
  HOME: '/',
  LOGIN: '/login',
  REGISTER: '/register',
  DASHBOARD: '/dashboard',
  SEARCH: '/search',
  DOCUMENTS: '/documents',
  VIEWER: '/viewer/:documentId',
} as const;

export const FILE_LIMITS = {
  MAX_FILE_SIZE: 500 * 1024 * 1024,
  ACCEPTED_TYPES: {
    'application/pdf': ['.pdf'],
  },
} as const;

export const CONFIDENCE_THRESHOLDS = {
  HIGH: 80,
  MEDIUM: 50,
} as const;
