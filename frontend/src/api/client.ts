// Get the base API URL from environment variables, fallback to local default
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

/**
 * A tiny wrapper around native fetch that standardizes error handling.
 */
export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  
  const headers: Record<string, string> = {
    ...((options.body instanceof FormData) ? {} : { 'Content-Type': 'application/json' }),
    ...(options.headers as Record<string, string>),
  };

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = 'Unknown error occurred';
    try {
      const errorData = await response.json();
      errorDetail = errorData.detail || errorDetail;
    } catch {
      // Body wasn't valid JSON, fallback to status text
      errorDetail = response.statusText;
    }
    
    throw new Error(`API Error (${response.status}): ${errorDetail}`);
  }

  if (response.status === 204) {
    return null as T;
  }

  return response.json();
}
