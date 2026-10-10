/**
 * src/hooks/useThresholds.ts
 * React Query hooks for threshold profile.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getThresholds,
  updateThresholds,
  type ThresholdUpdateRequest,
} from '@/api/thresholds';

export const thresholdKeys = {
  active: ['thresholds', 'active'] as const,
};

export function useThresholds() {
  return useQuery({
    queryKey: thresholdKeys.active,
    queryFn: getThresholds,
    staleTime: 60_000,
  });
}

export function useUpdateThresholds() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ThresholdUpdateRequest) => updateThresholds(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['thresholds'] });
      queryClient.invalidateQueries({ queryKey: ['audit'] });
    },
  });
}
