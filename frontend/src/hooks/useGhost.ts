/**
 * src/hooks/useGhost.ts
 * React Query hooks for ghost batch assessments and batches.
 */

import { useQuery } from '@tanstack/react-query';
import {
  listGhostAssessments,
  getGhostAssessment,
  listBatches,
  type ListGhostParams,
  type ListBatchesParams,
} from '@/api/ghost';

export const ghostKeys = {
  all: ['ghost'] as const,
  assessments: (params: ListGhostParams) => ['ghost', 'assessments', params] as const,
  assessment: (id: string) => ['ghost', 'assessment', id] as const,
  batches: (params: ListBatchesParams) => ['ghost', 'batches', params] as const,
};

export function useGhostAssessments(params: ListGhostParams = {}) {
  return useQuery({
    queryKey: ghostKeys.assessments(params),
    queryFn: () => listGhostAssessments(params),
    staleTime: 30_000,
  });
}

export function useGhostAssessment(assessmentId: string | undefined) {
  return useQuery({
    queryKey: ghostKeys.assessment(assessmentId ?? ''),
    queryFn: () => getGhostAssessment(assessmentId!),
    enabled: !!assessmentId,
    staleTime: 30_000,
  });
}

export function useBatches(params: ListBatchesParams = {}) {
  return useQuery({
    queryKey: ghostKeys.batches(params),
    queryFn: () => listBatches(params),
    staleTime: 30_000,
  });
}
