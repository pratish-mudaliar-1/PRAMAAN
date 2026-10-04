import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ExternalLink, Clock, AlertTriangle, Info } from 'lucide-react';
import { MOCK_FLAGS, MOCK_AUDIT } from '@/api/mockData';
import { StatusChip } from '@/components/status/StatusChip';

function formatSLA(deadline: string) {
  const diff = new Date(deadline).getTime() - Date.now();
  const h = Math.floor(diff / 3_600_000);
  if (diff < 0) return <span className="sla-critical font-mono text-xs font-bold">Overdue</span>;
  if (h < 12)   return <span className="sla-critical font-mono text-xs">{h}h left</span>;
  if (h < 48)   return <span className="sla-warning  font-mono text-xs">{h}h left</span>;
  return <span className="sla-ok font-mono text-xs">{Math.floor(h / 24)}d left</span>;
}

const FLAG_TYPE_LABELS: Record<string, string> = {
  OCCUPANCY: 'Occupancy', ITEM_ABSENT: 'Item absent',
  FEED_HEALTH: 'Feed health', DUPLICATE_EVIDENCE: 'Duplicate evidence',
  CAMERA_SWAP: 'Camera swap', GHOST_BATCH: 'Ghost batch',
};

export function FlagsCasesPage() {
  const [typeFilter, setTypeFilter]     = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [selectedFlag, setSelectedFlag] = useState<string | null>(null);

  const types   = ['ALL', 'OCCUPANCY', 'CAMERA_SWAP', 'GHOST_BATCH', 'ITEM_ABSENT', 'FEED_HEALTH', 'DUPLICATE_EVIDENCE'];
  const statuses = ['ALL', 'OPEN', 'TC_RESPONDED', 'UNDER_REVIEW', 'CLOSED'];

  const filtered = MOCK_FLAGS.filter(f => {
    const t = typeFilter   === 'ALL' || f.type   === typeFilter;
    const s = statusFilter === 'ALL' || f.status === statusFilter;
    return t && s;
  }).sort((a, b) => {
    const sev = { HIGH: 0, MEDIUM: 1, LOW: 2 } as const;
    return sev[a.severity] - sev[b.severity];
  });

  const selected = selectedFlag ? MOCK_FLAGS.find(f => f.id === selectedFlag) : null;

  return (
    <div className="page-root">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Flags &amp; Cases
          </h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            Unified exception inbox — exception-first ordering
          </p>
        </div>
        <span className="simulated-badge">SIMULATED DATA</span>
      </div>

      {/* Principle banner */}
      <div className="neu-alert-info">
        <Info size={14} style={{ color: 'var(--accent)', flexShrink: 0, marginTop: 2 }} />
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          Flags are leads for review, not proven violations. Every flag shows the rule, numbers, time window and evidence.
          The training centre has a response path on every flag.
        </p>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div className="neu-segment-group" role="group" aria-label="Filter by flag type">
          {types.map(t => (
            <button
              key={t}
              className={`neu-segment ${typeFilter === t ? 'active' : ''}`}
              onClick={() => setTypeFilter(t)}
            >
              {t === 'ALL' ? 'All types' : FLAG_TYPE_LABELS[t] ?? t}
            </button>
          ))}
        </div>
        <div className="neu-segment-group" role="group" aria-label="Filter by status">
          {statuses.map(s => (
            <button
              key={s}
              className={`neu-segment ${statusFilter === s ? 'active' : ''}`}
              onClick={() => setStatusFilter(s)}
            >
              {s === 'ALL' ? 'All statuses' : s.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Flag list */}
        <div className="lg:col-span-2 neu-card overflow-hidden">
          <div className="px-4 py-3" style={{ borderBottom: 'var(--edge)' }}>
            <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              {filtered.length} flag{filtered.length !== 1 ? 's' : ''}
            </p>
          </div>
          <div className="neu-well overflow-x-auto" style={{ borderRadius: 0, border: 'none', boxShadow: 'none' }}>
            <table className="pramaan-table pramaan-table-clickable min-w-[600px]" role="grid" aria-label="Flags table">
              <thead>
                <tr>
                  {['Centre', 'Type', 'Severity', 'SLA', 'Status', ''].map(h => <th key={h}>{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-disabled)', padding: '2rem' }}>
                      No flags match the current filters.
                    </td>
                  </tr>
                ) : filtered.map(f => (
                  <tr
                    key={f.id}
                    onClick={() => setSelectedFlag(f.id === selectedFlag ? null : f.id)}
                    style={{
                      cursor: 'pointer',
                      background: selectedFlag === f.id ? 'rgba(111,140,255,0.08)' : undefined,
                    }}
                  >
                    <td>
                      <p className="font-medium text-sm" style={{ color: 'var(--text-primary)' }}>{f.centre_name}</p>
                      <p className="text-[10px] font-mono" style={{ color: 'var(--text-disabled)' }}>{f.id}</p>
                    </td>
                    <td>
                      <StatusChip
                        status={f.type}
                        label={FLAG_TYPE_LABELS[f.type] ?? f.type}
                        size="xs"
                      />
                    </td>
                    <td><StatusChip status={f.severity} size="xs" /></td>
                    <td>{formatSLA(f.sla_deadline)}</td>
                    <td><StatusChip status={f.status} size="xs" /></td>
                    <td>
                      {f.evidence_link && (
                        <Link
                          to={f.evidence_link}
                          className="neu-btn neu-btn-xs"
                          style={{ textDecoration: 'none' }}
                          onClick={e => e.stopPropagation()}
                        >
                          <ExternalLink size={11} /> View
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Flag detail panel */}
        <div className="space-y-4">
          {selected ? (
            <FlagDetail flag={selected} />
          ) : (
            <div className="neu-well p-6 text-center">
              <p style={{ color: 'var(--text-disabled)', fontSize: '0.85rem' }}>
                Click a flag to see rule, evidence and TC response path.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function FlagDetail({ flag }: { flag: typeof MOCK_FLAGS[0] }) {
  const [tcNote, setTcNote] = useState('');
  const relatedAudit = MOCK_AUDIT.filter(a => a.entity_id === flag.id);

  return (
    <div className="space-y-3">
      {/* Rule explanation */}
      <div className="neu-card p-4">
        <p className="section-header">Flag detail</p>
        <p className="font-semibold text-sm mb-1" style={{ color: 'var(--text-primary)' }}>{flag.id}</p>
        <p className="text-xs mb-2" style={{ color: 'var(--text-secondary)' }}>{flag.centre_name}</p>
        <div className="flex gap-2 flex-wrap mb-3">
          <StatusChip status={flag.type} label={flag.type.replace('_', ' ')} size="xs" />
          <StatusChip status={flag.severity} size="xs" />
          <StatusChip status={flag.status} size="xs" />
        </div>

        <div className="rule-card mb-3">
          <p className="text-xs font-semibold mb-1" style={{ color: 'var(--accent)' }}>Rule fired</p>
          <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{flag.rule_fired}</p>
        </div>

        <div className="flex items-center gap-1 text-xs mb-3" style={{ color: 'var(--text-disabled)' }}>
          <Clock size={10} />
          Created: {new Date(flag.created_at).toLocaleString('en-IN')}
        </div>
        <div className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-disabled)' }}>
          <AlertTriangle size={10} />
          SLA: {new Date(flag.sla_deadline).toLocaleString('en-IN')}
        </div>
      </div>

      {/* TC response */}
      <div className="neu-card p-4">
        <p className="section-header">TC response</p>
        {flag.tc_response ? (
          <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{flag.tc_response}</p>
        ) : (
          <div className="space-y-2">
            <p className="text-xs" style={{ color: 'var(--text-disabled)' }}>No response yet. TC can add a note:</p>
            <textarea
              className="neu-input"
              style={{ minHeight: 80, resize: 'vertical' }}
              placeholder="Training Centre response note…"
              value={tcNote}
              onChange={e => setTcNote(e.target.value)}
              aria-label="TC response note"
            />
            <button className="neu-btn neu-btn-primary neu-btn-sm w-full">Submit response</button>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="neu-card p-4 space-y-2">
        <p className="section-header">Actions</p>
        <button className="neu-btn w-full neu-btn-sm">Request inspection</button>
        <button className="neu-btn w-full neu-btn-sm">Request TC explanation</button>
        <button className="neu-btn w-full neu-btn-sm neu-btn-danger">Escalate (note required)</button>
        <button className="neu-btn w-full neu-btn-sm" style={{ color: 'var(--text-disabled)' }}>Close as explained</button>
      </div>

      {/* Audit trail */}
      {relatedAudit.length > 0 && (
        <div className="neu-card p-4">
          <p className="section-header">Audit trail</p>
          <div className="space-y-2">
            {relatedAudit.map(a => (
              <div key={a.id} className="flex gap-2">
                <div
                  className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0"
                  style={{ background: 'var(--accent)' }}
                />
                <div>
                  <p className="text-xs" style={{ color: 'var(--text-primary)' }}>{a.action.replace(/_/g, ' ')}</p>
                  {a.note && <p className="text-[11px]" style={{ color: 'var(--text-secondary)' }}>{a.note}</p>}
                  <p className="text-[10px] font-mono" style={{ color: 'var(--text-disabled)' }}>
                    {a.actor} · {new Date(a.ts).toLocaleString('en-IN')}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
