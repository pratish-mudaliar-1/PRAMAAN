/**
 * src/api/ghost.ts — Ghost batch assessment API functions
 * Maps to backend:
 *   GET /v1/ghost-assessments
 *   GET /v1/ghost-assessments/{id}
 *   GET /v1/batches
 */

import { apiClient } from './client';
import type { GhostEvaluation, GhostStatus, Batch } from '@/types';

export interface ListGhostParams {
  centre_id?: string;
  state?: GhostStatus;
  limit?: number;
  offset?: number;
}

export interface ListGhostResponse {
  items: GhostEvaluation[];
  total: number;
  limit: number;
  offset: number;
}

export interface ListBatchesParams {
  centre_id?: string;
  ghost_state?: GhostStatus;
  limit?: number;
  offset?: number;
}

export interface ListBatchesResponse {
  items: Batch[];
  total: number;
  limit: number;
  offset: number;
}

export async function listGhostAssessments(params: ListGhostParams = {}): Promise<ListGhostResponse> {
  const { data } = await apiClient.get<ListGhostResponse>('/v1/ghost-assessments', { params });
  return data;
}

export async function getGhostAssessment(assessmentId: string): Promise<GhostEvaluation> {
  const { data } = await apiClient.get<GhostEvaluation>(`/v1/ghost-assessments/${assessmentId}`);
  return data;
}

export async function listBatches(params: ListBatchesParams = {}): Promise<ListBatchesResponse> {
  const { data } = await apiClient.get<ListBatchesResponse>('/v1/batches', { params });
  return data;
}

export async function getBatchGhostAssessment(batchId: string): Promise<GhostEvaluation> {
  const { data } = await apiClient.get<GhostEvaluation>(`/v1/batches/${batchId}/ghost-assessment`);
  return data;
}

export async function getCentreGhostRollup(centreId: string): Promise<any> {
  const { data } = await apiClient.get<any>(`/v1/centres/${centreId}/ghost-batches`);
  return data;
}

export async function reevaluateGhostBatch(batchId: string): Promise<any> {
  const { data } = await apiClient.post<any>(`/v1/ghost/re-evaluate/${batchId}`);
  return data;
}
