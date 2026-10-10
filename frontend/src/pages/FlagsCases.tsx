import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ExternalLink, Clock, RefreshCw } from 'lucide-react';
import { useFlags, useFlag, useResolveFlag } from '@/hooks/useFlags';
import { useCentres } from '@/hooks/useCentres';
import { StatusChip } from '@/components/status/StatusChip';
import type { Flag } from '@/types';

const FLAG_TYPE_LABELS: Record<string, string> = {
  ATTENDANCE_RED: 'Attendance Red',
  ATTENDANCE_AMBER_REPEAT: 'Amber Repeat',
  GHOST_BATCH: 'Ghost Batch',
  ITEM_ABSENT: 'Item Absent',
  DEVICE_OFFLINE: 'Device Offline',
  INTEGRITY_CHAIN_BREAK: 'Integrity Break',
  EVIDENCE_DUPLICATE: 'Evidence Duplicate',
};

export function FlagsCasesPage() {
  const [typeFilter, setTypeFilter]     = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [selectedFlag, setSelectedFlag] = useState<string | null>(null);

  const { data: flagsData, isPending, isError, refetch } = useFlags({ limit: 200 });
  const { data: centresData } = useCentres({ limit: 200 });
  const allFlags   = flagsData?.items ?? [];
  const allCentres = centresData?.items ?? [];

  const types = [
    'ALL',
    'ATTENDANCE_RED',
    'ATTENDANCE_AMBER_REPEAT',
    'GHOST_BATCH',
    'ITEM_ABSENT',
    'DEVICE_OFFLINE',
    'INTEGRITY_CHAIN_BREAK',
    'EVIDENCE_DUPLICATE',
  ];
  const statuses = ['ALL', 'OPEN', 'UNDER_REVIEW', 'CLOSED_CONFIRMED', 'CLOSED_DISMISSED'];

  const filtered = allFlags.filter(f => {
    const t = typeFilter   === 'ALL' || f.flag_type === typeFilter;
    const s = statusFilter === 'ALL' || f.status === statusFilter;
    return t && s;
  }).sort((a, b) => {
    const sev = { HIGH: 0, MEDIUM: 1, LOW: 2 } as const;
    return sev[a.severity] - sev[b.severity];
  });

  const selected = selectedFlag ? allFlags.find(f => f.id === selectedFlag) : null;

  return (
    <div className="page-root">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Flags &amp; Cases
          </h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            Unified exception inbox — backend reconciliation rules
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isPending && <RefreshCw size={14} className="animate-spin" style={{ color: 'var(--text-disabled)' }} />}
          {isError && <button onClick={() => refetch()} className="neu-btn neu-btn-xs">Retry</button>}
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex gap-2 flex-wrap items-center">
        <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>Type:</span>
        {types.map(t => (
          <button
            key={t}
            className={`neu-btn neu-btn-xs ${typeFilter === t ? 'neu-btn-primary' : ''}`}
            onClick={() => setTypeFilter(t)}
          >
            {t === 'ALL' ? 'All types' : (FLAG_TYPE_LABELS[t] ?? t)}
          </button>
        ))}
      </div>

      <div className="flex gap-2 flex-wrap items-center">
        <span className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>Status:</span>
        {statuses.map(s => (
          <button
            key={s}
            className={`neu-btn neu-btn-xs ${statusFilter === s ? 'neu-btn-primary' : ''}`}
            onClick={() => setStatusFilter(s)}
          >
            {s.replace(/_/g, ' ')}
          </button>
        ))}
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
                  {['Centre', 'Type', 'Severity', 'Created', 'Status', ''].map(h => <th key={h}>{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-disabled)', padding: '2rem' }}>
                      No flags match the current filters.
                    </td>
                  </tr>
                ) : filtered.map(f => {
                  const centre = allCentres.find(c => c.id === f.centre_id);
                  const evidenceLink = f.flag_type === 'GHOST_BATCH'
                    ? `/ghost-batches/${f.session_id ?? ''}`
                    : f.flag_type === 'INTEGRITY_CHAIN_BREAK'
                    ? '/camera-integrity'
                    : `/centres/${f.centre_id}`;

                  return (
                    <tr
                      key={f.id}
                      onClick={() => setSelectedFlag(f.id === selectedFlag ? null : f.id)}
                      style={{
                        cursor: 'pointer',
                        background: selectedFlag === f.id ? 'rgba(111,140,255,0.08)' : undefined,
                      }}
                    >
                      <td>
                        <p className="font-medium text-sm" style={{ color: 'var(--text-primary)' }}>{centre?.name ?? f.centre_id}</p>
                        <p className="text-[10px] font-mono" style={{ color: 'var(--text-disabled)' }}>{f.id}</p>
                      </td>
                      <td>
                        <StatusChip
                          status={f.flag_type}
                          label={FLAG_TYPE_LABELS[f.flag_type] ?? f.flag_type}
                          size="xs"
                        />
                      </td>
                      <td><StatusChip status={f.severity} size="xs" /></td>
                      <td>
                        <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                          {new Date(f.created_at).toLocaleDateString('en-IN')}
                        </span>
                      </td>
                      <td><StatusChip status={f.status} size="xs" /></td>
                      <td>
                        <Link
                          to={evidenceLink}
                          className="neu-btn neu-btn-xs"
                          style={{ textDecoration: 'none' }}
                          onClick={e => e.stopPropagation()}
                        >
                          <ExternalLink size={11} /> View
                        </Link>
                      </td>
                    </tr>
                  );
                })}
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
                Click a flag to view explainability details, rules, and audit trail.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function FlagDetail({ flag }: { flag: Flag }) {
  const { data: centresData } = useCentres({ limit: 200 });
  const resolve = useResolveFlag();
  const centre = (centresData?.items ?? []).find(c => c.id === flag.centre_id);
  const [resolving, setResolving] = useState(false);

  const handleResolve = async (status: 'CLOSED_CONFIRMED' | 'CLOSED_DISMISSED') => {
    setResolving(true);
    try {
      await resolve.mutateAsync({ flagId: flag.id, body: { resolution_reason: 'Reviewed via dashboard', status } });
    } finally {
      setResolving(false);
    }
  };

  return (
    <div className="space-y-3">
      {/* Rule explanation */}
      <div className="neu-card p-4">
        <p className="section-header">Flag detail</p>
        <p className="font-semibold text-sm mb-1" style={{ color: 'var(--text-primary)' }}>{flag.id}</p>
        <p className="text-xs mb-2" style={{ color: 'var(--text-secondary)' }}>{centre?.name ?? flag.centre_id}</p>
        <div className="flex gap-2 flex-wrap mb-3">
          <StatusChip status={flag.flag_type} label={FLAG_TYPE_LABELS[flag.flag_type] ?? flag.flag_type} size="xs" />
          <StatusChip status={flag.severity} size="xs" />
          <StatusChip status={flag.status} size="xs" />
        </div>

        <div className="rule-card mb-3">
          <p className="text-xs font-semibold mb-1" style={{ color: 'var(--accent)' }}>{flag.rule_name}</p>
          <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{flag.description}</p>
        </div>

        <div className="flex items-center gap-1 text-xs mb-1" style={{ color: 'var(--text-disabled)' }}>
          <Clock size={10} />
          Created: {new Date(flag.created_at).toLocaleString('en-IN')}
        </div>
      </div>

      {/* Actions */}
      <div className="neu-card p-4 space-y-2">
        <p className="section-header">Actions</p>
        <button
          className="neu-btn w-full neu-btn-sm"
          disabled={resolving || flag.status !== 'OPEN'}
          onClick={() => handleResolve('CLOSED_CONFIRMED')}
        >
          Confirm (Close Confirmed)
        </button>
        <button
          className="neu-btn w-full neu-btn-sm neu-btn-danger"
          disabled={resolving || flag.status !== 'OPEN'}
          onClick={() => handleResolve('CLOSED_DISMISSED')}
        >
          Dismiss Flag
        </button>
        {flag.status !== 'OPEN' && (
          <p className="text-xs text-center" style={{ color: 'var(--text-disabled)' }}>Flag is already {flag.status.replace(/_/g, ' ')}</p>
        )}
      </div>

    </div>
  );
}
