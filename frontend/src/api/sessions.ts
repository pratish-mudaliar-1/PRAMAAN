/**
 * src/api/sessions.ts  —  Session API functions
 * Maps to  GET /v1/sessions, GET /v1/sessions/{id}
 */

import { apiClient } from './client';
import type { Session } from '@/types';

// ─── List ──────────────────────────────────────────────────────────────────────

export interface ListSessionsParams {
  centre_id?: string;
  batch_id?: string;
  status?: string;
  limit?: number;
  offset?: number;
}

export interface ListSessionsResponse {
  items: Session[];
  limit: number;
  offset: number;
}

export async function listSessions(params: ListSessionsParams = {}): Promise<ListSessionsResponse> {
  const { data } = await apiClient.get<ListSessionsResponse>('/v1/sessions', { params });
  return data;
}

// ─── Detail ────────────────────────────────────────────────────────────────────

export async function getSession(sessionId: string): Promise<Session> {
  const { data } = await apiClient.get<Session>(`/v1/sessions/${sessionId}`);
  return data;
}
