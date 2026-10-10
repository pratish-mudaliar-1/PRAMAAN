/**
 * src/hooks/useAudit.ts
 * React Query hooks for audit trail.
 */

import { useQuery } from '@tanstack/react-query';
import { listAuditLogs, type ListAuditParams } from '@/api/audit';

export const auditKeys = {
  all: ['audit'] as const,
  list: (params: ListAuditParams) => ['audit', 'list', params] as const,
};

export function useAuditLogs(params: ListAuditParams = {}) {
  return useQuery({
    queryKey: auditKeys.list(params),
    queryFn: () => listAuditLogs(params),
    staleTime: 15_000,
  });
}
