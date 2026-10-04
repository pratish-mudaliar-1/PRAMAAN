import React, { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Wifi, WifiOff, MapPin, Clock, AlertTriangle } from 'lucide-react';
import { MOCK_CENTRES, MOCK_FLAGS } from '@/api/mockData';
import { StatusChip } from '@/components/status/StatusChip';

export function CentreDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [tab, setTab] = useState('sessions');

  const centre = MOCK_CENTRES.find(c => c.id === id);
  if (!centre) {
    return (
      <div className="page-root">
        <div className="neu-card p-8 text-center">
          <p style={{ color: 'var(--text-secondary)' }}>Centre not found: {id}</p>
          <Link to="/centres" className="neu-btn mt-4 inline-flex">← Back to centres</Link>
        </div>
      </div>
    );
  }

  const centreFlags = MOCK_FLAGS.filter(f => f.centre_id === centre.id);
  const hb = new Date(centre.last_heartbeat);
  const minsAgo = Math.floor((Date.now() - hb.getTime()) / 60_000);

  const tabs = [
    { id: 'sessions',    label: 'Sessions'        },
    { id: 'infra',       label: 'Infrastructure'  },
    { id: 'camera',      label: 'Camera Integrity'},
    { id: 'ghost',       label: 'Ghost Batches'   },
    { id: 'evidence',    label: 'Evidence'        },
    { id: 'cases',       label: 'Cases'           },
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
            <StatusChip status={centre.status} />
            {centre.suspected_swaps > 0 && <StatusChip status="SUSPECTED_SWAP" />}
          </div>
          <div className="flex items-center gap-4 mt-1 flex-wrap">
            <span className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-secondary)' }}>
              <MapPin size={11} /> {centre.state} · {centre.scheme}
            </span>
            <span className="flex items-center gap-1 text-xs" style={{ color: minsAgo > 60 ? 'var(--st-amber)' : 'var(--text-secondary)' }}>
              <Clock size={11} /> Last heartbeat: {minsAgo < 60 ? `${minsAgo}m ago` : `${Math.floor(minsAgo / 60)}h ago`}
            </span>
          </div>
        </div>
        <span className="simulated-badge">SIMULATED</span>
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
                  {f.type.replace('_', ' ')}: {f.rule_fired.slice(0, 60)}…
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
      {tab === 'cases'    && <CasesTab    flags={centreFlags}   />}
    </div>
  );
}

/* ── Tab content placeholders ── */

function InfoWell({ children }: { children: React.ReactNode }) {
  return (
    <div className="neu-well p-4">
      {children}
    </div>
  );
}

