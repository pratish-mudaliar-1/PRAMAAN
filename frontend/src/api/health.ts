/**
 * src/api/health.ts  —  Health & readiness probe functions
 * Maps to  GET /v1/healthz, GET /v1/readyz
 */

import { apiClient } from './client';

export interface HealthResponse {
  status: string;
  service: string;
}

export interface ReadyzResponse {
  status: 'ready' | 'degraded';
  checks: Record<string, string>;
  uptime_seconds: number;
}

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await apiClient.get<HealthResponse>('/v1/healthz');
  return data;
}

export async function getReadiness(): Promise<ReadyzResponse> {
  const { data } = await apiClient.get<ReadyzResponse>('/v1/readyz');
  return data;
}
