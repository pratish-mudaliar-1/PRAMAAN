import React, { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Info, AlertTriangle, ArrowUp } from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Cell, ReferenceLine,
} from 'recharts';
import { MOCK_GHOST_EVALUATIONS, MOCK_BATCHES } from '@/api/mockData';
import { StatusChip } from '@/components/status/StatusChip';

const INDICATORS = [
  { key: 'i1_persistent_shortfall', label: 'I1 — Persistent shortfall', desc: 'Share of sessions with ratio < 0.50', weight: 0.40 },
  { key: 'i2_near_zero',            label: 'I2 — Near-zero occupancy',  desc: 'Observed ≤ 10% of claimed',           weight: 0.20 },
  { key: 'i3_claim_uniformity',     label: 'I3 — Claim uniformity',     desc: 'Near-constant claimed count',          weight: 0.15 },
  { key: 'i4_out_of_schedule',      label: 'I4 — Out-of-schedule',      desc: 'Claims outside scheduled hours',       weight: 0.10 },
  { key: 'i5_room_overlap',         label: 'I5 — Room overlap',         desc: 'Two batches claiming same room/time',  weight: 0.10 },
  { key: 'i6_trend',                label: 'I6 — Trend divergence',     desc: 'Claims rising, observed falling',      weight: 0.05 },
] as const;

function ghostStatusChip(status: string) {
  const m: Record<string, { cls: string; label: string }> = {
    CLEAR:           { cls: 'chip-clear',    label: 'Clear'            },
    WATCH:           { cls: 'chip-watch',    label: 'Watch'            },
    SUSPECTED_GHOST: { cls: 'chip-ghost',    label: 'Suspected ghost'  },
    ESCALATED:       { cls: 'chip-escalated', label: 'Escalated'      },
  };
  const d = m[status] ?? { cls: 'chip-nodata', label: status };
  return <span className={`chip ${d.cls}`}>{d.label}</span>;
}

function ScoreDial({ score }: { score: number }) {
  const r = 52;
  const circ = 2 * Math.PI * r;
  const fill = circ * (1 - score / 100);
  const color = score >= 60 ? 'var(--st-ghost)' : score >= 30 ? 'var(--st-amber)' : 'var(--st-green)';

  return (
    <div className="neu-card p-4 flex flex-col items-center">
      <p className="section-header w-full">Ghost Score</p>
      <svg width={128} height={128} viewBox="0 0 128 128" aria-label={`Ghost score: ${score} out of 100`}>
        <circle className="score-track" cx={64} cy={64} r={r} strokeWidth={10} />
        <circle
          className="score-fill"
          cx={64} cy={64} r={r}
          strokeWidth={10}
          stroke={color}
          strokeDasharray={circ}
          strokeDashoffset={fill}
          transform="rotate(-90 64 64)"
        />
        <text x={64} y={64} textAnchor="middle" dy="0.35em"
          style={{ fill: color, fontFamily: 'var(--font-mono)', fontSize: 26, fontWeight: 700 }}>
          {score}
        </text>
        <text x={64} y={88} textAnchor="middle"
          style={{ fill: 'var(--text-disabled)', fontFamily: 'var(--font-ui)', fontSize: 10 }}>
          / 100
        </text>
      </svg>
      <p className="text-xs text-center mt-1" style={{ color }}>
        {score >= 60 ? 'SUSPECTED GHOST' : score >= 30 ? 'WATCH' : 'CLEAR'}
      </p>
      <p className="text-[10px] text-center mt-1" style={{ color: 'var(--text-disabled)' }}>
        Initial hypothesis — calibrate on pilot
      </p>
    </div>
  );
}

