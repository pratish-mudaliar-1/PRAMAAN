import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  AlertTriangle, CheckCircle, RotateCcw, RefreshCw,
  ShieldAlert, Calendar, UploadCloud, Radio
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine,
  ResponsiveContainer, CartesianGrid,
} from 'recharts';
import { useCameras, useCamera, useCameraObservations, useRebaselineCamera } from '@/hooks/useCameras';
import {
  listCameraReferences,
  uploadCameraReference,
  createMaintenanceWindow,
  listMaintenanceWindows,
  challengeCamera,
} from '@/api/cameras';
import { StatusChip } from '@/components/status/StatusChip';
import { CompareSlider } from '@/components/evidence/CompareSlider';
import type { Camera } from '@/types';

/* ── Similarity timeline tooltip ── */
function SimTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="pramaan-tooltip">
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.7rem' }}>{label}</p>
      <p>
        <span style={{ color: 'var(--accent)' }}>Similarity / समानता: </span>
        <span className="font-mono">{payload[0]?.value != null ? payload[0]?.value?.toFixed(3) : '—'}</span>
      </p>
      {payload[0]?.payload?.state && (
        <p>
          <span style={{ color: 'var(--text-secondary)' }}>Classification: </span>
          {payload[0].payload.state}
        </p>
      )}
    </div>
  );
}

