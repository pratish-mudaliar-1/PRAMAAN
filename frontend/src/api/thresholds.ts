/**
 * src/api/thresholds.ts — Threshold management API functions
 * Maps to backend:
 *   GET /v1/thresholds
 *   PUT /v1/thresholds
 */

import { apiClient } from './client';

export interface ThresholdProfile {
  id: string;
  scheme_code?: string | null;
  state_code?: string | null;
  version: number;
  is_active: boolean;
  t_green: number;
  t_amber: number;
  repeat_n: number;
  min_feed_health_fraction: number;
  item_absent_min_windows: number;
  item_absent_min_days: number;
  phash_hamming_threshold: number;
  extra?: Record<string, unknown> | null;
  approved_by?: string | null;
  approved_at?: string | null;
  approval_note?: string | null;
}

export interface ThresholdUpdateRequest {
  t_green: number;
  t_amber: number;
  repeat_n: number;
  min_feed_health_fraction: number;
  item_absent_min_windows: number;
  item_absent_min_days: number;
  phash_hamming_threshold: number;
  approval_note?: string | null;
}

export async function getThresholds(): Promise<ThresholdProfile> {
  const { data } = await apiClient.get<ThresholdProfile>('/v1/thresholds');
  return data;
}

export async function updateThresholds(payload: ThresholdUpdateRequest): Promise<ThresholdProfile> {
  const { data } = await apiClient.put<ThresholdProfile>('/v1/thresholds', payload);
  return data;
}