function BatchDetail({ evalId }: { evalId: string }) {
  const evaluation = MOCK_GHOST_EVALUATIONS.find(e => e.id === evalId);
  if (!evaluation) return null;
  const batch = MOCK_BATCHES.find(b => b.id === evaluation.batch_id);

  const indData = INDICATORS.map(ind => ({
    name: ind.label.slice(0, 18),
    value: (evaluation.indicators[ind.key as keyof typeof evaluation.indicators] * 100),
    label: ind.label,
    desc: ind.desc,
    weight: ind.weight,
  }));

  const [tcNote, setTcNote]         = useState('');
  const [acknowledged, setAcknowledged] = useState(false);

  const explanations = [
    'Trainees present but outside camera view',
    'Session temporarily moved to another room',
    'Camera coverage gap (partial zone)',
    'Field trip day — off-site activity',
  ];

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header */}
      <div className="neu-card p-4">
        <div className="flex items-start justify-between flex-wrap gap-2">
          <div>
            <p className="font-bold" style={{ color: 'var(--text-primary)' }}>
              {batch?.trade ?? evaluation.batch_id}
            </p>
            <p className="text-xs font-mono mt-0.5" style={{ color: 'var(--text-disabled)' }}>
              {evaluation.batch_id} · {evaluation.valid_sessions} valid sessions
            </p>
          </div>
          {ghostStatusChip(evaluation.status)}
        </div>
        <p className="text-xs mt-2" style={{ color: 'var(--text-secondary)' }}>
          Evaluated {new Date(evaluation.evaluated_at).toLocaleDateString('en-IN')} ·
          Window: {new Date(evaluation.window_start).toLocaleDateString('en-IN')} —{' '}
          {new Date(evaluation.window_end).toLocaleDateString('en-IN')}
        </p>
        {evaluation.valid_sessions < 5 && (
          <div className="neu-alert-info mt-3">
            <Info size={13} style={{ color: 'var(--accent)', flexShrink: 0 }} />
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Insufficient evidence — fewer than 5 valid sessions. No ghost verdict possible.
            </p>
          </div>
        )}
      </div>

      {/* Score dial + breakdown */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <ScoreDial score={evaluation.ghost_score} />

        <div className="neu-card p-4">
          <p className="section-header">Score breakdown</p>
          <div className="neu-well-sm p-2" style={{ height: 180 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={indData} layout="vertical" margin={{ left: 0, right: 10 }}>
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10 }} />
                <YAxis dataKey="name" type="category" width={80} tick={{ fontSize: 9, fill: 'var(--text-secondary)' }} />
                <CartesianGrid strokeDasharray="2 2" />
                <Tooltip
                  content={({ active, payload }) => active && payload?.length ? (
                    <div className="pramaan-tooltip">
                      <p style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{payload[0]?.payload?.label}</p>
                      <p style={{ color: 'var(--text-secondary)', fontSize: '0.7rem' }}>{payload[0]?.payload?.desc}</p>
                      <p style={{ color: 'var(--accent)' }}>Score: {payload[0]?.value?.toFixed(0)}/100 · Weight: {(payload[0]?.payload?.weight * 100).toFixed(0)}%</p>
                    </div>
                  ) : null}
                />
                <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                  {indData.map((d, i) => (
                    <Cell key={i} fill={d.value > 60 ? 'var(--st-ghost)' : d.value > 30 ? 'var(--st-amber)' : 'var(--accent)'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Indicator plain-language */}
      <div className="neu-card p-4">
        <p className="section-header">Plain-language summary</p>
        <div className="space-y-2">
          {INDICATORS.map(ind => {
            const val = evaluation.indicators[ind.key as keyof typeof evaluation.indicators];
            return (
              <div key={ind.key} className="flex items-start gap-2 p-2 rounded-[8px]"
                style={{ background: val > 0.6 ? 'rgba(255,159,107,0.06)' : 'transparent', border: val > 0.6 ? '1px solid rgba(255,159,107,0.2)' : '1px solid transparent' }}>
                <span className="font-mono text-xs shrink-0 mt-0.5" style={{ color: 'var(--accent)' }}>{ind.label.slice(0, 2)}</span>
                <div>
                  <p className="text-xs" style={{ color: 'var(--text-primary)' }}>
                    {ind.desc} — score: <span className="font-mono">{(val * 100).toFixed(0)}/100</span>
                    {' '}(weight: {(ind.weight * 100).toFixed(0)}%)
                  </p>
                  {ind.key === 'i1_persistent_shortfall' && val > 0.6 && (
                    <p className="text-xs mt-0.5" style={{ color: 'var(--st-ghost)' }}>
                      In {Math.round(val * evaluation.valid_sessions)} of {evaluation.valid_sessions} valid sessions, observed was under half of claimed.
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Fairness panel */}
      <div className="neu-card p-4">
        <p className="section-header">Fairness: possible innocent explanations</p>
        <p className="text-xs mb-3" style={{ color: 'var(--text-secondary)' }}>
          Reviewer must acknowledge these before escalating.
        </p>
        <div className="space-y-2">
          {explanations.map((e, i) => (
            <label key={i} className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" style={{ accentColor: 'var(--accent)' }} />
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{e}</span>
            </label>
          ))}
        </div>
        <label className="flex items-center gap-2 mt-3 cursor-pointer">
          <input type="checkbox" checked={acknowledged} onChange={e => setAcknowledged(e.target.checked)} style={{ accentColor: 'var(--accent)' }} />
          <span className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
            I have considered all possible explanations
          </span>
        </label>
      </div>

      {/* TC response + actions */}
      <div className="neu-card p-4 space-y-2">
        <p className="section-header">TC response box</p>
        <textarea
          className="neu-input"
          style={{ minHeight: 72, resize: 'vertical' }}
          placeholder="Training Centre explanation…"
          value={tcNote}
          onChange={e => setTcNote(e.target.value)}
          aria-label="TC response"
        />
        <div className="grid grid-cols-2 gap-2">
          <button className="neu-btn neu-btn-sm">Add to watchlist</button>
          <button className="neu-btn neu-btn-sm">Request inspection</button>
          <button className="neu-btn neu-btn-sm">Request TC explanation</button>
          <button
            className={`neu-btn neu-btn-sm ${acknowledged ? 'neu-btn-danger' : ''}`}
            disabled={!acknowledged}
            style={!acknowledged ? { opacity: 0.4, cursor: 'not-allowed' } : {}}
          >
            <ArrowUp size={13} /> Escalate
          </button>
        </div>
        {!acknowledged && (
          <p className="text-xs" style={{ color: 'var(--text-disabled)' }}>
            Escalation requires acknowledging the fairness checklist above.
          </p>
        )}
      </div>
    </div>
  );
}

export function GhostBatchesPage() {
  const { batchId: paramId } = useParams<{ batchId?: string }>();
  const [selectedEval, setSelectedEval] = useState<string | null>(
    paramId ? MOCK_GHOST_EVALUATIONS.find(e => e.batch_id === paramId)?.id ?? null : null
  );

  return (
    <div className="page-root">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>Ghost Batches</h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            Multi-day pattern detection · Rule-based · Transparent indicators
          </p>
        </div>
        <span className="simulated-badge">SIMULATED DATA</span>
      </div>

      {/* Principle note */}
      <div className="neu-alert-info">
        <Info size={14} style={{ color: 'var(--accent)', flexShrink: 0, marginTop: 2 }} />
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          No ghost verdict with &lt; 5 valid sessions or &lt; 3 distinct evidence days.
          Sessions marked NO-DATA, PENDING or EVIDENCE_COMPROMISED are excluded from evaluation.
          Ghost Score is transparent and rule-based — no black-box model.
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
        {/* Batch list */}
        <div className="xl:col-span-2 neu-card overflow-hidden">
          <div className="px-4 py-3" style={{ borderBottom: 'var(--edge)' }}>
            <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Ghost batch evaluations</p>
          </div>
          <div className="neu-well overflow-x-auto" style={{ borderRadius: 0, border: 'none', boxShadow: 'none' }}>
            <table className="pramaan-table pramaan-table-clickable min-w-[380px]">
              <thead>
                <tr>
                  {['Batch', 'Status', 'Score', 'Valid sessions'].map(h => <th key={h}>{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {MOCK_GHOST_EVALUATIONS.sort((a, b) => b.ghost_score - a.ghost_score).map(ev => {
                  const batch = MOCK_BATCHES.find(b => b.id === ev.batch_id);
                  return (
                    <tr
                      key={ev.id}
                      onClick={() => setSelectedEval(ev.id === selectedEval ? null : ev.id)}
                      style={{
                        cursor: 'pointer',
                        background: selectedEval === ev.id ? 'rgba(111,140,255,0.08)' : undefined,
                      }}
                    >
                      <td>
                        <p className="font-medium text-sm" style={{ color: 'var(--text-primary)' }}>
                          {batch?.trade ?? ev.batch_id}
                        </p>
                        <p className="text-[10px] font-mono" style={{ color: 'var(--text-disabled)' }}>{ev.batch_id}</p>
                      </td>
                      <td>{ghostStatusChip(ev.status)}</td>
                      <td>
                        <span className="font-mono font-bold" style={{
                          color: ev.ghost_score >= 60 ? 'var(--st-ghost)' : ev.ghost_score >= 30 ? 'var(--st-amber)' : 'var(--st-green)',
                        }}>
                          {ev.ghost_score}
                        </span>
                      </td>
                      <td>
                        <span className="font-mono text-xs">{ev.valid_sessions}</span>
                        {ev.valid_sessions < 5 && (
                          <span className="ml-1 chip chip-pending" style={{ fontSize: '0.6rem', padding: '1px 4px' }}>insuff.</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Detail panel */}
        <div className="xl:col-span-3">
          {selectedEval
            ? <BatchDetail evalId={selectedEval} />
            : (
              <div className="neu-well p-8 text-center">
                <p style={{ color: 'var(--text-disabled)' }}>
                  Select a batch to see Ghost Score, indicator breakdown, evidence and fairness panel.
                </p>
              </div>
            )}
        </div>
      </div>
    </div>
  );
}
