import axios, { type AxiosError, type AxiosResponse } from 'axios';
import axiosRetry from 'axios-retry';
import { v4 as uuidv4 } from 'uuid';

// Environment-based API configuration
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const API_TIMEOUT = Number(import.meta.env.VITE_API_TIMEOUT) || 10000;

// Create axios instance with base configuration
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Configure retry logic for transient errors
axiosRetry(apiClient, {
  retries: 3,
  retryCondition: (error: AxiosError) => {
    // Retry on network errors or specific HTTP status codes
    return (
      axiosRetry.isNetworkOrIdempotentRequestError(error) ||
      [502, 503, 504].includes(error.response?.status ?? 0)
    );
  },
  retryDelay: axiosRetry.exponentialDelay,
  onRetry: (retryCount, error) => {
    console.warn(`[API] Retry attempt ${retryCount} for ${error.config?.url}`);
  },
});

// Request interceptor for adding auth tokens and request ID
apiClient.interceptors.request.use(
  (config) => {
    // Add unique request ID for correlation
    config.headers['X-Request-ID'] = uuidv4();

    // Add auth token if available
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Handle unauthorized access
      localStorage.removeItem('auth_token');
      // Redirect to login if needed
    }

    // Log errors with correlation ID
    const requestId = error.config?.headers?.['X-Request-ID'];
    console.error(`[API Error] Request ID: ${requestId}`, {
      url: error.config?.url,
      status: error.response?.status,
      message: error.message,
    });

    return Promise.reject(error);
  }
);

/**
 * API Error type for normalized error handling
 */
export interface ApiError {
  message: string;
  code: string;
  status?: number;
  requestId?: string;
  isTimeout: boolean;
  isNetworkError: boolean;
  canRetry: boolean;
}

/**
 * Normalizes axios errors into user-friendly error objects
 */
export function normalizeError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError;
    const status = axiosError.response?.status;
    const requestId = axiosError.config?.headers?.['X-Request-ID'] as string | undefined;
    const isTimeout = axiosError.code === 'ECONNABORTED';
    const isNetworkError = !axiosError.response && !isTimeout;

    // Determine if the error is retryable
    const canRetry = isNetworkError || isTimeout || [502, 503, 504].includes(status ?? 0);

    // Generate user-friendly message based on error type
    let message: string;
    let code: string;

    if (isTimeout) {
      message = 'The request took too long. Please try again.';
      code = 'TIMEOUT';
    } else if (isNetworkError) {
      message = 'Unable to connect to the server. Please check your connection.';
      code = 'NETWORK_ERROR';
    } else {
      switch (status) {
        case 400:
          message = 'Invalid request. Please check your input.';
          code = 'BAD_REQUEST';
          break;
        case 401:
          message = 'Authentication required. Please log in.';
          code = 'UNAUTHORIZED';
          break;
        case 403:
          message = 'You do not have permission to perform this action.';
          code = 'FORBIDDEN';
          break;
        case 404:
          message = 'The requested resource was not found.';
          code = 'NOT_FOUND';
          break;
        case 500:
          message = 'An internal server error occurred. Please try again later.';
          code = 'SERVER_ERROR';
          break;
        case 502:
        case 503:
        case 504:
          message = 'The server is temporarily unavailable. Please try again.';
          code = 'SERVICE_UNAVAILABLE';
          break;
        default:
          message = 'An unexpected error occurred. Please try again.';
          code = 'UNKNOWN_ERROR';
      }
    }

    return {
      message,
      code,
      status,
      requestId,
      isTimeout,
      isNetworkError,
      canRetry,
    };
  }

  // Handle non-axios errors
  return {
    message: 'An unexpected error occurred. Please try again.',
    code: 'UNKNOWN_ERROR',
    isTimeout: false,
    isNetworkError: false,
    canRetry: false,
  };
}

/**
 * Health check response type
 */
export interface HealthResponse {
  status: string;
  version: string;
}

/**
 * Fetch backend health status
 */
export async function fetchHealth(): Promise<HealthResponse> {
  const response = await apiClient.get<HealthResponse>('/health');
  return response.data;
}

export default apiClient;
