/**
 * src/hooks/useCameras.ts
 * React Query hooks for cameras and camera integrity.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listCameras,
  getCamera,
  getCameraObservations,
  rebaselineCamera,
  type ListCamerasParams,
  type RebaselineCameraPayload,
} from '@/api/cameras';

export const cameraKeys = {
  all: ['cameras'] as const,
  list: (params: ListCamerasParams) => ['cameras', 'list', params] as const,
  detail: (id: string) => ['cameras', 'detail', id] as const,
  observations: (id: string, limit?: number) => ['cameras', 'observations', id, limit] as const,
};

export function useCameras(params: ListCamerasParams = {}) {
  return useQuery({
    queryKey: cameraKeys.list(params),
    queryFn: () => listCameras(params),
    staleTime: 30_000,
  });
}

export function useCamera(cameraId: string | undefined) {
  return useQuery({
    queryKey: cameraKeys.detail(cameraId ?? ''),
    queryFn: () => getCamera(cameraId!),
    enabled: !!cameraId,
    staleTime: 30_000,
  });
}

export function useCameraObservations(cameraId: string | undefined, limit = 30) {
  return useQuery({
    queryKey: cameraKeys.observations(cameraId ?? '', limit),
    queryFn: () => getCameraObservations(cameraId!, limit),
    enabled: !!cameraId,
    staleTime: 30_000,
  });
}

export function useRebaselineCamera() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ cameraId, payload }: { cameraId: string; payload?: RebaselineCameraPayload }) =>
      rebaselineCamera(cameraId, payload),
    onSuccess: (_, { cameraId }) => {
      queryClient.invalidateQueries({ queryKey: cameraKeys.all });
      queryClient.invalidateQueries({ queryKey: cameraKeys.detail(cameraId) });
      queryClient.invalidateQueries({ queryKey: ['audit'] });
    },
  });
}
