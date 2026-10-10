/**
 * src/api/centres.ts  —  Centre API functions
 * Maps to backend  GET /v1/centres, /v1/centres/{id}, /v1/centres/{id}/risk
 */

import { apiClient } from './client';
import type { Centre } from '@/types';

// ─── List ──────────────────────────────────────────────────────────────────────

export interface ListCentresParams {
  state_code?: string;
  limit?: number;
  offset?: number;
}

export interface ListCentresResponse {
  items: Centre[];
  limit: number;
  offset: number;
}

export async function listCentres(params: ListCentresParams = {}): Promise<ListCentresResponse> {
  const { data } = await apiClient.get<ListCentresResponse>('/v1/centres', { params });
  return {
    ...data,
    items: (data.items || []).map(item => ({
      ...item,
      centre_code: item.code || item.centre_code || item.name,
      code: item.code || item.centre_code || item.name,
    })),
  };
}

// ─── Detail ────────────────────────────────────────────────────────────────────

export interface CentreZone {
  id: string;
  zone_code: string;
  zone_type: string;
  coverage_factor: number;
}

export interface CentreDetail extends Centre {
  zones: CentreZone[];
}

export async function getCentre(centreId: string): Promise<CentreDetail> {
  const { data } = await apiClient.get<CentreDetail>(`/v1/centres/${centreId}`);
  return {
    ...data,
    centre_code: data.code || data.centre_code || data.name,
    code: data.code || data.centre_code || data.name,
  };
}

// ─── Risk ──────────────────────────────────────────────────────────────────────

export interface CentreRisk {
  centre_id: string;
  risk_score: number;
  risk_tier: 'HIGH' | 'MEDIUM' | 'LOW';
  explanation: string;
  red_sessions: number;
  amber_sessions: number;
  ghost_batch_flags: number;
  total_sessions: number;
}

export async function getCentreRisk(centreId: string): Promise<CentreRisk> {
  const { data } = await apiClient.get<CentreRisk>(`/v1/centres/${centreId}/risk`);
  return data;
}
