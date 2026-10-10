/**
 * src/api/cases.ts  —  Case management API functions
 * Maps to  GET/POST /v1/cases, GET /v1/cases/{id},
 *          POST /v1/cases/{id}/events, POST /v1/cases/{id}/respond
 */

import { apiClient } from './client';
import type { Case } from '@/types';

// ─── List ──────────────────────────────────────────────────────────────────────

export interface ListCasesParams {
  centre_id?: string;
  status?: string;
  priority?: string;
  limit?: number;
  offset?: number;
}

export interface ListCasesResponse {
  items: Case[];
  limit: number;
  offset: number;
}

export async function listCases(params: ListCasesParams = {}): Promise<ListCasesResponse> {
  const { data } = await apiClient.get<ListCasesResponse>('/v1/cases', { params });
  return data;
}

// ─── Detail ────────────────────────────────────────────────────────────────────

export async function getCase(caseId: string): Promise<Case> {
  const { data } = await apiClient.get<Case>(`/v1/cases/${caseId}`);
  return data;
}

// ─── Create ───────────────────────────────────────────────────────────────────

export interface CreateCaseBody {
  centre_id: string;
  title: string;
  description?: string;
  priority?: 'HIGH' | 'MEDIUM' | 'LOW';
  flag_ids?: string[];
}

export interface CreateCaseResponse {
  id: string;
  case_number: string;
  status: string;
}

export async function createCase(body: CreateCaseBody): Promise<CreateCaseResponse> {
  const { data } = await apiClient.post<CreateCaseResponse>('/v1/cases', body);
  return data;
}

// ─── Event transition ─────────────────────────────────────────────────────────

export interface AddCaseEventBody {
  to_status: string;
  note?: string;
}

export async function addCaseEvent(
  caseId: string,
  body: AddCaseEventBody,
): Promise<{ status: string; from_status: string; to_status: string }> {
  const { data } = await apiClient.post(`/v1/cases/${caseId}/events`, body);
  return data;
}

// ─── TC response ──────────────────────────────────────────────────────────────

export interface SubmitResponseBody {
  response_text: string;
  attachment_s3_keys?: string[];
}

export async function submitTcResponse(
  caseId: string,
  body: SubmitResponseBody,
): Promise<{ status: string; response_id: string }> {
  const { data } = await apiClient.post(`/v1/cases/${caseId}/respond`, body);
  return data;
}
