/**
 * src/hooks/useCases.ts
 * React Query hooks for cases.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listCases,
  getCase,
  createCase,
  addCaseEvent,
  submitTcResponse,
  type ListCasesParams,
  type CreateCaseBody,
  type AddCaseEventBody,
  type SubmitResponseBody,
} from '@/api/cases';

export const caseKeys = {
  all: ['cases'] as const,
  list: (params: ListCasesParams) => ['cases', 'list', params] as const,
  detail: (id: string) => ['cases', 'detail', id] as const,
};

export function useCases(params: ListCasesParams = {}) {
  return useQuery({
    queryKey: caseKeys.list(params),
    queryFn: () => listCases(params),
    staleTime: 20_000,
  });
}

export function useCase(caseId: string | undefined) {
  return useQuery({
    queryKey: caseKeys.detail(caseId ?? ''),
    queryFn: () => getCase(caseId!),
    enabled: !!caseId,
  });
}

export function useCreateCase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateCaseBody) => createCase(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: caseKeys.all });
    },
  });
}

export function useAddCaseEvent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ caseId, body }: { caseId: string; body: AddCaseEventBody }) =>
      addCaseEvent(caseId, body),
    onSuccess: (_data, { caseId }) => {
      qc.invalidateQueries({ queryKey: caseKeys.all });
      qc.invalidateQueries({ queryKey: caseKeys.detail(caseId) });
    },
  });
}

export function useSubmitTcResponse() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ caseId, body }: { caseId: string; body: SubmitResponseBody }) =>
      submitTcResponse(caseId, body),
    onSuccess: (_data, { caseId }) => {
      qc.invalidateQueries({ queryKey: caseKeys.detail(caseId) });
    },
  });
}
