/**
 * src/api/cameras.ts — Camera integrity API functions
 * Maps to backend:
 *   GET  /v1/cameras
 *   GET  /v1/cameras/{id}
 *   GET  /v1/cameras/{id}/observations
 *   POST /v1/cameras/{id}/rebaseline
 */

import { apiClient } from './client';
import type { Camera, CameraViewState } from '@/types';

export interface ListCamerasParams {
  centre_id?: string;
  view_state?: CameraViewState;
  limit?: number;
  offset?: number;
}

export interface ListCamerasResponse {
  items: Camera[];
  total: number;
  limit: number;
  offset: number;
}

export interface CameraObservationItem {
  timestamp: string;
  similarity_score?: number | null;
  state?: string;
  flag_triggered?: boolean;
}

export interface CameraObservationsResponse {
  camera_id: string;
  observations: CameraObservationItem[];
}

export interface RebaselineCameraPayload {
  new_phash?: string;
  keypoints_json?: Record<string, unknown>;
  lighting_tag?: string;
  reason?: string;
}

export interface RebaselineCameraResponse {
  camera_id: string;
  new_version: number;
  state: string;
  rebaselined_at: string;
  message: string;
}

export async function listCameras(params: ListCamerasParams = {}): Promise<ListCamerasResponse> {
  const { data } = await apiClient.get<ListCamerasResponse>('/v1/cameras', { params });
  return data;
}

export async function getCamera(cameraId: string): Promise<Camera> {
  const { data } = await apiClient.get<Camera>(`/v1/cameras/${cameraId}`);
  return data;
}

export async function getCameraObservations(cameraId: string, limit = 30): Promise<CameraObservationItem[]> {
  const { data } = await apiClient.get<CameraObservationItem[]>(`/v1/cameras/${cameraId}/observations`, {
    params: { limit },
  });
  return data;
}

export async function rebaselineCamera(
  cameraId: string,
  payload: RebaselineCameraPayload = {},
): Promise<RebaselineCameraResponse> {
  const { data } = await apiClient.post<RebaselineCameraResponse>(`/v1/cameras/${cameraId}/rebaseline`, payload);
  return data;
}

export async function uploadCameraReference(
  cameraId: string,
  payload: { lighting_tag?: string; reason?: string; image_base64?: string },
): Promise<any> {
  const { data } = await apiClient.post(`/v1/cameras/${cameraId}/references`, payload);
  return data;
}

export async function listCameraReferences(cameraId: string): Promise<any[]> {
  const { data } = await apiClient.get<any[]>(`/v1/cameras/${cameraId}/references`);
  return data;
}

export async function listRebaselineRequests(statusFilter?: string): Promise<any[]> {
  const { data } = await apiClient.get<any[]>('/v1/cameras/rebaseline-requests/list', {
    params: statusFilter ? { status_filter: statusFilter } : {},
  });
  return data;
}

export async function approveRebaselineRequest(requestId: string, role = 'inspector'): Promise<any> {
  const { data } = await apiClient.post(`/v1/cameras/rebaseline-requests/${requestId}/approve`, { role });
  return data;
}

export async function rejectRebaselineRequest(requestId: string, reason: string): Promise<any> {
  const { data } = await apiClient.post(`/v1/cameras/rebaseline-requests/${requestId}/reject`, { reason });
  return data;
}

export async function createMaintenanceWindow(
  cameraId: string,
  payload: { starts_at: string; ends_at: string; reason: string },
): Promise<any> {
  const { data } = await apiClient.post(`/v1/cameras/${cameraId}/maintenance-windows`, payload);
  return data;
}

export async function listMaintenanceWindows(cameraId: string): Promise<any[]> {
  const { data } = await apiClient.get<any[]>(`/v1/cameras/${cameraId}/maintenance-windows`);
  return data;
}

export async function challengeCamera(cameraId: string): Promise<any> {
  const { data } = await apiClient.post(`/v1/cameras/${cameraId}/challenge`);
  return data;
}

export async function reevaluateCamera(cameraId: string): Promise<any> {
  const { data } = await apiClient.post(`/v1/cameras/re-evaluate/${cameraId}`);
  return data;
}
