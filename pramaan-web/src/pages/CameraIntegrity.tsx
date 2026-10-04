import React, { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { AlertTriangle, CheckCircle, Clock, Eye, RotateCcw } from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine,
  ResponsiveContainer, CartesianGrid,
} from 'recharts';
import { MOCK_CAMERAS, MOCK_CAMERA_BASELINES, MOCK_CAMERA_VIEW_EVENTS } from '@/api/mockData';
import { StatusChip } from '@/components/status/StatusChip';

/* â”€â”€ Similarity timeline tooltip â”€â”€ */
function SimTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="pramaan-tooltip">
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.7rem' }}>{label}</p>
      <p><span style={{ color: 'var(--accent)' }}>Similarity: </span><span className="font-mono">{payload[0]?.value?.toFixed(3)}</span></p>
      {payload[0]?.payload?.state && (
        <p><span style={{ color: 'var(--text-secondary)' }}>State: </span>{payload[0].payload.state}</p>
      )}
    </div>
  );
}

/* â”€â”€ Camera list table â”€â”€ */
function CameraTable({ onSelect }: { onSelect: (id: string) => void }) {
  return (
    <div className="neu-card overflow-hidden">
      <div className="px-4 py-3" style={{ borderBottom: 'var(--edge)' }}>
        <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>All cameras</h2>
      </div>
      <div className="neu-well overflow-x-auto" style={{ borderRadius: 0, border: 'none', boxShadow: 'none' }}>
        <table className="pramaan-table pramaan-table-clickable min-w-[700px]" role="grid" aria-label="Camera list">
          <thead>
            <tr>
              {['Camera', 'Zone', 'Centre', 'View state', 'Similarity', 'Anchors', 'Baseline', 'Last seen'].map(h => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {MOCK_CAMERAS.map(cam => {
              const stateChip = cam.view_state;
              const isCritical = ['SUSPECTED_SWAP', 'SWAP_CONFIRMED', 'VIEW_MISMATCH'].includes(cam.view_state);
              return (
                <tr
                  key={cam.id}
                  onClick={() => onSelect(cam.id)}
                  style={{
                    cursor: 'pointer',
                    background: isCritical ? 'rgba(255,122,217,0.04)' : undefined,
                  }}
                >
                  <td>
                    <p className="font-medium text-sm" style={{ color: isCritical ? 'var(--st-swap)' : 'var(--text-primary)' }}>
                      {cam.label}
                    </p>
                    <p className="text-[10px] font-mono" style={{ color: 'var(--text-disabled)' }}>{cam.id}</p>
                  </td>
                  <td style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>{cam.zone_id}</td>
                  <td style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>{cam.centre_id}</td>
                  <td><StatusChip status={stateChip} size="xs" /></td>
                  <td>
                    {cam.last_similarity != null
                      ? <span className="font-mono text-sm" style={{
                          color: cam.last_similarity < 0.35 ? 'var(--st-red)'
                               : cam.last_similarity < 0.75 ? 'var(--st-amber)'
                               : 'var(--st-green)',
                        }}>{cam.last_similarity.toFixed(3)}</span>
                      : <span style={{ color: 'var(--text-disabled)' }}>â€”</span>}
                  </td>
                  <td>
                    <span className="font-mono text-xs">
                      {cam.anchors_found}/{cam.anchors_total}
                    </span>
                  </td>
                  <td><span className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>v{cam.current_baseline_ver}</span></td>
                  <td>
                    <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                      {new Date(cam.last_seen).toLocaleString('en-IN', { hour12: false, hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* â”€â”€ Camera Detail â”€â”€ */
function CameraDetail({ cameraId }: { cameraId: string }) {
  const cam = MOCK_CAMERAS.find(c => c.id === cameraId);
  if (!cam) return null;

  const events = MOCK_CAMERA_VIEW_EVENTS.filter(e => e.camera_id === cameraId);
  const baselines = MOCK_CAMERA_BASELINES.filter(b => b.camera_id === cameraId);
  const isSwap = ['SUSPECTED_SWAP', 'SWAP_CONFIRMED', 'VIEW_MISMATCH'].includes(cam.view_state);

  const timelineData = events.map(e => ({
    ts: new Date(e.ts).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false }),
    sim: e.similarity,
    state: e.state,
    anchors: e.anchors_found,
  }));

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header */}
      <div className="neu-card p-4">
        <div className="flex items-start justify-between flex-wrap gap-2">
          <div>
            <p className="font-bold text-base" style={{ color: 'var(--text-primary)' }}>{cam.label}</p>
            <p className="text-xs font-mono mt-0.5" style={{ color: 'var(--text-disabled)' }}>{cam.id} Â· {cam.zone_id}</p>
          </div>
          <StatusChip status={cam.view_state} />
        </div>

        {isSwap && (
          <div className="neu-alert-red mt-3">
            <AlertTriangle size={14} style={{ color: 'var(--st-red)', flexShrink: 0 }} />
            <div>
              <p className="text-xs font-semibold" style={{ color: 'var(--st-red)' }}>
                Evidence compromised â€” counts excluded from reconciliation
              </p>
              <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
                Sessions using this camera show NO-DATA (evidence compromised), not low-occupancy RED.
                A separate integrity flag has been raised.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Similarity score + gauge */}
      <div className="grid grid-cols-2 gap-4">
        <div className="neu-card p-4">
          <p className="section-header">Current similarity</p>
          <p
            className="kpi-value"
            style={{
              color: cam.last_similarity == null ? 'var(--text-disabled)'
                   : cam.last_similarity < 0.35 ? 'var(--st-red)'
                   : cam.last_similarity < 0.75 ? 'var(--st-amber)'
                   : 'var(--st-green)',
            }}
          >
            {cam.last_similarity?.toFixed(3) ?? 'â€”'}
          </p>
          <div className="flex gap-3 mt-3 text-xs" style={{ color: 'var(--text-disabled)' }}>
            <span style={{ color: 'var(--st-green)' }}>â‰¥ 0.75 SAME</span>
            <span style={{ color: 'var(--st-amber)' }}>0.35â€“0.75 DRIFT</span>
            <span style={{ color: 'var(--st-red)' }}>&lt; 0.35 MISMATCH</span>
          </div>
          <p className="text-xs mt-1" style={{ color: 'var(--text-disabled)' }}>
            Initial hypothesis â€” calibrate on pilot
          </p>
        </div>
        <div className="neu-card p-4">
          <p className="section-header">Anchor match</p>
          <p className="kpi-value">{cam.anchors_found}<span className="text-base font-normal" style={{ color: 'var(--text-disabled)' }}>/{cam.anchors_total}</span></p>
          <p className="text-xs mt-2" style={{ color: 'var(--text-secondary)' }}>
            registered anchors found in current view
          </p>
          {cam.anchors_found < cam.anchors_total / 2 && (
            <p className="text-xs mt-1" style={{ color: 'var(--st-amber)' }}>
              &lt; 50% anchors found â€” view may have changed
            </p>
          )}
        </div>
      </div>

      {/* Similarity timeline */}
      {timelineData.length > 0 && (
        <div className="neu-card p-4">
          <p className="section-header">Similarity timeline</p>
          <div className="neu-well-sm p-3" style={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={timelineData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="ts" tick={{ fontSize: 10 }} />
                <YAxis domain={[0, 1]} tick={{ fontSize: 10 }} />
                <Tooltip content={<SimTooltip />} />
                <ReferenceLine y={0.75} stroke="var(--st-green)" strokeDasharray="4 4" label={{ value: 'SAME 0.75', fill: 'var(--st-green)', fontSize: 10 }} />
                <ReferenceLine y={0.35} stroke="var(--st-red)" strokeDasharray="4 4" label={{ value: 'MISMATCH 0.35', fill: 'var(--st-red)', fontSize: 10 }} />
                <Line
                  type="monotone"
                  dataKey="sim"
                  stroke="var(--accent)"
                  strokeWidth={2}
                  dot={(p: any) => {
                    const s = p.payload.state;
                    const c = s === 'SUSPECTED_SWAP' || s === 'VIEW_MISMATCH' ? 'var(--st-red)'
                            : s === 'VIEW_DRIFTED' ? 'var(--st-amber)' : 'var(--st-green)';
                    return <circle key={p.cx} cx={p.cx} cy={p.cy} r={4} fill={c} stroke="var(--bg-raised)" strokeWidth={1.5} />;
                  }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Explanation card */}
      {cam.view_state !== 'SAME_VIEW' && (
        <div className="rule-card">
          <p className="text-xs font-semibold mb-1" style={{ color: 'var(--accent)' }}>Explanation</p>
          {cam.view_state === 'SUSPECTED_SWAP' && (
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Scene similarity fell from 0.83 to 0.19 at 10:42 and stayed below 0.35 for 15 minutes.
              {' '}{cam.anchors_total - cam.anchors_found} of {cam.anchors_total} registered anchors not found.
              No feed-health fault detected. Counts from this camera were excluded from reconciliation.
              A VIEW_MISMATCH persisting â‰¥ 3 consecutive 5-minute windows triggered SUSPECTED_SWAP status.
            </p>
          )}
          {cam.view_state === 'VIEW_MISMATCH' && (
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Scene similarity fell below 0.35. {cam.anchors_total - cam.anchors_found} anchors missing.
              Monitoring for persistence before raising SUSPECTED_SWAP.
            </p>
          )}
          {cam.view_state === 'VIEW_DRIFTED' && (
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Anchors match but a small position shift detected. Within normal range â€” no swap suspected.
              Monitor for further drift.
            </p>
          )}
        </div>
      )}

      {/* Baseline history */}
      <div className="neu-card p-4">
        <p className="section-header">Baseline history</p>
        <div className="space-y-2">
          {baselines.map(b => (
            <div
              key={b.id}
              className="flex items-center gap-3 p-2 rounded-[8px]"
              style={{
                background: b.status === 'ACTIVE' ? 'rgba(61,220,151,0.06)' : 'transparent',
                border: b.status === 'ACTIVE' ? '1px solid rgba(61,220,151,0.2)' : '1px solid transparent',
              }}
            >
              <div className="w-8 h-8 rounded-[8px] flex items-center justify-center shrink-0 font-mono font-bold text-sm"
                style={{ background: 'rgba(111,140,255,0.12)', color: 'var(--accent)' }}>
                v{b.version}
              </div>
              <div className="flex-1">
                <p className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>
                  {b.status === 'ACTIVE' ? 'âœ“ Active' : 'Superseded'}
                  {' '}Â· {b.lighting_tag}
                </p>
                <p className="text-[10px] font-mono" style={{ color: 'var(--text-disabled)' }}>
                  {new Date(b.captured_at).toLocaleDateString('en-IN')} Â· {b.captured_by}
                  {b.approved_by ? ` Â· approved by ${b.approved_by}` : ''}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Actions */}
      <div className="neu-card p-4 space-y-2">
        <p className="section-header">Actions</p>
        <button className="neu-btn w-full neu-btn-sm">Request inspection</button>
        <button className="neu-btn w-full neu-btn-sm">
          <RotateCcw size={13} /> Request re-baseline
        </button>
        <button className="neu-btn w-full neu-btn-sm">
          <Eye size={13} /> Mark reviewed (add note)
        </button>
        <button className="neu-btn w-full neu-btn-sm neu-btn-danger">Escalate</button>
      </div>
    </div>
  );
}

/* â”€â”€ Page â”€â”€ */
export function CameraIntegrityPage() {
  const { cameraId: paramId } = useParams<{ cameraId?: string }>();
  const [selectedId, setSelectedId] = useState<string | null>(paramId ?? null);

  const suspicious = MOCK_CAMERAS.filter(c =>
    ['SUSPECTED_SWAP', 'SWAP_CONFIRMED', 'VIEW_MISMATCH'].includes(c.view_state)
  );

  return (
    <div className="page-root">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Camera Integrity
          </h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            Scene similarity monitoring Â· Swap detection Â· Baseline management
          </p>
        </div>
        <span className="simulated-badge">SIMULATED DATA</span>
      </div>

      {/* Alert banner for swaps */}
      {suspicious.length > 0 && (
        <div className="neu-alert-red animate-pulse-alert">
          <AlertTriangle size={16} style={{ color: 'var(--st-red)', flexShrink: 0, marginTop: 2 }} />
          <div>
            <p className="text-sm font-semibold" style={{ color: 'var(--st-red)' }}>
              {suspicious.length} camera(s) with integrity concern â€” counts excluded from reconciliation
            </p>
            <div className="flex gap-2 flex-wrap mt-1">
              {suspicious.map(c => (
                <button
                  key={c.id}
                  className="chip chip-swap cursor-pointer hover:opacity-80"
                  onClick={() => setSelectedId(c.id)}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Total cameras',    value: MOCK_CAMERAS.length,                                                color: 'var(--text-primary)' },
          { label: 'Same view',        value: MOCK_CAMERAS.filter(c => c.view_state === 'SAME_VIEW').length,      color: 'var(--st-green)' },
          { label: 'Suspected swap',   value: MOCK_CAMERAS.filter(c => c.view_state === 'SUSPECTED_SWAP').length, color: 'var(--st-swap)' },
          { label: 'View mismatch',    value: MOCK_CAMERAS.filter(c => c.view_state === 'VIEW_MISMATCH').length,  color: 'var(--st-red)' },
        ].map(kpi => (
          <div key={kpi.label} className="neu-card p-4">
            <p className="kpi-label">{kpi.label}</p>
            <p className="kpi-value mt-1" style={{ color: kpi.color }}>{kpi.value}</p>
          </div>
        ))}
      </div>

      {/* Main: camera table + detail */}
      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
        <div className="xl:col-span-2">
          <CameraTable onSelect={(id) => setSelectedId(id === selectedId ? null : id)} />
        </div>
        <div className="xl:col-span-3">
          {selectedId
            ? <CameraDetail cameraId={selectedId} />
            : (
              <div className="neu-well p-8 text-center">
                <p style={{ color: 'var(--text-disabled)' }}>Select a camera to view similarity timeline, compare slider and baseline history.</p>
              </div>
            )}
        </div>
      </div>

      {/* Principle note */}
      <div className="neu-alert-info">
        <CheckCircle size={14} style={{ color: 'var(--accent)', flexShrink: 0, marginTop: 2 }} />
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          <strong style={{ color: 'var(--text-primary)' }}>UNCERTAIN never raises a swap.</strong>
          {' '}Feed faults, occlusion and too-dark frames mark the window UNCERTAIN and are excluded from the persistence count.
          An approved or pending re-baseline shows REBASELINE_PENDING, not a swap flag.
          Thresholds are initial hypotheses â€” calibrate on pilot.
        </p>
      </div>
    </div>
  );
}

