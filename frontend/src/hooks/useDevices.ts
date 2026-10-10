/**
 * src/hooks/useDevices.ts
 * React Query hooks for edge devices.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listDevices,
  updateDeviceStatus,
  type ListDevicesParams,
  type UpdateDeviceStatusPayload,
} from '@/api/devices';

export const deviceKeys = {
  all: ['devices'] as const,
  list: (params: ListDevicesParams) => ['devices', 'list', params] as const,
};

export function useDevices(params: ListDevicesParams = {}) {
  return useQuery({
    queryKey: deviceKeys.list(params),
    queryFn: () => listDevices(params),
    staleTime: 30_000,
  });
}

export function useUpdateDeviceStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ deviceId, payload }: { deviceId: string; payload: UpdateDeviceStatusPayload }) =>
      updateDeviceStatus(deviceId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: deviceKeys.all });
      queryClient.invalidateQueries({ queryKey: ['audit'] });
    },
  });
}
