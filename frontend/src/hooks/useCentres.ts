/**
 * src/hooks/useCentres.ts
 * React Query hooks for centres.
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { listCentres, getCentre, getCentreRisk, type ListCentresParams } from '@/api/centres';

// ── Query key factory ──────────────────────────────────────────────────────

export const centreKeys = {
  all: ['centres'] as const,
  list: (params: ListCentresParams) => ['centres', 'list', params] as const,
  detail: (id: string) => ['centres', 'detail', id] as const,
  risk: (id: string) => ['centres', 'risk', id] as const,
};

// ── Hooks ──────────────────────────────────────────────────────────────────

export function useCentres(params: ListCentresParams = {}) {
  return useQuery({
    queryKey: centreKeys.list(params),
    queryFn: () => listCentres(params),
    staleTime: 30_000,
  });
}

export function useCentre(centreId: string | undefined) {
  return useQuery({
    queryKey: centreKeys.detail(centreId ?? ''),
    queryFn: () => getCentre(centreId!),
    enabled: !!centreId,
  });
}

export function useCentreRisk(centreId: string | undefined) {
  return useQuery({
    queryKey: centreKeys.risk(centreId ?? ''),
    queryFn: () => getCentreRisk(centreId!),
    enabled: !!centreId,
    staleTime: 60_000,
  });
}
