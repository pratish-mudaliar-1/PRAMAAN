/**
 * src/api/client.ts
 * Central axios instance.  All API modules import from here.
 *
 * Auth:  reads the JWT from localStorage (key = "pramaan_token").
 *        If the token is missing the request goes through without auth
 *        (the backend will return 401 which we surface as an ApiError).
 *
 * Proxy: Vite rewrites /api → http://localhost:8000
 *        so every relative URL here looks like /api/v1/...
 */

import axios, { type AxiosError } from 'axios';

// ── Token store (dev: localStorage; prod: swap to secure cookie) ───────────

export const TOKEN_KEY = 'pramaan_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// ── Axios instance ─────────────────────────────────────────────────────────

export const apiClient = axios.create({
  baseURL: '/api',          // Vite proxy → http://localhost:8000
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
});

// Attach bearer token on every request
apiClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Error normalisation ────────────────────────────────────────────────────

export interface ApiError {
  status: number;
  detail: string;
}

export function isApiError(e: unknown): e is ApiError {
  return typeof e === 'object' && e !== null && 'status' in e && 'detail' in e;
}

apiClient.interceptors.response.use(
  (r) => r,
  (err: AxiosError) => {
    const status = err.response?.status ?? 0;
    const data = err.response?.data as { detail?: string } | undefined;
    const detail =
      data?.detail ??
      err.message ??
      'Unknown error';
    return Promise.reject({ status, detail } satisfies ApiError);
  },
);
