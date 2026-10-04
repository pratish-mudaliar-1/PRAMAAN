import React, { useState } from 'react';
import { Wifi, WifiOff, RefreshCw, Activity, Database } from 'lucide-react';
import { MOCK_EDGE_DEVICES } from '@/api/mockData';
import { StatusChip } from '@/components/status/StatusChip';

function fmtBytes(b: number) {
  if (b === 0) return '0 B';
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(2)} MB`;
}

export function EdgeConsolePage() {
  const [devices, setDevices] = useState(MOCK_EDGE_DEVICES.map(d => ({ ...d })));

  const toggleDevice = (id: string) => {
    setDevices(prev => prev.map(d =>
      d.id === id
        ? { ...d, status: d.status === 'ONLINE' ? 'OFFLINE' : 'ONLINE' }
        : d
    ));
  };

  const streamEquivMbps = 2;          // Mbps per camera if streaming
  const pramaanBytesPerCamPerMin = 250;

  return (
    <div className="page-root">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>Edge &amp; Bandwidth Console</h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            Device heartbeat · Queue depth · Bandwidth comparison
          </p>
        </div>
        <span className="simulated-badge">SIMULATED DATA</span>
      </div>

      {/* Bandwidth comparison */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="neu-card p-4">
          <p className="kpi-label">PRAMAAN metadata</p>
          <p className="kpi-value mt-1" style={{ color: 'var(--st-green)' }}>~250 B</p>
          <p className="text-xs mt-1" style={{ color: 'var(--text-disabled)' }}>per camera · per minute · design estimate</p>
        </div>
        <div className="neu-card p-4">
          <p className="kpi-label">Streaming equivalent</p>
          <p className="kpi-value mt-1" style={{ color: 'var(--st-red)' }}>~2 Mbps</p>
          <p className="text-xs mt-1" style={{ color: 'var(--text-disabled)' }}>per camera · continuous stream · design estimate</p>
        </div>
        <div className="neu-card p-4">
          <p className="kpi-label">Bandwidth saving</p>
          <p className="kpi-value mt-1" style={{ color: 'var(--accent)' }}>~99.97%</p>
          <p className="text-xs mt-1" style={{ color: 'var(--text-disabled)' }}>
            {pramaanBytesPerCamPerMin * 8 / 1000} Kbps vs {streamEquivMbps * 1000} Kbps · design estimate · hypothesis
          </p>
        </div>
      </div>

      {/* Device table */}
      <div className="neu-card overflow-hidden">
        <div className="px-4 py-3" style={{ borderBottom: 'var(--edge)' }}>
          <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Edge devices</p>
        </div>
        <div className="neu-well overflow-x-auto" style={{ borderRadius: 0, border: 'none', boxShadow: 'none' }}>
          <table className="pramaan-table min-w-[700px]">
            <thead>
              <tr>
                {['Device', 'Centre', 'Status', 'Queue depth', 'Bytes sent today', 'Last heartbeat', 'Model', 'Control'].map(h => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {devices.map(d => {
                const minsAgo = Math.floor((Date.now() - new Date(d.last_heartbeat).getTime()) / 60_000);
                const isOffline = d.status === 'OFFLINE';
                return (
                  <tr key={d.id} style={isOffline ? { opacity: 0.7 } : {}}>
                    <td>
                      <p className="font-medium text-sm" style={{ color: 'var(--text-primary)' }}>{d.label}</p>
                      <p className="text-[10px] font-mono" style={{ color: 'var(--text-disabled)' }}>{d.id}</p>
                    </td>
                    <td style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>{d.centre_id}</td>
                    <td><StatusChip status={d.status} size="xs" /></td>
                    <td>
                      <span className="font-mono" style={{ color: d.queue_depth > 0 ? 'var(--st-amber)' : 'var(--text-secondary)' }}>
                        {d.queue_depth.toLocaleString('en-IN')}
                      </span>
                      {d.queue_depth > 1000 && (
                        <span className="ml-1 chip chip-amber" style={{ fontSize: '0.65rem', padding: '1px 4px' }}>backlog</span>
                      )}
                    </td>
                    <td>
                      <div>
                        <span className="font-mono text-sm">{fmtBytes(d.bytes_sent_today)}</span>
                        <div className="bandwidth-track mt-1" style={{ width: 80 }}>
                          <div
                            className="bandwidth-fill"
                            style={{ width: `${Math.min((d.bytes_sent_today / 500_000) * 100, 100)}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td>
                      <span
                        className="text-xs font-mono"
                        style={{ color: minsAgo > 60 ? 'var(--st-red)' : minsAgo > 10 ? 'var(--st-amber)' : 'var(--text-secondary)' }}
                      >
                        {minsAgo < 60 ? `${minsAgo}m ago` : minsAgo < 1440 ? `${Math.floor(minsAgo / 60)}h ago` : `${Math.floor(minsAgo / 1440)}d ago`}
                      </span>
                    </td>
                    <td><span className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>{d.model_version}</span></td>
                    <td>
                      <button
                        className={`neu-btn neu-btn-xs ${isOffline ? '' : 'neu-btn-danger'}`}
                        onClick={() => toggleDevice(d.id)}
                        title={isOffline ? 'Reconnect (demo)' : 'Disconnect (demo)'}
                      >
                        {isOffline
                          ? <><Wifi size={12} /> Reconnect</>
                          : <><WifiOff size={12} /> Disconnect</>}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Demo triggers */}
      <div className="neu-card p-4">
        <p className="section-header">Demo triggers</p>
        <p className="text-xs mb-3" style={{ color: 'var(--text-secondary)' }}>
          These simulate edge-device events for the demo. All actions are labelled SIMULATED.
        </p>
        <div className="flex gap-2 flex-wrap">
          {[
            { label: 'Cover camera', desc: 'Triggers feed-health alert' },
            { label: 'Replay old photo', desc: 'Triggers duplicate-evidence detection' },
            { label: 'Simulate camera swap', desc: 'Drops similarity → SUSPECTED_SWAP' },
            { label: 'Seed ghost batch', desc: 'Adds 12-day ghost pattern for CTR-D' },
          ].map(t => (
            <button key={t.label} className="neu-btn neu-btn-sm" title={t.desc}>
              <Activity size={12} /> {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Queue sync note */}
      <div className="neu-alert-info">
        <Database size={14} style={{ color: 'var(--accent)', flexShrink: 0, marginTop: 2 }} />
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          When an edge device goes offline, observations queue in IndexedDB on the edge node.
          On reconnect, the queue syncs in order. NO-DATA sessions are created for the gap —
          they never generate flags or ghost evidence.
        </p>
      </div>
    </div>
  );
}
