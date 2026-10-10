/**
 * src/hooks/useSessions.ts
 * React Query hooks for sessions.
 */

import { useQuery } from '@tanstack/react-query';
import { listSessions, getSession, type ListSessionsParams } from '@/api/sessions';

export const sessionKeys = {
  all: ['sessions'] as const,
  list: (params: ListSessionsParams) => ['sessions', 'list', params] as const,
  detail: (id: string) => ['sessions', 'detail', id] as const,
};

export function useSessions(params: ListSessionsParams = {}) {
  return useQuery({
    queryKey: sessionKeys.list(params),
    queryFn: () => listSessions(params),
    staleTime: 30_000,
  });
}

export function useSession(sessionId: string | undefined) {
  return useQuery({
    queryKey: sessionKeys.detail(sessionId ?? ''),
    queryFn: () => getSession(sessionId!),
    enabled: !!sessionId,
  });
}
