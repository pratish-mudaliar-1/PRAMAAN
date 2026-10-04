import React, { useState } from 'react';
import { Info, Save } from 'lucide-react';
import { MOCK_THRESHOLDS } from '@/api/mockData';

export function SettingsPage() {
  const [thresholds, setThresholds] = useState(MOCK_THRESHOLDS.map(t => ({ ...t })));
  const [saved, setSaved] = useState(false);

  const update = (key: string, value: number) => {
    setSaved(false);
    setThresholds(prev => prev.map(t => t.key === key ? { ...t, value } : t));
  };

  const save = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  const groups = [
    { label: 'Attendance reconciliation', prefix: 'attendance.' },
    { label: 'Camera integrity',          prefix: 'camera.'     },
    { label: 'Ghost batch detection',     prefix: 'ghost.'      },
  ];

  return (
    <div className="page-root">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Settings &amp; Thresholds
          </h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            All thresholds are initial hypotheses — calibrate on pilot data
          </p>
        </div>
        <span className="simulated-badge">SIMULATED DATA</span>
      </div>

      {/* Honesty notice */}
      <div className="neu-alert-amber">
        <Info size={14} style={{ color: 'var(--st-amber)', flexShrink: 0, marginTop: 2 }} />
        <div>
          <p className="text-sm font-semibold" style={{ color: 'var(--st-amber)' }}>
            Initial hypotheses — calibrate on pilot
          </p>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            These thresholds have not been validated against real training-centre data.
            Changes are logged in the audit trail. Do not treat any threshold as a proven threshold.
          </p>
        </div>
      </div>

      {groups.map(g => (
        <div key={g.prefix} className="neu-card overflow-hidden">
          <div className="px-4 py-3" style={{ borderBottom: 'var(--edge)' }}>
            <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{g.label}</p>
          </div>
          <div className="p-4 space-y-5">
            {thresholds.filter(t => t.key.startsWith(g.prefix)).map(t => (
              <div key={t.key}>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{t.label}</label>
                  <span className="font-mono text-sm" style={{ color: 'var(--accent)' }}>{t.value}</span>
                </div>
                <div className="neu-well-sm p-3">
                  <input
                    type="range"
                    min={t.value < 1 ? 0 : 1}
                    max={t.value < 1 ? 1 : 100}
                    step={t.value < 1 ? 0.05 : 1}
                    value={t.value}
                    onChange={e => update(t.key, parseFloat(e.target.value))}
                    style={{
                      width: '100%',
                      accentColor: 'var(--accent)',
                      background: 'transparent',
                    }}
                    aria-label={t.label}
                  />
                  <p className="text-xs mt-2" style={{ color: 'var(--text-secondary)' }}>
                    {t.hypothesis_note}
                  </p>
                  <p className="text-[10px] font-mono mt-1" style={{ color: 'var(--text-disabled)' }}>
                    Last modified: {t.modified_by} · {new Date(t.modified_at).toLocaleDateString('en-IN')}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* Save button */}
      <div className="flex items-center gap-3">
        <button className="neu-btn neu-btn-primary" onClick={save}>
          <Save size={14} /> Save thresholds
        </button>
        {saved && (
          <span className="text-sm animate-fade-in" style={{ color: 'var(--st-green)' }}>
            ✓ Saved (demo only — no persistence)
          </span>
        )}
        <p className="text-xs" style={{ color: 'var(--text-disabled)' }}>
          All changes are recorded in the audit log.
        </p>
      </div>
    </div>
  );
}
