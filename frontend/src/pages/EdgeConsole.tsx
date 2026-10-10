import React, { useState } from 'react';
import { Wifi, WifiOff, RefreshCw, Database, Server, CheckCircle } from 'lucide-react';
import { useDevices, useUpdateDeviceStatus } from '@/hooks/useDevices';
import { StatusChip } from '@/components/status/StatusChip';
import type { DeviceItem } from '@/api/devices';

function fmtBytes(b: number) {
  if (b === 0) return '0 B';
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(2)} MB`;
}

export function EdgeConsolePage() {
  const { data, isPending, isError } = useDevices({ limit: 50 });
  const updateStatusMutation = useUpdateDeviceStatus();
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);

  const devices = data?.items ?? [];

  const handleToggleStatus = async (device: DeviceItem) => {
    const nextStatus = device.status === 'ACTIVE' ? 'OFFLINE' : 'ACTIVE';
    try {
      await updateStatusMutation.mutateAsync({
        deviceId: device.id,
        payload: {
          status: nextStatus,
          reason: `Reviewer toggled status to ${nextStatus} via Edge Console`,
        },
      });
      setActionFeedback(`Device ${device.serial_number} updated to ${nextStatus}`);
      setTimeout(() => setActionFeedback(null), 4000);
    } catch (e: any) {
      setActionFeedback(`Status update failed: ${e?.detail || e?.message || 'Error'}`);
    }
  };

  const streamEquivMbps = 2; // Mbps per camera if continuous streaming
  const pramaanBytesPerCamPerMin = 250;

  return (
    <div className="page-root">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>Edge &amp; Bandwidth Console</h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            Device telemetry · Health monitoring · Cryptographic edge status
          </p>
        </div>
      </div>

      {actionFeedback && (
        <div className="neu-alert-info">
          <CheckCircle size={14} style={{ color: 'var(--accent)', flexShrink: 0 }} />
          <p className="text-xs font-semibold" style={{ color: 'var(--accent)' }}>{actionFeedback}</p>
        </div>
      )}

      {/* Bandwidth comparison */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="neu-card p-4">
          <p className="kpi-label">PRAMAAN metadata</p>
          <p className="kpi-value mt-1" style={{ color: 'var(--st-green)' }}>~250 B</p>
          <p className="text-xs mt-1" style={{ color: 'var(--text-disabled)' }}>per camera · per minute · signed observations</p>
        </div>
        <div className="neu-card p-4">
          <p className="kpi-label">Streaming equivalent</p>
          <p className="kpi-value mt-1" style={{ color: 'var(--st-red)' }}>~2 Mbps</p>
          <p className="text-xs mt-1" style={{ color: 'var(--text-disabled)' }}>per camera · continuous stream · high bandwidth</p>
        </div>
        <div className="neu-card p-4">
          <p className="kpi-label">Bandwidth saving</p>
          <p className="kpi-value mt-1" style={{ color: 'var(--accent)' }}>~99.97%</p>
          <p className="text-xs mt-1" style={{ color: 'var(--text-disabled)' }}>
            {pramaanBytesPerCamPerMin * 8 / 1000} Kbps vs {streamEquivMbps * 1000} Kbps edge architecture
          </p>
        </div>
      </div>

      {/* Device table */}
      <div className="neu-card overflow-hidden">
        <div className="px-4 py-3" style={{ borderBottom: 'var(--edge)' }}>
          <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Enrolled Edge Devices ({devices.length})
          </p>
        </div>
        <div className="neu-well overflow-x-auto" style={{ borderRadius: 0, border: 'none', boxShadow: 'none' }}>
          {isPending ? (
            <div className="p-8 text-center">
              <RefreshCw size={16} className="animate-spin inline-block mr-2 text-disabled" />
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Loading edge devices…</span>
            </div>
          ) : isError || !devices.length ? (
            <div className="p-8 text-center">
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>No enrolled devices found.</p>
            </div>
          ) : (
            <table className="pramaan-table min-w-[700px]">
              <thead>
                <tr>
                  {['Device / Serial', 'Centre', 'Status', 'Health', 'Queue Depth', 'CPU / Temp', 'Last Heartbeat', 'Firmware', 'Action'].map(h => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {devices.map(d => {
                  const minsAgo = d.last_heartbeat_at
                    ? Math.floor((Date.now() - new Date(d.last_heartbeat_at).getTime()) / 60_000)
                    : null;
                  const isOffline = d.status === 'OFFLINE';
                  const queueDepth = d.queue_depth ?? 0;

                  return (
                    <tr key={d.id} style={isOffline ? { opacity: 0.7 } : {}}>
                      <td>
                        <p className="font-medium text-sm font-mono" style={{ color: 'var(--text-primary)' }}>{d.serial_number}</p>
                        <p className="text-[10px] font-mono" style={{ color: 'var(--text-disabled)' }}>{d.id.slice(0, 12)}…</p>
                      </td>
                      <td style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                        {d.centre_name || d.centre_id.slice(0, 10)}
                      </td>
                      <td><StatusChip status={d.status} size="xs" /></td>
                      <td><StatusChip status={d.health_status} size="xs" /></td>
                      <td>
                        <span className="font-mono" style={{ color: queueDepth > 0 ? 'var(--st-amber)' : 'var(--text-secondary)' }}>
                          {queueDepth.toLocaleString('en-IN')}
                        </span>
                        {queueDepth > 1000 && (
                          <span className="ml-1 chip chip-amber" style={{ fontSize: '0.65rem', padding: '1px 4px' }}>backlog</span>
                        )}
                      </td>
                      <td>
                        <span className="font-mono text-xs">
                          {d.cpu_percent != null ? `${d.cpu_percent}%` : '—'} / {d.temperature_celsius != null ? `${d.temperature_celsius}°C` : '—'}
                        </span>
                      </td>
                      <td>
                        <span
                          className="text-xs font-mono"
                          style={{ color: minsAgo === null || minsAgo > 60 ? 'var(--st-red)' : minsAgo > 10 ? 'var(--st-amber)' : 'var(--text-secondary)' }}
                        >
                          {minsAgo === null ? '—' : minsAgo < 60 ? `${minsAgo}m ago` : `${Math.floor(minsAgo / 60)}h ago`}
                        </span>
                      </td>
                      <td>
                        <span className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>
                          {d.firmware_version ?? '1.0.0'}
                        </span>
                      </td>
                      <td>
                        <button
                          className={`neu-btn neu-btn-xs ${isOffline ? '' : 'neu-btn-danger'}`}
                          onClick={() => handleToggleStatus(d)}
                          disabled={updateStatusMutation.isPending}
                          title={isOffline ? 'Activate device' : 'Set device Offline'}
                        >
                          {isOffline ? (
                            <><Wifi size={12} /> Activate</>
                          ) : (
                            <><WifiOff size={12} /> Disconnect</>
                          )}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Queue sync note */}
      <div className="neu-alert-info">
        <Database size={14} style={{ color: 'var(--accent)', flexShrink: 0, marginTop: 2 }} />
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          When an edge device loses connectivity, observations queue on the device and sync with sequential hash-chain verification upon reconnection.
          Every status transition triggers an immutable audit log entry.
        </p>
      </div>
    </div>
  );
}
