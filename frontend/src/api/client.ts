import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';
import type { HttpErrorResponse, Token } from '@/types';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Create axios instance
export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Token storage keys
const ACCESS_TOKEN_KEY = 'pedagogy_access_token';
const REFRESH_TOKEN_KEY = 'pedagogy_refresh_token';
const PRELIMINARY_TOKEN_KEY = 'pedagogy_preliminary_token';

// Token management functions
export const getAccessToken = (): string | null => {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
};

export const getRefreshToken = (): string | null => {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
};

export const getPreliminaryToken = (): string | null => {
  return localStorage.getItem(PRELIMINARY_TOKEN_KEY);
};

export const setTokens = (tokens: Token): void => {
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
};

export const setPreliminaryToken = (token: string): void => {
  localStorage.setItem(PRELIMINARY_TOKEN_KEY, token);
};

export const clearTokens = (): void => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(PRELIMINARY_TOKEN_KEY);
};

export const clearPreliminaryToken = (): void => {
  localStorage.removeItem(PRELIMINARY_TOKEN_KEY);
};

// Request interceptor - Add auth token to requests
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Don't override if Authorization header is already set explicitly
    if (config.headers?.Authorization) {
      return config;
    }
    // First try access token, then fall back to preliminary token
    const token = getAccessToken() || getPreliminaryToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Track if we're currently refreshing to prevent multiple refresh calls
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((promise) => {
    if (error) {
      promise.reject(error);
    } else if (token) {
      promise.resolve(token);
    }
  });
  failedQueue = [];
};

// Response interceptor - Handle token refresh on 401
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<HttpErrorResponse>) => {
    const originalRequest = error.config;

    // Skip refresh for these endpoints (auth endpoints and join which uses preliminary token)
    const skipRefreshEndpoints = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/select-organisation', '/org/join'];
    const isSkipEndpoint = skipRefreshEndpoints.some(
      (endpoint) => originalRequest?.url?.includes(endpoint)
    );

    if (error.response?.status === 401 && !isSkipEndpoint && originalRequest) {
      if (isRefreshing) {
        // Queue this request to retry after refresh
        return new Promise((resolve, reject) => {
          failedQueue.push({
            resolve: (token: string) => {
              if (originalRequest.headers) {
                originalRequest.headers.Authorization = `Bearer ${token}`;
              }
              resolve(apiClient(originalRequest));
            },
            reject: (err: unknown) => {
              reject(err);
            },
          });
        });
      }

      isRefreshing = true;
      const refreshToken = getRefreshToken();

      if (!refreshToken) {
        isRefreshing = false;
        clearTokens();
        window.location.href = '/login';
        return Promise.reject(error);
      }

      try {
        const response = await axios.post<Token>(`${API_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        });

        const newTokens = response.data;
        setTokens(newTokens);

        processQueue(null, newTokens.access_token);
        isRefreshing = false;

        // Retry original request with new token
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${newTokens.access_token}`;
        }
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        isRefreshing = false;
        clearTokens();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;
