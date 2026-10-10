/**
 * src/api/evidence.ts — Evidence API functions
 * Maps to backend:
 *   GET /v1/evidence
 *   GET /v1/evidence/{id}/view
 */

import { apiClient } from './client';

export interface EvidenceItem {
  id: string;
  device_id: string;
  zone_id?: string | null;
  session_id?: string | null;
  flag_id?: string | null;
  s3_key: string;
  content_type: string;
  size_bytes: number;
  captured_at: string;
  is_near_duplicate: boolean;
  duplicate_of_id?: string | null;
  legal_hold: boolean;
}

export interface ListEvidenceParams {
  session_id?: string;
  centre_id?: string;
  limit?: number;
  offset?: number;
}

export interface ListEvidenceResponse {
  items: EvidenceItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface EvidenceViewResponse {
  evidence_id: string;
  view_url: string;
  expires_in_seconds: number;
  content_type: string;
  captured_at: string;
}

export async function listEvidence(params: ListEvidenceParams = {}): Promise<ListEvidenceResponse> {
  const { data } = await apiClient.get<ListEvidenceResponse>('/v1/evidence', { params });
  return data;
}

export async function getEvidenceView(evidenceId: string): Promise<EvidenceViewResponse> {
  const { data } = await apiClient.get<EvidenceViewResponse>(`/v1/evidence/${evidenceId}/view`);
  return data;
}
