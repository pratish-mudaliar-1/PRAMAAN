/**
 * src/api/audit.ts — Audit trail API functions
 * Maps to backend:
 *   GET /v1/audit-log
 */

import { apiClient } from './client';
import type { AuditEvent } from '@/types';

export interface ListAuditParams {
  actor?: string;
  action?: string;
  resource_type?: string;
  limit?: number;
  offset?: number;
}

export interface ListAuditResponse {
  items: AuditEvent[];
  total: number;
  limit: number;
  offset: number;
}

export async function listAuditLogs(params: ListAuditParams = {}): Promise<ListAuditResponse> {
  const { data } = await apiClient.get<ListAuditResponse>('/v1/audit-log', { params });
  return data;
}
