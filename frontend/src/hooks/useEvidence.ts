/**
 * src/hooks/useEvidence.ts
 * React Query hooks for evidence items and viewing URLs.
 */

import { useQuery } from '@tanstack/react-query';
import { listEvidence, getEvidenceView, type ListEvidenceParams } from '@/api/evidence';

export const evidenceKeys = {
  all: ['evidence'] as const,
  list: (params: ListEvidenceParams) => ['evidence', 'list', params] as const,
  view: (id: string) => ['evidence', 'view', id] as const,
};

export function useEvidence(params: ListEvidenceParams = {}) {
  return useQuery({
    queryKey: evidenceKeys.list(params),
    queryFn: () => listEvidence(params),
    staleTime: 30_000,
  });
}

export function useEvidenceView(evidenceId: string | undefined) {
  return useQuery({
    queryKey: evidenceKeys.view(evidenceId ?? ''),
    queryFn: () => getEvidenceView(evidenceId!),
    enabled: !!evidenceId,
    staleTime: 60_000,
  });
}
