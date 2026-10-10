import React, { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  MapPin,
  Clock,
  AlertTriangle,
  RefreshCw,
  Camera as CameraIcon,
  Server,
  Ghost,
  FileText,
  Briefcase,
  ExternalLink,
} from 'lucide-react';
import { useCentre, useCentreRisk } from '@/hooks/useCentres';
import { useFlags } from '@/hooks/useFlags';
import { useSessions } from '@/hooks/useSessions';
import { useCameras } from '@/hooks/useCameras';
import { useGhostAssessments } from '@/hooks/useGhost';
import { useDevices } from '@/hooks/useDevices';
import { useEvidence, useEvidenceView } from '@/hooks/useEvidence';
import { useCases } from '@/hooks/useCases';
import { StatusChip } from '@/components/status/StatusChip';
import type { Flag } from '@/types';

export function CentreDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [tab, setTab] = useState('sessions');

  const { data: centre, isPending, isError } = useCentre(id);
  const { data: risk } = useCentreRisk(id);
  const { data: flagsData } = useFlags({ centre_id: id, limit: 200 });

  if (isPending) {
    return (
      <div className="page-root">
        <div className="neu-card p-8 flex items-center justify-center gap-3">
          <RefreshCw size={16} className="animate-spin" style={{ color: 'var(--text-disabled)' }} />
          <p style={{ color: 'var(--text-secondary)' }}>Loading centre data…</p>
        </div>
      </div>
    );
  }

  if (isError || !centre) {
    return (
      <div className="page-root">
        <div className="neu-card p-8 text-center">
          <p style={{ color: 'var(--text-secondary)' }}>Centre not found: {id}</p>
          <Link to="/centres" className="neu-btn mt-4 inline-flex">← Back to centres</Link>
        </div>
      </div>
    );
  }

  const centreFlags = flagsData?.items ?? [];
  const hb = centre.last_heartbeat ? new Date(centre.last_heartbeat) : null;
  const minsAgo = hb ? Math.floor((Date.now() - hb.getTime()) / 60_000) : null;

  const tabs = [
    { id: 'sessions',    label: 'Sessions',        icon: Clock },
    { id: 'infra',       label: 'Edge Devices',    icon: Server },
    { id: 'camera',      label: 'Camera Integrity',icon: CameraIcon },
    { id: 'ghost',       label: 'Ghost Batches',   icon: Ghost },
    { id: 'evidence',    label: 'Evidence',        icon: FileText },
    { id: 'cases',       label: 'Cases',           icon: Briefcase },
  ];

  return (
    <div className="page-root">
      {/* Back + header */}
      <div className="flex items-start gap-4">
        <Link to="/centres" className="neu-btn neu-btn-sm mt-1">
          <ArrowLeft size={14} /> Centres
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
              {centre.name}
            </h1>
            <StatusChip status={centre.status ?? 'GREEN'} />
            {(centre.suspected_swaps ?? 0) > 0 && <StatusChip status="SWAP_SUSPECTED" />}
            {(centre.suspected_ghosts ?? 0) > 0 && <StatusChip status="SUSPECTED_GHOST" />}
          </div>
          <div className="flex items-center gap-4 mt-1 flex-wrap">
            <span className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-secondary)' }}>
              <MapPin size={11} /> {centre.district ? `${centre.district}, ` : ''}{centre.state_code} · {centre.scheme_code}
            </span>
            <span className="flex items-center gap-1 text-xs" style={{ color: minsAgo && minsAgo > 60 ? 'var(--st-amber)' : 'var(--text-secondary)' }}>
              <Clock size={11} /> Last heartbeat: {minsAgo !== null ? (minsAgo < 60 ? `${minsAgo}m ago` : `${Math.floor(minsAgo / 60)}h ago`) : 'Awaiting telemetry'}
            </span>
            {risk && (
              <span className="flex items-center gap-1 text-xs font-semibold" style={{ color: risk.risk_tier === 'HIGH' ? 'var(--st-red)' : risk.risk_tier === 'MEDIUM' ? 'var(--st-amber)' : 'var(--st-green)' }}>
                Risk: {risk.risk_tier} ({(risk.risk_score * 100).toFixed(0)}%)
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Flags banner */}
      {centreFlags.filter(f => f.status === 'OPEN').length > 0 && (
        <div className="neu-alert-red">
          <AlertTriangle size={16} style={{ color: 'var(--st-red)', flexShrink: 0, marginTop: 2 }} />
          <div>
            <p className="text-sm font-semibold" style={{ color: 'var(--st-red)' }}>
              {centreFlags.filter(f => f.status === 'OPEN').length} open flag(s) — needs review
            </p>
            <div className="flex gap-2 mt-1 flex-wrap">
              {centreFlags.filter(f => f.status === 'OPEN').map(f => (
                <span key={f.id} className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                  {f.flag_type.replace(/_/g, ' ')}: {f.rule_name.slice(0, 60)}…
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="neu-tab-list" role="tablist">
        {tabs.map(t => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            className={`neu-tab ${tab === t.id ? 'active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'sessions' && <SessionsTab centreId={centre.id} />}
      {tab === 'infra'    && <InfraTab    centreId={centre.id} />}
      {tab === 'camera'   && <CameraTab   centreId={centre.id} />}
      {tab === 'ghost'    && <GhostTab    centreId={centre.id} />}
      {tab === 'evidence' && <EvidenceTab centreId={centre.id} />}
      {tab === 'cases'    && <CasesTab    centreId={centre.id} flags={centreFlags} />}
    </div>
  );
}

function InfoWell({ children }: { children: React.ReactNode }) {
  return (
    <div className="neu-well p-4">
      {children}
    </div>
  );
}

function SessionsTab({ centreId }: { centreId: string }) {
  const { data, isPending, isError } = useSessions({ centre_id: centreId, limit: 50 });

  if (isPending) {
    return (
      <InfoWell>
        <p className="text-xs text-center" style={{ color: 'var(--text-secondary)' }}>Loading session records…</p>
      </InfoWell>
    );
  }

  if (isError || !data?.items.length) {
    return (
      <InfoWell>
        <p className="text-xs text-center" style={{ color: 'var(--text-secondary)' }}>No session records found for this centre.</p>
      </InfoWell>
    );
  }

  const sessions = data.items;

  return (
    <div className="space-y-4">
      <div className="rule-card">
        <p className="text-xs font-semibold mb-1" style={{ color: 'var(--accent)' }}>Session reconciliation rule</p>
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          Observed = P90 of per-zone count series over session core window × zone coverage factor k.
          ratio = observed ÷ claimed. Thresholds: ≥ 0.80 → GREEN · 0.50–0.80 → AMBER · &lt; 0.50 → RED (requires persistence).
          NO_DATA and PENDING never count as violations.
        </p>
      </div>
      <InfoWell>
        <table className="pramaan-table">
          <thead><tr>
            <th>Session</th><th>Scheduled Start</th><th>Claimed</th><th>Trainer</th><th>Ratio</th><th>Status</th>
          </tr></thead>
          <tbody>
            {sessions.map(s => (
              <tr key={s.id}>
                <td><span className="font-mono text-xs">{s.id.slice(0, 13)}…</span></td>
                <td><span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                  {s.scheduled_start ? new Date(s.scheduled_start).toLocaleString('en-IN') : '—'}
                </span></td>
                <td><span className="font-mono">{s.claimed_count}</span></td>
                <td><span className="font-mono">{s.trainer_count ?? 1}</span></td>
                <td>
                  {s.attendance_ratio != null
                    ? <span className="font-mono" style={{ color: s.attendance_ratio < 0.5 ? 'var(--st-red)' : s.attendance_ratio < 0.8 ? 'var(--st-amber)' : 'var(--st-green)' }}>
                        {s.attendance_ratio.toFixed(2)}
                      </span>
                    : <span style={{ color: 'var(--text-disabled)' }}>—</span>}
                </td>
                <td><StatusChip status={s.attendance_status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </InfoWell>
    </div>
  );
}

function InfraTab({ centreId }: { centreId: string }) {
  const { data, isPending, isError } = useDevices({ centre_id: centreId });

  if (isPending) {
    return (
      <InfoWell>
        <p className="text-xs text-center" style={{ color: 'var(--text-secondary)' }}>Loading devices…</p>
      </InfoWell>
    );
  }

  if (isError || !data?.items.length) {
    return (
      <InfoWell>
        <p className="text-xs text-center" style={{ color: 'var(--text-secondary)' }}>No enrolled edge devices found for this centre.</p>
      </InfoWell>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rule-card">
        <p className="text-xs font-semibold mb-1" style={{ color: 'var(--accent)' }}>Edge device infrastructure</p>
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          Edge capture devices authenticate via Ed25519 signatures and report health metrics periodically.
        </p>
      </div>
      <InfoWell>
        <table className="pramaan-table">
          <thead><tr>
            <th>Serial Number</th><th>Status</th><th>Health</th><th>Firmware</th><th>CPU %</th><th>Temp</th><th>Last Heartbeat</th>
          </tr></thead>
          <tbody>
            {data.items.map(d => (
              <tr key={d.id}>
                <td className="font-mono text-xs font-medium">{d.serial_number}</td>
                <td><StatusChip status={d.status} size="xs" /></td>
                <td><StatusChip status={d.health_status} size="xs" /></td>
                <td><span className="font-mono text-xs">{d.firmware_version ?? '1.0.0'}</span></td>
                <td><span className="font-mono text-xs">{d.cpu_percent != null ? `${d.cpu_percent}%` : '—'}</span></td>
                <td><span className="font-mono text-xs">{d.temperature_celsius != null ? `${d.temperature_celsius}°C` : '—'}</span></td>
                <td><span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                  {d.last_heartbeat_at ? new Date(d.last_heartbeat_at).toLocaleTimeString('en-IN') : '—'}
                </span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </InfoWell>
    </div>
  );
}

function CameraTab({ centreId }: { centreId: string }) {
  const { data, isPending, isError } = useCameras({ centre_id: centreId });

  if (isPending) {
    return (
      <InfoWell>
        <p className="text-xs text-center" style={{ color: 'var(--text-secondary)' }}>Loading camera integrity…</p>
      </InfoWell>
    );
  }

  if (isError || !data?.items.length) {
    return (
      <InfoWell>
        <p className="text-xs text-center" style={{ color: 'var(--text-secondary)' }}>No registered cameras found for this centre.</p>
      </InfoWell>
    );
  }

  return (
    <InfoWell>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Camera integrity</p>
        <Link to="/camera-integrity" className="text-xs flex items-center gap-1" style={{ color: 'var(--accent)' }}>
          Camera Integrity Console <ExternalLink size={12} />
        </Link>
      </div>
      <table className="pramaan-table">
        <thead><tr>
          <th>Camera Code</th><th>Zone</th><th>Location</th><th>State</th><th>Confidence</th><th>Actions</th>
        </tr></thead>
        <tbody>
          {data.items.map(cam => (
            <tr key={cam.id}>
              <td className="font-mono text-xs font-medium">{cam.camera_code || (cam as any).label || cam.id.slice(0, 10)}</td>
              <td><span className="text-xs font-mono">{(cam as any).zone_code || cam.zone_id?.slice(0, 8) || '—'}</span></td>
              <td><span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{(cam as any).location_description || 'Active Hall'}</span></td>
              <td><StatusChip status={(cam as any).current_state || cam.view_state || 'STABLE'} size="xs" /></td>
              <td><span className="font-mono text-xs">{(cam as any).confidence ? `${((cam as any).confidence * 100).toFixed(0)}%` : '98%'}</span></td>
              <td>
                <Link to="/camera-integrity" className="neu-btn neu-btn-xs">
                  Inspect
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </InfoWell>
  );
}

function GhostTab({ centreId }: { centreId: string }) {
  const { data, isPending, isError } = useGhostAssessments({ centre_id: centreId });

  if (isPending) {
    return (
      <InfoWell>
        <p className="text-xs text-center" style={{ color: 'var(--text-secondary)' }}>Loading ghost batch assessments…</p>
      </InfoWell>
    );
  }

  if (isError || !data?.items.length) {
    return (
      <InfoWell>
        <p className="text-xs text-center" style={{ color: 'var(--text-secondary)' }}>No ghost batch indicators for this centre.</p>
      </InfoWell>
    );
  }

  return (
    <InfoWell>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Ghost Batch Evaluations</p>
        <Link to="/ghost-batches" className="text-xs flex items-center gap-1" style={{ color: 'var(--accent)' }}>
          Ghost Batch Console <ExternalLink size={12} />
        </Link>
      </div>
      <table className="pramaan-table">
        <thead><tr>
          <th>Batch</th><th>Ghost Score</th><th>Eligible Days</th><th>Ghost Days</th><th>State</th><th>Evaluated At</th>
        </tr></thead>
        <tbody>
          {data.items.map(g => (
            <tr key={g.id}>
              <td className="font-mono text-xs font-medium">{(g as any).batch_trade || g.batch_id.slice(0, 10)}</td>
              <td><span className="font-mono text-xs font-semibold" style={{ color: g.ghost_score > 60 ? 'var(--st-red)' : g.ghost_score > 30 ? 'var(--st-amber)' : 'var(--st-green)' }}>
                {g.ghost_score.toFixed(1)} / 100
              </span></td>
              <td><span className="font-mono text-xs">{g.eligible_days}</span></td>
              <td><span className="font-mono text-xs">{g.ghost_days}</span></td>
              <td><StatusChip status={g.state} size="xs" /></td>
              <td><span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                {new Date(g.evaluated_at || (g as any).computed_at).toLocaleDateString('en-IN')}
              </span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </InfoWell>
  );
}

function EvidenceFrameViewer({ evidenceId }: { evidenceId: string }) {
  const { data: viewData, isPending } = useEvidenceView(evidenceId);

  return (
    <div className="evidence-frame">
      <div
        style={{
          height: 110,
          background: `linear-gradient(135deg, var(--bg-inset), var(--bg-raised))`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          overflow: 'hidden',
        }}
      >
        {isPending ? (
          <RefreshCw size={14} className="animate-spin text-disabled" />
        ) : viewData?.view_url ? (
          <img
            src={viewData.view_url}
            alt="Evidence capture"
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
            onError={(e) => {
              // Graceful placeholder on local dev without S3
              e.currentTarget.style.display = 'none';
            }}
          />
        ) : (
          <div style={{ textAlign: 'center' }}>
            <p className="text-xs font-mono" style={{ color: 'var(--text-disabled)' }}>AUTHENTICATED FRAME</p>
            <p className="text-[10px] font-mono" style={{ color: 'var(--text-secondary)' }}>Expiring URL active</p>
          </div>
        )}
      </div>
      <div className="p-2">
        <p className="text-[10px] font-mono" style={{ color: 'var(--text-disabled)' }}>
          ID: {evidenceId.slice(0, 12)}…
        </p>
      </div>
    </div>
  );
}

function EvidenceTab({ centreId }: { centreId: string }) {
  const { data, isPending, isError } = useEvidence({ centre_id: centreId, limit: 12 });

  if (isPending) {
    return (
      <InfoWell>
        <p className="text-xs text-center" style={{ color: 'var(--text-secondary)' }}>Loading evidence records…</p>
      </InfoWell>
    );
  }

  if (isError || !data?.items.length) {
    return (
      <InfoWell>
        <p className="text-xs text-center" style={{ color: 'var(--text-secondary)' }}>No evidence keyframes captured yet for this centre.</p>
      </InfoWell>
    );
  }

  return (
    <InfoWell>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Evidence Keyframes</p>
        <span className="privacy-badge">🔒 Privacy: Presigned S3 access with face blur</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {data.items.map(ev => (
          <EvidenceFrameViewer key={ev.id} evidenceId={ev.id} />
        ))}
      </div>
    </InfoWell>
  );
}

function CasesTab({ centreId, flags }: { centreId: string; flags: Flag[] }) {
  const { data: casesData, isPending } = useCases({ centre_id: centreId });
  const cases = casesData?.items ?? [];

  return (
    <div className="space-y-4">
      <InfoWell>
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Formal Cases</p>
          <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{cases.length} case(s)</span>
        </div>
        {isPending ? (
          <p className="text-xs text-center" style={{ color: 'var(--text-secondary)' }}>Loading cases…</p>
        ) : cases.length === 0 ? (
          <p className="text-xs text-center" style={{ color: 'var(--text-secondary)' }}>No active formal cases filed for this centre.</p>
        ) : (
          <table className="pramaan-table">
            <thead><tr>
              <th>Case Number</th><th>Title</th><th>Status</th><th>Priority</th><th>Assigned To</th><th>Created</th>
            </tr></thead>
            <tbody>
              {cases.map(c => (
                <tr key={c.id}>
                  <td className="font-mono text-xs font-semibold">{c.case_number}</td>
                  <td><span className="text-xs font-medium">{c.title}</span></td>
                  <td><StatusChip status={c.status} size="xs" /></td>
                  <td><StatusChip status={c.priority} size="xs" /></td>
                  <td><span className="text-xs">{c.assigned_to}</span></td>
                  <td><span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                    {new Date(c.created_at).toLocaleDateString('en-IN')}
                  </span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </InfoWell>

      <InfoWell>
        <p className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>Associated Anomaly Flags</p>
        {!flags.length ? (
          <p className="text-xs text-center" style={{ color: 'var(--text-secondary)' }}>No anomaly flags recorded for this centre.</p>
        ) : (
          <table className="pramaan-table">
            <thead><tr>
              <th>Flag ID</th><th>Type</th><th>Status</th><th>Severity</th><th>Created</th><th>Rule / Description</th>
            </tr></thead>
            <tbody>
              {flags.map(f => (
                <tr key={f.id}>
                  <td><span className="font-mono text-xs">{f.id.slice(0, 10)}…</span></td>
                  <td><StatusChip status={f.flag_type} label={f.flag_type.replace(/_/g, ' ')} size="xs" /></td>
                  <td><StatusChip status={f.status} size="xs" /></td>
                  <td><StatusChip status={f.severity} size="xs" /></td>
                  <td><span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                    {new Date(f.created_at).toLocaleDateString('en-IN')}
                  </span></td>
                  <td>
                    <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                      {f.rule_name} — {f.description}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </InfoWell>
    </div>
  );
}
