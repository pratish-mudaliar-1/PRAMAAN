/**
 * src/hooks/useFlags.ts
 * React Query hooks for flags.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listFlags,
  getFlag,
  resolveFlag,
  type ListFlagsParams,
  type ResolveFlagBody,
} from '@/api/flags';

export const flagKeys = {
  all: ['flags'] as const,
  list: (params: ListFlagsParams) => ['flags', 'list', params] as const,
  detail: (id: string) => ['flags', 'detail', id] as const,
};

export function useFlags(params: ListFlagsParams = {}) {
  return useQuery({
    queryKey: flagKeys.list(params),
    queryFn: () => listFlags(params),
    staleTime: 20_000,
  });
}

export function useFlag(flagId: string | undefined) {
  return useQuery({
    queryKey: flagKeys.detail(flagId ?? ''),
    queryFn: () => getFlag(flagId!),
    enabled: !!flagId,
  });
}

export function useResolveFlag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ flagId, body }: { flagId: string; body: ResolveFlagBody }) =>
      resolveFlag(flagId, body),
    onSuccess: (_data, { flagId }) => {
      // Invalidate list and this specific detail
      qc.invalidateQueries({ queryKey: flagKeys.all });
      qc.invalidateQueries({ queryKey: flagKeys.detail(flagId) });
    },
  });
}
