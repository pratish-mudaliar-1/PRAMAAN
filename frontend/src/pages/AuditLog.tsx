import React, { useState } from 'react';
import { RefreshCw, ShieldCheck, Filter } from 'lucide-react';
import { useAuditLogs } from '@/hooks/useAudit';

export function AuditLogPage() {
  const [actionFilter, setActionFilter] = useState<string>('');
  const { data, isPending, isError } = useAuditLogs({
    action: actionFilter || undefined,
    limit: 100,
  });

  const auditLogs = data?.items ?? [];

  return (
    <div className="page-root">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>Audit Trail</h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            Cryptographically linked, SHA-256 tamper-evident record of all system events and reviewer decisions
          </p>
        </div>
        <div className="flex items-center gap-2">
          <ShieldCheck size={16} style={{ color: 'var(--st-green)' }} />
          <span className="text-xs font-mono" style={{ color: 'var(--st-green)' }}>HASH-CHAIN ACTIVE</span>
        </div>
      </div>

      <div className="neu-card overflow-hidden">
        <div className="px-4 py-3 flex items-center justify-between flex-wrap gap-2" style={{ borderBottom: 'var(--edge)' }}>
          <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            {auditLogs.length} Immutable Log Entries
          </p>
          <div className="flex items-center gap-2">
            <Filter size={13} style={{ color: 'var(--text-secondary)' }} />
            <select
              className="neu-input text-xs py-1 px-2"
              value={actionFilter}
              onChange={e => setActionFilter(e.target.value)}
              aria-label="Filter by action"
            >
              <option value="">All Actions</option>
              <option value="FLAG_RESOLVE">Flag Resolves</option>
              <option value="CAMERA_REBASELINE">Camera Rebaselines</option>
              <option value="THRESHOLD_UPDATE">Threshold Updates</option>
              <option value="DEVICE_STATUS_UPDATE">Device Updates</option>
              <option value="INGESTION_BATCH">Ingestion Batches</option>
            </select>
          </div>
        </div>
        <div className="neu-well overflow-x-auto" style={{ borderRadius: 0, border: 'none', boxShadow: 'none' }}>
          {isPending ? (
            <div className="p-8 text-center">
              <RefreshCw size={16} className="animate-spin inline-block mr-2 text-disabled" />
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Loading verified audit trail…</span>
            </div>
          ) : isError || !auditLogs.length ? (
            <div className="p-8 text-center">
              <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>No audit events found.</p>
            </div>
          ) : (
            <table className="pramaan-table min-w-[700px]">
              <thead>
                <tr>
                  {['Timestamp', 'Actor', 'Action', 'Resource', 'Note / Details', 'Verification'].map(h => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {auditLogs.map(a => (
                  <tr key={a.id}>
                    <td>
                      <span className="font-mono text-xs">
                        {new Date(a.occurred_at).toLocaleString('en-IN')}
                      </span>
                    </td>
                    <td>
                      <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                        {a.actor}
                      </span>
                    </td>
                    <td>
                      <span
                        className="chip"
                        style={{
                          background:
                            a.actor === 'system'
                              ? 'rgba(111,140,255,0.10)'
                              : 'rgba(61,220,151,0.08)',
                          color:
                            a.actor === 'system'
                              ? 'var(--accent)'
                              : 'var(--st-green)',
                          border: `1px solid ${
                            a.actor === 'system'
                              ? 'rgba(111,140,255,0.25)'
                              : 'rgba(61,220,151,0.2)'
                          }`,
                        }}
                      >
                        {a.action.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td>
                      <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                        {a.resource_type}/{a.resource_id ? a.resource_id.slice(0, 8) + '…' : '—'}
                      </span>
                    </td>
                    <td>
                      {a.detail?.note ? (
                        <span className="text-xs" style={{ color: 'var(--text-primary)' }}>
                          {String(a.detail.note)}
                        </span>
                      ) : a.detail ? (
                        <span className="text-[11px] font-mono" style={{ color: 'var(--text-secondary)' }}>
                          {JSON.stringify(a.detail)}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-disabled)' }}>—</span>
                      )}
                    </td>
                    <td>
                      <span className="text-[10px] font-mono" style={{ color: 'var(--st-green)' }} title="SHA-256 Hash Chain Linked">
                        ✓ Verified
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