/* ── Camera list table ── */
function CameraTable({
  cameras,
  selectedId,
  onSelect,
}: {
  cameras: Camera[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="neu-card overflow-hidden">
      <div className="px-4 py-3" style={{ borderBottom: 'var(--edge)' }}>
        <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
          All Cameras / सभी कैमरे ({cameras.length})
        </h2>
      </div>
      <div className="neu-well overflow-x-auto" style={{ borderRadius: 0, border: 'none', boxShadow: 'none' }}>
        <table className="pramaan-table pramaan-table-clickable min-w-[650px]" role="grid" aria-label="Camera list">
          <thead>
            <tr>
              {['Camera / कैमरा', 'Zone / क्षेत्र', 'State / स्थिति', 'Similarity / समानता', 'Status'].map(h => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cameras.map(cam => {
              const stateChip = (cam as any).current_state || cam.view_state || 'STABLE';
              const isCritical = ['SWAP_CONFIRMED', 'SWAP_SUSPECTED', 'MOVED_CONFIRMED'].includes(stateChip);
              const isSelected = cam.id === selectedId;
              const sim = (cam as any).confidence ?? cam.last_similarity;
              const label = (cam as any).camera_code || (cam as any).label || cam.id.slice(0, 10);

              return (
                <tr
                  key={cam.id}
                  onClick={() => onSelect(cam.id)}
                  style={{
                    cursor: 'pointer',
                    background: isSelected
                      ? 'rgba(111,140,255,0.08)'
                      : isCritical
                      ? 'rgba(255,122,217,0.04)'
                      : undefined,
                  }}
                >
                  <td>
                    <p className="font-medium text-sm" style={{ color: isCritical ? 'var(--st-swap)' : 'var(--text-primary)' }}>
                      {label}
                    </p>
                    <p className="text-[10px] font-mono" style={{ color: 'var(--text-disabled)' }}>
                      {(cam as any).location_description || cam.id.slice(0, 12)}
                    </p>
                  </td>
                  <td style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                    {(cam as any).zone_code || cam.zone_id?.slice(0, 8) || '—'}
                  </td>
                  <td><StatusChip status={stateChip} size="xs" /></td>
                  <td>
                    {sim != null ? (
                      <span
                        className="font-mono text-sm"
                        style={{
                          color:
                            sim < 0.35
                              ? 'var(--st-red)'
                              : sim < 0.75
                              ? 'var(--st-amber)'
                              : 'var(--st-green)',
                        }}
                      >
                        {sim.toFixed(3)}
                      </span>
                    ) : (
                      <span style={{ color: 'var(--text-disabled)' }}>—</span>
                    )}
                  </td>
                  <td>
                    <span className="text-xs" style={{ color: cam.is_active ? 'var(--st-green)' : 'var(--text-disabled)' }}>
                      {cam.is_active ? 'Active' : 'Disabled'}
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

/* ── Camera Detail ── */
function CameraDetail({ cameraId }: { cameraId: string }) {
  const { data: cam, isPending } = useCamera(cameraId);
  const { data: obsData } = useCameraObservations(cameraId, 40);
  const rebaselineMutation = useRebaselineCamera();

  const [feedbackMsg, setFeedbackMsg] = useState<{ text: string; type: 'success' | 'error' | 'info' } | null>(null);
  const [challengeResult, setChallengeResult] = useState<any | null>(null);
  const [references, setReferences] = useState<any[]>([]);
  const [maintWindows, setMaintWindows] = useState<any[]>([]);
  const [showMaintModal, setShowMaintModal] = useState(false);
  const [maintReason, setMaintReason] = useState('Routine lens maintenance & cleaning');
  const [rebaselineReason, setRebaselineReason] = useState('Authorized classroom relocation');
  const [showUploadModal, setShowUploadModal] = useState(false);

  // Load references and maintenance windows
  useEffect(() => {
    if (!cameraId) return;
    listCameraReferences(cameraId)
      .then(setReferences)
      .catch(() => setReferences([]));
    listMaintenanceWindows(cameraId)
      .then(setMaintWindows)
      .catch(() => setMaintWindows([]));
  }, [cameraId]);

  const showFeedback = (text: string, type: 'success' | 'error' | 'info' = 'success') => {
    setFeedbackMsg({ text, type });
    setTimeout(() => setFeedbackMsg(null), 6000);
  };

  if (isPending || !cam) {
    return (
      <div className="neu-well p-8 text-center">
        <RefreshCw size={16} className="animate-spin inline-block mr-2 text-disabled" />
        <span style={{ color: 'var(--text-secondary)' }}>Loading camera telemetry…</span>
      </div>
    );
  }

  const rawState = (cam as any).current_state || cam.view_state || 'STABLE';
  const isSwap = ['SWAP_CONFIRMED', 'SWAP_SUSPECTED', 'MOVED_CONFIRMED', 'SUSPECTED_SWAP'].includes(rawState);
  const isConfirmedTamper = ['SWAP_CONFIRMED', 'MOVED_CONFIRMED'].includes(rawState);
  const sim = (cam as any).confidence ?? cam.last_similarity;
  const label = (cam as any).camera_code || (cam as any).label || cam.id.slice(0, 10);
  const firstSuspected = (cam as any).first_suspected_at || (cam as any).since;

  const observations = Array.isArray(obsData) ? obsData : (obsData as any)?.observations ?? [];
  const timelineData = observations.map((o: any) => ({
    ts: new Date(o.timestamp || o.ts).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false }),
    sim: o.similarity_score ?? o.fused_similarity ?? 0.85,
    state: o.state || o.classification || 'STABLE',
  }));

  const handleChallenge = async () => {
    try {
      const res = await challengeCamera(cameraId);
      setChallengeResult(res);
      showFeedback(`Challenge complete: status ${res.status}. Similarity: ${res.latest_similarity?.toFixed(3) || '1.0'}`, 'info');
    } catch (e: any) {
      showFeedback(`Challenge failed: ${e?.message || 'Error'}`, 'error');
    }
  };

  const handleScheduleMaint = async () => {
    try {
      const now = new Date();
      const endsAt = new Date(now.getTime() + 2 * 60 * 60 * 1000); // 2 hours
      const mw = await createMaintenanceWindow(cameraId, {
        starts_at: now.toISOString(),
        ends_at: endsAt.toISOString(),
        reason: maintReason,
      });
      setMaintWindows(prev => [mw, ...prev]);
      setShowMaintModal(false);
      showFeedback('Maintenance window scheduled successfully (2 hours). Evidence alerts suppressed.', 'success');
    } catch (e: any) {
      showFeedback(`Failed to schedule maintenance window: ${e?.message || 'Error'}`, 'error');
    }
  };

  const handleUploadNewReference = async () => {
    try {
      const res = await uploadCameraReference(cameraId, {
        reason: rebaselineReason,
        lighting_tag: 'day',
      });
      setShowUploadModal(false);
      showFeedback(`Reference uploaded! Rebaseline Request #${res.rebaseline_request_id.slice(0, 8)} pending inspector approval.`, 'success');
      listCameraReferences(cameraId).then(setReferences);
    } catch (e: any) {
      showFeedback(`Failed to submit reference: ${e?.message || 'Error'}`, 'error');
    }
  };

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header */}
      <div className="neu-card p-4">
        <div className="flex items-start justify-between flex-wrap gap-2">
          <div>
            <div className="flex items-center gap-2">
              <p className="font-bold text-base" style={{ color: 'var(--text-primary)' }}>{label}</p>
              <span className="text-[11px] px-2 py-0.5 rounded-full" style={{ background: 'rgba(111,140,255,0.12)', color: 'var(--accent)' }}>
                Lead for Human Review / मानवीय समीक्षा
              </span>
            </div>
            <p className="text-xs font-mono mt-0.5" style={{ color: 'var(--text-disabled)' }}>
              ID: {cam.id} · Zone: {(cam as any).zone_code || cam.zone_id || '—'} · Centre: {(cam as any).centre_name || '—'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <StatusChip status={rawState} />
            <button
              className="neu-btn neu-btn-sm"
              onClick={handleChallenge}
              title="Issue random server challenge frame verification"
            >
              <Radio size={12} className="inline mr-1 text-accent" />
              Challenge / सत्यापन
            </button>
          </div>
        </div>

        {feedbackMsg && (
          <div className={`mt-3 ${feedbackMsg.type === 'error' ? 'neu-alert-red' : feedbackMsg.type === 'info' ? 'neu-alert-info' : 'neu-alert-info'}`}>
            <CheckCircle size={14} style={{ color: 'var(--accent)', flexShrink: 0 }} />
            <p className="text-xs font-semibold" style={{ color: 'var(--accent)' }}>{feedbackMsg.text}</p>
          </div>
        )}

        {/* Untrusted Since Banner with Change-Point */}
        {isConfirmedTamper && (
          <div className="neu-alert-red mt-3 p-3 rounded-lg border border-red-500/30">
            <div className="flex items-start gap-2">
              <ShieldAlert size={18} style={{ color: 'var(--st-red)', flexShrink: 0, marginTop: 2 }} />
              <div>
                <p className="text-xs font-bold uppercase tracking-wide" style={{ color: 'var(--st-red)' }}>
                  UNTRUSTED SINCE / अप्रामाणिक तिथि: {firstSuspected ? new Date(firstSuspected).toLocaleString('en-IN') : 'Confirmed'}
                </p>
                <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
                  Camera entered <strong style={{ color: 'var(--st-red)' }}>{rawState}</strong>.
                  All attendance observations from this change-point forward are marked <code>UNTRUSTED</code> and
                  treated as <strong>NO_DATA</strong> in reconciliation.
                  A formal tampering case with evidence pack has been generated. No student attendance penalties applied.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Visual Reference vs Current Redacted View (CompareSlider) */}
      <div className="neu-card p-4">
        <div className="flex items-center justify-between mb-2">
          <div>
            <p className="section-header">Reference Baseline vs Current Redacted View</p>
            <p className="text-xs" style={{ color: 'var(--text-disabled)' }}>
              मानदंड दृश्य बनाम वर्तमान धुंधला दृश्य · Faces redacted at edge
            </p>
          </div>
          <div className="flex gap-2 text-[11px]" style={{ color: 'var(--text-secondary)' }}>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full" style={{ background: 'var(--st-green)' }}></span>
              Baseline (v{(references[0]?.version) || 1})
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full" style={{ background: isSwap ? 'var(--st-red)' : 'var(--accent)' }}></span>
              Query Keyframe
            </span>
          </div>
        </div>

        <div className="w-full rounded-[10px] overflow-hidden border border-white/10" style={{ height: 260 }}>
          <CompareSlider
            beforeLabel="Registered Baseline (v1)"
            afterLabel="Current Redacted Stream"
            anchors={[
              { x: 25, y: 35, found: !isSwap, label: 'Workbench A' },
              { x: 55, y: 45, found: !isSwap, label: 'Whiteboard' },
              { x: 75, y: 30, found: !isSwap, label: 'Notice Board' },
            ]}
          />
        </div>
      </div>

      {/* KPIs & Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="neu-card p-3">
          <p className="section-header">Current similarity</p>
          <p
            className="kpi-value text-xl mt-1 font-mono"
            style={{
              color:
                sim == null
                  ? 'var(--text-disabled)'
                  : sim < 0.35
                  ? 'var(--st-red)'
                  : sim < 0.75
                  ? 'var(--st-amber)'
                  : 'var(--st-green)',
            }}
          >
            {sim != null ? sim.toFixed(3) : '—'}
          </p>
          <p className="text-[10px] mt-1" style={{ color: 'var(--text-disabled)' }}>Threshold: ≥ 0.75 STABLE</p>
        </div>

        <div className="neu-card p-3">
          <p className="section-header">Consecutive Suspicious</p>
          <p className="kpi-value text-xl mt-1 font-mono">
            {(cam as any).consecutive_suspicious ?? 0}
            <span className="text-xs font-normal" style={{ color: 'var(--text-disabled)' }}> / 3</span>
          </p>
          <p className="text-[10px] mt-1" style={{ color: 'var(--text-disabled)' }}>K-of-M persistence window</p>
        </div>

        <div className="neu-card p-3">
          <p className="section-header">Active References</p>
          <p className="kpi-value text-xl mt-1 font-mono">{references.length || 1}</p>
          <p className="text-[10px] mt-1" style={{ color: 'var(--text-disabled)' }}>Lighting views: day/night</p>
        </div>

        <div className="neu-card p-3">
          <p className="section-header">Maintenance Windows</p>
          <p className="kpi-value text-xl mt-1 font-mono">{maintWindows.length}</p>
          <p className="text-[10px] mt-1" style={{ color: 'var(--text-disabled)' }}>Alerts suppressed</p>
        </div>
      </div>

      {/* Similarity timeline */}
      {timelineData.length > 0 && (
        <div className="neu-card p-4">
          <p className="section-header">Similarity Timeline ({timelineData.length} observations)</p>
          <div className="neu-well-sm p-3 mt-2" style={{ height: 180 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={timelineData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="ts" tick={{ fontSize: 10 }} />
                <YAxis domain={[0, 1]} tick={{ fontSize: 10 }} />
                <Tooltip content={<SimTooltip />} />
                <ReferenceLine y={0.75} stroke="var(--st-green)" strokeDasharray="4 4" label={{ value: 'STABLE 0.75', fill: 'var(--st-green)', fontSize: 9 }} />
                <ReferenceLine y={0.35} stroke="var(--st-red)" strokeDasharray="4 4" label={{ value: 'SWAP 0.35', fill: 'var(--st-red)', fontSize: 9 }} />
                <Line
                  type="monotone"
                  dataKey="sim"
                  stroke="var(--accent)"
                  strokeWidth={2}
                  dot={(p: any) => {
                    const s = p.payload.state;
                    const c = ['SWAP_CONFIRMED', 'SWAP_SUSPECTED', 'MOVED_CONFIRMED'].includes(s)
                      ? 'var(--st-red)'
                      : ['DRIFT_SUSPECTED', 'OCCLUDED'].includes(s)
                      ? 'var(--st-amber)'
                      : 'var(--st-green)';
                    return <circle key={p.cx} cx={p.cx} cy={p.cy} r={3.5} fill={c} stroke="var(--bg-raised)" strokeWidth={1} />;
                  }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Actions & Workflows */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Rebaseline Approval Workflow */}
        <div className="neu-card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="section-header">Baseline Management & Approval</p>
            <span className="text-[10px] font-mono" style={{ color: 'var(--text-disabled)' }}>Two-Person Rule</span>
          </div>
          <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
            Submit a new reference keyframe when cameras are legitimately relocated.
            Requires Inspector and State Officer approvals.
          </p>

          <div className="flex gap-2">
            <button
              className="neu-btn neu-btn-sm flex-1"
              onClick={() => setShowUploadModal(true)}
            >
              <UploadCloud size={13} className="inline mr-1" />
              Upload Reference (पुनर्आधार)
            </button>
            <button
              className="neu-btn neu-btn-sm"
              onClick={async () => {
                try {
                  await rebaselineMutation.mutateAsync({
                    cameraId,
                    payload: { reason: 'Direct supervisor rebaseline override' },
                  });
                  showFeedback('Camera rebaselined to STABLE.', 'success');
                } catch (e: any) {
                  showFeedback(`Rebaseline failed: ${e?.message || 'Error'}`, 'error');
                }
              }}
              disabled={rebaselineMutation.isPending}
            >
              <RotateCcw size={12} className={rebaselineMutation.isPending ? 'animate-spin inline mr-1' : 'inline mr-1'} />
              Override
            </button>
          </div>

          {/* Reference list */}
          <div className="mt-2 space-y-1">
            <p className="text-[11px] font-semibold" style={{ color: 'var(--text-primary)' }}>Registered Views:</p>
            {references.slice(0, 3).map(r => (
              <div key={r.id} className="flex items-center justify-between text-xs p-1.5 rounded bg-black/20 font-mono">
                <span>v{r.version} ({r.lighting_tag})</span>
                <span className={r.active ? 'text-green-400 font-bold' : 'text-gray-400'}>
                  {r.active ? 'ACTIVE' : 'INACTIVE'}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Maintenance Windows */}
        <div className="neu-card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="section-header">Maintenance Windows (रखरखाव)</p>
            <button
              className="neu-btn neu-btn-sm"
              onClick={() => setShowMaintModal(true)}
            >
              <Calendar size={12} className="inline mr-1" />
              Schedule Window
            </button>
          </div>
          <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
            Active windows suppress alerts during planned maintenance without deleting audit evidence.
          </p>

          <div className="space-y-1 mt-2">
            {maintWindows.length === 0 ? (
              <p className="text-xs" style={{ color: 'var(--text-disabled)' }}>No maintenance windows scheduled.</p>
            ) : (
              maintWindows.slice(0, 3).map(m => (
                <div key={m.id} className="text-xs p-2 rounded bg-black/20">
                  <p className="font-semibold text-[11px]" style={{ color: 'var(--text-primary)' }}>{m.reason}</p>
                  <p className="text-[10px] font-mono mt-0.5" style={{ color: 'var(--text-disabled)' }}>
                    {new Date(m.starts_at).toLocaleDateString()} · {new Date(m.starts_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} - {new Date(m.ends_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Upload Reference Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="neu-card p-5 max-w-md w-full space-y-3 animate-scale-in">
            <h3 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>Upload New Reference Baseline</h3>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Submits a keyframe for ORB & pHash feature extraction and initiates two-person approval.
            </p>
            <div>
              <label className="text-xs block mb-1">Reason for Rebaseline / कारण</label>
              <input
                className="neu-input w-full text-xs"
                value={rebaselineReason}
                onChange={e => setRebaselineReason(e.target.value)}
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button className="neu-btn neu-btn-sm" onClick={() => setShowUploadModal(false)}>Cancel</button>
              <button className="neu-btn neu-btn-sm neu-btn-primary" onClick={handleUploadNewReference}>
                Submit Request
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Maintenance Modal */}
      {showMaintModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="neu-card p-5 max-w-md w-full space-y-3 animate-scale-in">
            <h3 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>Schedule Maintenance Window</h3>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Alerts for this camera will be suppressed during the next 2 hours. Evidence remains recorded.
            </p>
            <div>
              <label className="text-xs block mb-1">Reason / कारण</label>
              <input
                className="neu-input w-full text-xs"
                value={maintReason}
                onChange={e => setMaintReason(e.target.value)}
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button className="neu-btn neu-btn-sm" onClick={() => setShowMaintModal(false)}>Cancel</button>
              <button className="neu-btn neu-btn-sm neu-btn-primary" onClick={handleScheduleMaint}>
                Confirm Window
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Page ── */
export function CameraIntegrityPage() {
  const { cameraId: paramId } = useParams<{ cameraId?: string }>();
  const [selectedId, setSelectedId] = useState<string | null>(paramId ?? null);

  const { data, isPending, isError } = useCameras({ limit: 100 });
  const cameras = data?.items ?? [];

  const suspicious = cameras.filter(c => {
    const st = (c as any).current_state || c.view_state;
    return ['SWAP_CONFIRMED', 'SWAP_SUSPECTED', 'MOVED_CONFIRMED'].includes(st);
  });

  return (
    <div className="page-root">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Camera Integrity / कैमरा अखंडता
          </h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            Scene similarity monitoring · Swap detection · Baseline management · Lead for human review
          </p>
        </div>
      </div>

      {/* Alert banner for confirmed swaps */}
      {suspicious.length > 0 && (
        <div className="neu-alert-red animate-pulse-alert">
          <AlertTriangle size={16} style={{ color: 'var(--st-red)', flexShrink: 0, marginTop: 2 }} />
          <div>
            <p className="text-sm font-semibold" style={{ color: 'var(--st-red)' }}>
              {suspicious.length} camera(s) with confirmed swap or tamper — observations marked UNTRUSTED
            </p>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
              Affected sessions treated as NO_DATA to prevent false attendance penalties. Investigation cases generated.
            </p>
            <div className="flex gap-2 flex-wrap mt-2">
              {suspicious.map(c => (
                <button
                  key={c.id}
                  className="chip chip-swap cursor-pointer hover:opacity-80"
                  onClick={() => setSelectedId(c.id)}
                >
                  {(c as any).camera_code || (c as any).label || c.id.slice(0, 10)}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Total cameras / कुल',       value: cameras.length,                                                                                       color: 'var(--text-primary)' },
          { label: 'Stable view / स्थिर',        value: cameras.filter(c => ((c as any).current_state || c.view_state) === 'STABLE').length,                  color: 'var(--st-green)' },
          { label: 'Suspected swap / संदिग्ध',  value: suspicious.length,                                                                                     color: 'var(--st-swap)' },
          { label: 'Drift suspected / विचलन',   value: cameras.filter(c => ((c as any).current_state || c.view_state) === 'DRIFT_SUSPECTED').length,        color: 'var(--st-amber)' },
        ].map(kpi => (
          <div key={kpi.label} className="neu-card p-4">
            <p className="kpi-label">{kpi.label}</p>
            <p className="kpi-value mt-1" style={{ color: kpi.color }}>
              {isPending ? '…' : kpi.value}
            </p>
          </div>
        ))}
      </div>

      {/* Main: camera table + detail */}
      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
        <div className="xl:col-span-2">
          {isPending ? (
            <div className="neu-card p-8 text-center">
              <RefreshCw size={16} className="animate-spin inline-block mr-2 text-disabled" />
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>Loading cameras…</p>
            </div>
          ) : isError || !cameras.length ? (
            <div className="neu-card p-8 text-center">
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>No registered cameras found.</p>
            </div>
          ) : (
            <CameraTable
              cameras={cameras}
              selectedId={selectedId}
              onSelect={(id) => setSelectedId(id === selectedId ? null : id)}
            />
          )}
        </div>
        <div className="xl:col-span-3">
          {selectedId ? (
            <CameraDetail cameraId={selectedId} />
          ) : (
            <div className="neu-well p-8 text-center">
              <p style={{ color: 'var(--text-disabled)' }}>
                Select a camera to view similarity timeline, visual baseline slider, change-point history, and maintenance windows.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Principle note */}
      <div className="neu-alert-info">
        <CheckCircle size={14} style={{ color: 'var(--accent)', flexShrink: 0, marginTop: 2 }} />
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          <strong style={{ color: 'var(--text-primary)' }}>Privacy and Fairness Guarantee:</strong>
          {' '}Server never receives un-redacted frames. Redacted areas are masked from ORB, SSIM, and histogram computation.
          Observations from untrusted cameras are treated as NO_DATA — never as low-occupancy attendance penalties.
        </p>
      </div>
    </div>
  );
}
