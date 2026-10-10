/**
 * src/api/flags.ts  —  Flag API functions
 * Maps to  GET /v1/flags, GET /v1/flags/{id}, POST /v1/flags/{id}/resolve
 */

import { apiClient } from './client';
import type { Flag } from '@/types';

// ─── List ──────────────────────────────────────────────────────────────────────

export interface ListFlagsParams {
  centre_id?: string;
  severity?: 'HIGH' | 'MEDIUM' | 'LOW';
  flag_type?: string;
  status?: string;
  limit?: number;
  offset?: number;
}

export interface ListFlagsResponse {
  items: Flag[];
  limit: number;
  offset: number;
}

export async function listFlags(params: ListFlagsParams = {}): Promise<ListFlagsResponse> {
  const { data } = await apiClient.get<ListFlagsResponse>('/v1/flags', { params });
  return data;
}

// ─── Detail ────────────────────────────────────────────────────────────────────

export async function getFlag(flagId: string): Promise<Flag> {
  const { data } = await apiClient.get<Flag>(`/v1/flags/${flagId}`);
  return data;
}

// ─── Resolve ──────────────────────────────────────────────────────────────────

export interface ResolveFlagBody {
  resolution_reason: string;
  status: 'CLOSED_CONFIRMED' | 'CLOSED_DISMISSED';
}

export interface ResolveFlagResponse {
  status: string;
  flag_id: string;
  new_status: string;
}

export async function resolveFlag(flagId: string, body: ResolveFlagBody): Promise<ResolveFlagResponse> {
  const { data } = await apiClient.post<ResolveFlagResponse>(`/v1/flags/${flagId}/resolve`, body);
  return data;
}
