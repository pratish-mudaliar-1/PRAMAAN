/**
 * src/api/devices.ts — Device management API functions
 * Maps to backend:
 *   GET  /v1/devices
 *   POST /v1/devices/{id}/status
 */

import { apiClient } from './client';

export interface DeviceItem {
  id: string;
  serial_number: string;
  centre_id: string;
  centre_name?: string | null;
  zone_id?: string | null;
  status: 'PENDING' | 'ACTIVE' | 'OFFLINE' | 'SUSPENDED' | 'REVOKED';
  is_active: boolean;
  last_seen_at?: string | null;
  last_heartbeat_at?: string | null;
  firmware_version?: string | null;
  model_version?: string | null;
  queue_depth?: number | null;
  cpu_percent?: number | null;
  temperature_celsius?: number | null;
  free_disk_mb?: number | null;
  health_status: 'HEALTHY' | 'DEGRADED' | 'CRITICAL' | 'OFFLINE';
}

export interface ListDevicesParams {
  centre_id?: string;
  status?: string;
  limit?: number;
  offset?: number;
}

export interface ListDevicesResponse {
  items: DeviceItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface UpdateDeviceStatusPayload {
  status: 'PENDING' | 'ACTIVE' | 'OFFLINE' | 'SUSPENDED' | 'REVOKED';
  reason?: string;
}

export interface UpdateDeviceStatusResponse {
  device_id: string;
  previous_status: string;
  new_status: string;
  updated_at: string;
}

export async function listDevices(params: ListDevicesParams = {}): Promise<ListDevicesResponse> {
  const { data } = await apiClient.get<ListDevicesResponse>('/v1/devices', { params });
  return data;
}

export async function updateDeviceStatus(
  deviceId: string,
  payload: UpdateDeviceStatusPayload,
): Promise<UpdateDeviceStatusResponse> {
  const { data } = await apiClient.post<UpdateDeviceStatusResponse>(`/v1/devices/${deviceId}/status`, payload);
  return data;
}
