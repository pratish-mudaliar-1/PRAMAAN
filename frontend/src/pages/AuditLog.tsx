import React from 'react';
import { MOCK_AUDIT } from '@/api/mockData';

export function AuditLogPage() {
  return (
    <div className="page-root">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>Audit Log</h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            Tamper-evident record of all system and reviewer actions
          </p>
        </div>
        <span className="simulated-badge">SIMULATED DATA</span>
      </div>

      <div className="neu-card overflow-hidden">
        <div className="px-4 py-3" style={{ borderBottom: 'var(--edge)' }}>
          <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            {MOCK_AUDIT.length} audit events
          </p>
        </div>
        <div className="neu-well overflow-x-auto" style={{ borderRadius: 0, border: 'none', boxShadow: 'none' }}>
          <table className="pramaan-table min-w-[700px]">
            <thead>
              <tr>
                {['Timestamp', 'Actor', 'Action', 'Entity', 'Note'].map(h => <th key={h}>{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {[...MOCK_AUDIT].reverse().map(a => (
                <tr key={a.id}>
                  <td><span className="font-mono text-xs">{new Date(a.ts).toLocaleString('en-IN')}</span></td>
                  <td><span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{a.actor}</span></td>
                  <td>
                    <span
                      className="chip"
                      style={{
                        background: a.actor === 'system' ? 'rgba(111,140,255,0.10)' : 'rgba(61,220,151,0.08)',
                        color: a.actor === 'system' ? 'var(--accent)' : 'var(--st-green)',
                        border: `1px solid ${a.actor === 'system' ? 'rgba(111,140,255,0.25)' : 'rgba(61,220,151,0.2)'}`,
                      }}
                    >
                      {a.action.replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td>
                    <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                      {a.entity_type}/{a.entity_id}
                    </span>
                  </td>
                  <td>
                    {a.note
                      ? <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{a.note}</span>
                      : <span style={{ color: 'var(--text-disabled)' }}>—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