function SessionsTab({ centreId }: { centreId: string }) {
  // Demo sessions for this centre
  const sessions = centreId === 'CTR-A' ? [
    { id: 'SES-A-001', date: '2026-09-22', claimed: 25, observed: 22, ratio: 0.88, status: 'GREEN'  },
    { id: 'SES-A-002', date: '2026-09-24', claimed: 25, observed: 20, ratio: 0.80, status: 'GREEN'  },
    { id: 'SES-A-003', date: '2026-09-26', claimed: 25, observed: 15, ratio: 0.60, status: 'AMBER'  },
    { id: 'SES-A-004', date: '2026-09-28', claimed: 25, observed:  9, ratio: 0.36, status: 'RED',
      rule: 'ratio 0.36 < 0.50 for 2+ windows' },
    { id: 'SES-A-005', date: '2026-09-30', claimed: 25, observed: 21, ratio: 0.84, status: 'GREEN'  },
  ] : centreId === 'CTR-E' ? [
    { id: 'SES-E-001', date: '2026-09-22', claimed: 18, observed: null, ratio: null, status: 'NO-DATA', rule: 'Edge offline' },
    { id: 'SES-E-002', date: '2026-09-24', claimed: 18, observed: null, ratio: null, status: 'NO-DATA', rule: 'Edge offline' },
  ] : [
    { id: 'SES-X-001', date: '2026-09-22', claimed: 20, observed: 19, ratio: 0.95, status: 'GREEN' },
    { id: 'SES-X-002', date: '2026-09-24', claimed: 20, observed: 18, ratio: 0.90, status: 'GREEN' },
  ];

  return (
    <div className="space-y-4">
      <div className="rule-card">
        <p className="text-xs font-semibold mb-1" style={{ color: 'var(--accent)' }}>Session reconciliation rule</p>
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          Observed = P90 of per-zone count series over session core window × zone coverage factor k.
          ratio = observed ÷ claimed. Thresholds: ≥ 0.80 → GREEN · 0.50–0.80 → AMBER · &lt; 0.50 → RED (requires persistence).
          NO-DATA and PENDING never count as violations.
        </p>
      </div>
      <InfoWell>
        <table className="pramaan-table">
          <thead><tr>
            <th>Session</th><th>Date</th><th>Claimed</th><th>Observed P90</th><th>Ratio</th><th>Status</th><th>Rule fired</th>
          </tr></thead>
          <tbody>
            {sessions.map(s => (
              <tr key={s.id}>
                <td><span className="font-mono text-xs">{s.id}</span></td>
                <td><span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>{s.date}</span></td>
                <td><span className="font-mono">{s.claimed}</span></td>
                <td>
                  {s.observed != null
                    ? <span className="font-mono">{s.observed}</span>
                    : <span style={{ color: 'var(--text-disabled)' }}>—</span>}
                </td>
                <td>
                  {s.ratio != null
                    ? <span className="font-mono" style={{ color: s.ratio < 0.5 ? 'var(--st-red)' : s.ratio < 0.8 ? 'var(--st-amber)' : 'var(--st-green)' }}>
                        {s.ratio.toFixed(2)}
                      </span>
                    : <span style={{ color: 'var(--text-disabled)' }}>—</span>}
                </td>
                <td><StatusChip status={s.status} /></td>
                <td>
                  {'rule' in s && s.rule
                    ? <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{s.rule}</span>
                    : <span style={{ color: 'var(--text-disabled)' }}>—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </InfoWell>
    </div>
  );
}

function InfraTab({ centreId }: { centreId: string }) {
  const items = centreId === 'CTR-B' ? [
    { name: 'Industrial Sewing Machine', sanctioned: 5, detected: 2, status: 'ABSENT',  note: 'Unseen in 3 unoccluded windows on 2 days' },
    { name: 'Overlock Machine',          sanctioned: 3, detected: 2, status: 'UNCERTAIN', note: 'Partially occluded — cannot confirm' },
    { name: 'Cutting Table',             sanctioned: 2, detected: 2, status: 'PRESENT', note: '' },
    { name: 'Iron Press',                sanctioned: 4, detected: 4, status: 'PRESENT', note: '' },
  ] : [
    { name: 'Computer Workstation',  sanctioned: 25, detected: 24, status: 'PRESENT', note: '' },
    { name: 'Monitor',               sanctioned: 25, detected: 23, status: 'PRESENT', note: '' },
    { name: 'Projector',             sanctioned:  1, detected:  1, status: 'PRESENT', note: '' },
  ];

  return (
    <div className="space-y-4">
      <div className="rule-card">
        <p className="text-xs font-semibold mb-1" style={{ color: 'var(--accent)' }}>Infrastructure compliance rule</p>
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          ABSENT only after item is unseen across several unoccluded windows on ≥ 2 days (persistence stepper).
          UNCERTAIN when occluded or evidence insufficient. No ABSENT verdict from a single observation.
        </p>
      </div>
      <InfoWell>
        <table className="pramaan-table">
          <thead><tr>
            <th>Item</th><th>Sanctioned</th><th>Detected</th><th>Status</th><th>Note</th>
          </tr></thead>
          <tbody>
            {items.map(item => (
              <tr key={item.name}>
                <td className="font-medium">{item.name}</td>
                <td className="font-mono">{item.sanctioned}</td>
                <td className="font-mono">{item.detected}</td>
                <td><StatusChip status={item.status} /></td>
                <td><span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{item.note || '—'}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </InfoWell>
    </div>
  );
}

function CameraTab({ centreId }: { centreId: string }) {
  return (
    <InfoWell>
      <p className="text-sm font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>Camera integrity</p>
      <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>
        See the global <Link to="/camera-integrity" style={{ color: 'var(--accent)' }}>Camera Integrity</Link> screen for
        similarity timelines, compare sliders and baseline history.
      </p>
      {centreId === 'CTR-C' && (
        <div className="neu-alert-red">
          <AlertTriangle size={15} style={{ color: 'var(--st-red)', flexShrink: 0 }} />
          <div>
            <p className="text-sm font-semibold" style={{ color: 'var(--st-red)' }}>
              SUSPECTED_SWAP — CAM-C-01
            </p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
              Scene similarity fell from 0.83 to 0.19 at 10:42 on 2026-10-04 and stayed below 0.35
              for 15 minutes. 7 of 9 registered anchors not found. Counts from this camera have been
              excluded from reconciliation.
            </p>
          </div>
        </div>
      )}
    </InfoWell>
  );
}

function GhostTab({ centreId }: { centreId: string }) {
  return (
    <InfoWell>
      <p className="text-sm font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>Ghost batch status</p>
      {centreId === 'CTR-D' ? (
        <div className="neu-alert-amber">
          <span style={{ color: 'var(--st-ghost)', fontSize: 18 }}>👻</span>
          <div>
            <p className="text-sm font-semibold" style={{ color: 'var(--st-ghost)' }}>SUSPECTED_GHOST — BATCH-D-01</p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
              Ghost Score: 78/100. See <Link to="/ghost-batches/BATCH-D-01" style={{ color: 'var(--accent)' }}>Ghost Batch detail</Link> for full breakdown.
            </p>
          </div>
        </div>
      ) : (
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>No ghost batch indicators for this centre.</p>
      )}
    </InfoWell>
  );
}

function EvidenceTab({ centreId }: { centreId: string }) {
  return (
    <InfoWell>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Evidence keyframes</p>
        <span className="privacy-badge">🔒 Privacy: faces blurred, counts only</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {[1, 2, 3].map(i => (
          <div key={i} className="evidence-frame">
            <div
              style={{
                height: 100,
                background: `linear-gradient(135deg, var(--bg-inset), var(--bg-raised))`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              <div style={{ textAlign: 'center' }}>
                <p className="text-xs font-mono" style={{ color: 'var(--text-disabled)' }}>BLURRED FRAME</p>
                <p className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>count: {9 + i}</p>
              </div>
            </div>
            <div className="p-2">
              <p className="text-[10px] font-mono" style={{ color: 'var(--text-disabled)' }}>
                2026-09-{20 + i}T10:{30 + i}:00+05:30
              </p>
            </div>
          </div>
        ))}
      </div>
    </InfoWell>
  );
}

function CasesTab({ flags }: { flags: typeof MOCK_FLAGS }) {
  if (!flags.length) {
    return (
      <InfoWell>
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>No cases for this centre.</p>
      </InfoWell>
    );
  }
  return (
    <InfoWell>
      <table className="pramaan-table">
        <thead><tr>
          <th>Flag ID</th><th>Type</th><th>Status</th><th>Severity</th><th>Created</th><th>TC response</th>
        </tr></thead>
        <tbody>
          {flags.map(f => (
            <tr key={f.id}>
              <td><span className="font-mono text-xs">{f.id}</span></td>
              <td><StatusChip status={f.type} label={f.type.replace('_', ' ')} size="xs" /></td>
              <td><StatusChip status={f.status} size="xs" /></td>
              <td><StatusChip status={f.severity} size="xs" /></td>
              <td><span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                {new Date(f.created_at).toLocaleDateString('en-IN')}
              </span></td>
              <td>
                {f.tc_response
                  ? <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{f.tc_response.slice(0, 50)}…</span>
                  : <span style={{ color: 'var(--text-disabled)', fontSize: '0.75rem' }}>—</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </InfoWell>
  );
}
