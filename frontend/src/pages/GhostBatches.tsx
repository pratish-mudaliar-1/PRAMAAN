import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Info, ArrowUp, RefreshCw, CheckCircle, ShieldAlert,
  ExternalLink, ChevronRight, Building2
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Cell,
} from 'recharts';
import { useGhostAssessments, useBatches } from '@/hooks/useGhost';
import { getCentreGhostRollup, reevaluateGhostBatch } from '@/api/ghost';
import { useCreateCase } from '@/hooks/useCases';
import { StatusChip } from '@/components/status/StatusChip';
import type { GhostStatus, GhostEvaluation } from '@/types';

const INDICATORS = [
  { key: 'persistence',      label: 'Persistence / निरंतरता',        desc: 'Fraction of eligible days with attendance deficit', weight: 0.35 },
  { key: 'magnitude',        label: 'Gap Magnitude / अंतर की गहराई',   desc: 'Depth of shortfall below red threshold',   weight: 0.30 },
  { key: 'consistency',      label: 'Claim Uniformity / दावा एकरूपता', desc: 'Artificial constancy in claimed counts',   weight: 0.20 },
  { key: 'evidence_quality', label: 'Evidence Quality / साक्ष्य गुणवत्ता', desc: 'Fraction of window with trusted valid data', weight: 0.15 },
] as const;

function ghostStatusChip(status: GhostStatus) {
  return <StatusChip status={status} size="xs" />;
}

function ScoreDial({ score }: { score: number }) {
  const r = 52;
  const circ = 2 * Math.PI * r;
  const fill = circ * (1 - score / 100);
  const color = score >= 60 ? 'var(--st-ghost)' : score >= 30 ? 'var(--st-amber)' : 'var(--st-green)';

  return (
    <div className="neu-card p-4 flex flex-col items-center">
      <div className="w-full flex items-center justify-between mb-1">
        <p className="section-header">Ghost Score / भूत-बैच स्कोर</p>
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-black/20 font-mono">0–100</span>
      </div>
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
          {score.toFixed(0)}
        </text>
        <text x={64} y={88} textAnchor="middle"
          style={{ fill: 'var(--text-disabled)', fontFamily: 'var(--font-ui)', fontSize: 10 }}>
          / 100
        </text>
      </svg>
      <p className="text-xs text-center mt-1 font-semibold uppercase tracking-wider" style={{ color }}>
        {score >= 60 ? 'SUSPECTED GHOST / संदिग्ध' : score >= 30 ? 'WATCH / निगरानी' : 'NORMAL / सामान्य'}
      </p>
      <p className="text-[10px] text-center mt-1" style={{ color: 'var(--text-disabled)' }}>
        Deterministic rule-based component score
      </p>
    </div>
  );
}

/* ── Multi-Day Table (clearly separates GHOST, NO_DATA, UNTRUSTED) ── */
function MultiDayBreakdownTable({ days }: { days: any[] }) {
  if (!days || days.length === 0) {
    return (
      <div className="neu-well p-4 text-center text-xs" style={{ color: 'var(--text-disabled)' }}>
        No day-by-day telemetry recorded yet.
      </div>
    );
  }

  return (
    <div className="neu-card p-4">
      <div className="flex items-center justify-between mb-2">
        <div>
          <p className="section-header">Multi-Day Attendance Evaluation / बहु-दिवसीय विश्लेषण</p>
          <p className="text-xs" style={{ color: 'var(--text-disabled)' }}>
            NO_DATA and UNTRUSTED days are excluded from denominator · Never shown as student violations
          </p>
        </div>
        <div className="flex gap-2 text-[10px] font-mono">
          <span className="px-1.5 py-0.5 rounded bg-red-500/20 text-red-300">GHOST</span>
          <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300">HEALTHY</span>
          <span className="px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300">UNTRUSTED (Camera)</span>
          <span className="px-1.5 py-0.5 rounded bg-gray-500/20 text-gray-300">NO_DATA</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="pramaan-table min-w-[550px]" role="grid">
          <thead>
            <tr>
              <th>Date (IST)</th>
              <th>Status / स्थिति</th>
              <th>Claimed / दावा</th>
              <th>Observed Ô</th>
              <th>Ratio / अनुपात</th>
              <th>Evidence Quality</th>
              <th>Interpretation</th>
            </tr>
          </thead>
          <tbody>
            {days.map((d: any, idx: number) => {
              const isGhost = d.status === 'GHOST';
              const isUntrusted = d.status === 'UNTRUSTED';
              const isNoData = d.status === 'NO_DATA';

              const badgeStyle = isGhost
                ? { background: 'rgba(255,107,107,0.18)', color: 'var(--st-red)', border: '1px solid rgba(255,107,107,0.3)' }
                : isUntrusted
                ? { background: 'rgba(255,122,217,0.18)', color: 'var(--st-swap)', border: '1px solid rgba(255,122,217,0.3)' }
                : isNoData
                ? { background: 'rgba(148,163,184,0.15)', color: 'var(--text-disabled)', border: '1px solid rgba(148,163,184,0.2)' }
                : { background: 'rgba(74,222,128,0.15)', color: 'var(--st-green)', border: '1px solid rgba(74,222,128,0.25)' };

              return (
                <tr key={idx} style={{ background: isGhost ? 'rgba(255,107,107,0.03)' : undefined }}>
                  <td className="font-mono text-xs">{d.date}</td>
                  <td>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wide" style={badgeStyle}>
                      {d.status}
                    </span>
                  </td>
                  <td className="font-mono text-xs font-semibold">{d.claimed}</td>
                  <td className="font-mono text-xs">{d.o_hat != null ? d.o_hat.toFixed(1) : '—'}</td>
                  <td>
                    <span
                      className="font-mono text-xs font-bold"
                      style={{
                        color:
                          d.ratio == null
                            ? 'var(--text-disabled)'
                            : d.ratio < 0.20
                            ? 'var(--st-red)'
                            : d.ratio < 0.50
                            ? 'var(--st-amber)'
                            : 'var(--st-green)',
                      }}
                    >
                      {d.ratio != null ? `${(d.ratio * 100).toFixed(0)}%` : '—'}
                    </span>
                  </td>
                  <td className="font-mono text-xs">
                    {d.evidence_quality != null ? `${(d.evidence_quality * 100).toFixed(0)}%` : '—'}
                  </td>
                  <td className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                    {isUntrusted ? (
                      <span className="text-pink-400 font-semibold">Camera Untrusted — Excluded</span>
                    ) : isNoData ? (
                      <span className="text-gray-400">Feed gap / Excluded</span>
                    ) : isGhost ? (
                      <span className="text-red-400 font-semibold">Shortfall (&lt;20%)</span>
                    ) : (
                      <span className="text-emerald-400">Regular presence</span>
                    )}
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

function BatchDetail({
  evaluation,
  batchTrade,
}: {
  evaluation: GhostEvaluation;
  batchTrade?: string;
}) {
  const createCaseMutation = useCreateCase();
  const [tcNote, setTcNote] = useState('');
  const [acknowledged, setAcknowledged] = useState(false);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);
  const [isReevaluating, setIsReevaluating] = useState(false);

  const explanationObj = (evaluation.explanation as Record<string, any>) || {};
  const cameraIntegrityExplains = explanationObj.camera_integrity_explains || (evaluation.untrusted_days > 0 && evaluation.ghost_days === 0);

  const indData = INDICATORS.map(ind => {
    const raw = Number(explanationObj[ind.key] ?? 0);
    return {
      name: ind.label,
      value: Math.round(raw * 100),
      label: ind.label,
      desc: ind.desc,
      weight: ind.weight,
    };
  });

  const explanations = [
    'Trainees present but outside camera view / छात्र कैमरे की दृष्टि से बाहर',
    'Session temporarily moved to another room / कक्षा अन्य कक्ष में स्थानांतरित',
    'Camera coverage gap (partial zone) / आंशिक क्षेत्र कवरेज',
    'Field trip day — off-site practical / क्षेत्र भ्रमण या व्यावहारिक प्रशिक्षण',
  ];

  const handleEscalate = async () => {
    if (!acknowledged) return;
    try {
      const res = await createCaseMutation.mutateAsync({
        centre_id: evaluation.centre_id,
        title: `Ghost Batch Escalation: ${batchTrade || evaluation.batch_id}`,
        description: `Formal case initiated from Ghost Evaluation ${evaluation.id} with score ${evaluation.ghost_score.toFixed(1)}/100. TC Note: ${tcNote || 'None provided'}.`,
        priority: evaluation.ghost_score > 60 ? 'HIGH' : 'MEDIUM',
      });
      setActionFeedback(`Case ${res.case_number} created successfully.`);
      setTimeout(() => setActionFeedback(null), 5000);
    } catch (e: any) {
      setActionFeedback(`Escalation failed: ${e?.detail || e?.message || 'Error'}`);
    }
  };

  const handleReevaluate = async () => {
    setIsReevaluating(true);
    try {
      await reevaluateGhostBatch(evaluation.batch_id);
      setActionFeedback('Batch re-evaluated against latest attendance & keyframe observations.');
      setTimeout(() => setActionFeedback(null), 5000);
    } catch (e: any) {
      setActionFeedback(`Re-evaluation failed: ${e?.message || 'Error'}`);
    } finally {
      setIsReevaluating(false);
    }
  };

  const perDayDetail = (evaluation as any).per_day_detail || [];

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header */}
      <div className="neu-card p-4">
        <div className="flex items-start justify-between flex-wrap gap-2">
          <div>
            <div className="flex items-center gap-2">
              <p className="font-bold text-base" style={{ color: 'var(--text-primary)' }}>
                {batchTrade ?? (evaluation as any).batch_trade ?? evaluation.batch_id}
              </p>
              <span className="text-[11px] px-2 py-0.5 rounded-full" style={{ background: 'rgba(255,159,107,0.15)', color: 'var(--st-ghost)' }}>
                Lead for Human Review / समीक्षा हेतु संकेत
              </span>
            </div>
            <p className="text-xs font-mono mt-0.5" style={{ color: 'var(--text-disabled)' }}>
              Batch ID: {evaluation.batch_id.slice(0, 12)}… · {evaluation.eligible_days} eligible days ({evaluation.ghost_days} ghost days)
            </p>
          </div>
          <div className="flex items-center gap-2">
            {ghostStatusChip(evaluation.state)}
            <button
              className="neu-btn neu-btn-sm"
              onClick={handleReevaluate}
              disabled={isReevaluating}
              title="Re-evaluate with late attendance or evidence telemetry"
            >
              <RefreshCw size={12} className={isReevaluating ? 'animate-spin inline mr-1' : 'inline mr-1'} />
              Re-evaluate
            </button>
          </div>
        </div>

        {actionFeedback && (
          <div className="neu-alert-info mt-3">
            <CheckCircle size={14} style={{ color: 'var(--accent)', flexShrink: 0 }} />
            <p className="text-xs font-semibold" style={{ color: 'var(--accent)' }}>{actionFeedback}</p>
          </div>
        )}

        {/* Camera Integrity Explanation Banner */}
        {cameraIntegrityExplains && (
          <div className="neu-alert-info mt-3 p-3 rounded-lg border border-purple-500/30" style={{ background: 'rgba(216,180,254,0.08)' }}>
            <div className="flex items-start gap-2">
              <ShieldAlert size={16} className="text-purple-400 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs font-bold text-purple-300">
                  Integrity Concern Explains Low Occupancy / कैमरा अखंडता मामला
                </p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                  Missing physical occupancy coincides with an <strong>UNTRUSTED CAMERA</strong> state.
                  PRAMAAN treats this as a camera integrity incident, <strong>never as an attendance penalty</strong> or ghost accusation.
                </p>
                <Link
                  to="/cameras"
                  className="inline-flex items-center gap-1 text-xs text-accent hover:underline mt-1 font-semibold"
                >
                  View Camera Integrity Console <ExternalLink size={11} />
                </Link>
              </div>
            </div>
          </div>
        )}

        <p className="text-xs mt-2" style={{ color: 'var(--text-secondary)' }}>
          Evaluated {new Date((evaluation as any).computed_at || evaluation.evaluated_at).toLocaleDateString('en-IN')} ·
          Window: {new Date(evaluation.window_start).toLocaleDateString('en-IN')} — {new Date(evaluation.window_end).toLocaleDateString('en-IN')}
        </p>

        {evaluation.eligible_days < 2 && (
          <div className="neu-alert-info mt-3">
            <Info size={13} style={{ color: 'var(--accent)', flexShrink: 0 }} />
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Insufficient evidence — fewer than 2 eligible days. No ghost verdict can be made.
            </p>
          </div>
        )}
      </div>

      {/* Multi-Day Evaluation Table */}
      <MultiDayBreakdownTable days={perDayDetail} />

      {/* Score dial + breakdown */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <ScoreDial score={evaluation.ghost_score ? evaluation.ghost_score * 100 : 0} />

        <div className="neu-card p-4">
          <p className="section-header">Score Breakdown / घटक विश्लेषण</p>
          <div className="neu-well-sm p-2" style={{ height: 180 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={indData} layout="vertical" margin={{ left: 0, right: 10 }}>
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10 }} />
                <YAxis dataKey="name" type="category" width={95} tick={{ fontSize: 8.5, fill: 'var(--text-secondary)' }} />
                <CartesianGrid strokeDasharray="2 2" />
                <Tooltip
                  content={({ active, payload }) => active && payload?.length ? (
                    <div className="pramaan-tooltip">
                      <p style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{payload[0]?.payload?.label}</p>
                      <p style={{ color: 'var(--text-secondary)', fontSize: '0.7rem' }}>{payload[0]?.payload?.desc}</p>
                      <p style={{ color: 'var(--accent)' }}>Score: {Number(payload[0]?.value ?? 0).toFixed(0)}/100 · Weight: {(payload[0]?.payload?.weight * 100).toFixed(0)}%</p>
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

      {/* State Machine Transition Timeline */}
      <div className="neu-card p-4">
        <p className="section-header">State Lifecycle & Hysteresis / स्थिति जीवनचक्र</p>
        <div className="flex items-center gap-2 mt-2 text-xs">
          {['NORMAL', 'WATCH', 'SUSPECTED_GHOST', 'ESCALATED', 'RESOLVED'].map((st, i) => {
            const isActive = evaluation.state === st;
            return (
              <React.Fragment key={st}>
                {i > 0 && <ChevronRight size={12} className="text-gray-500" />}
                <span
                  className={`px-2 py-1 rounded font-mono text-[11px] ${
                    isActive ? 'font-bold ring-1 ring-accent' : 'opacity-40'
                  }`}
                  style={{
                    background: isActive ? 'rgba(111,140,255,0.15)' : 'transparent',
                    color: isActive ? 'var(--text-primary)' : 'var(--text-disabled)',
                  }}
                >
                  {st}
                </span>
              </React.Fragment>
            );
          })}
        </div>
        <p className="text-[11px] mt-2" style={{ color: 'var(--text-disabled)' }}>
          Recovery requires {3} consecutive healthy eligible days to transition to RESOLVED.
        </p>
      </div>

      {/* Fairness checklist */}
      <div className="neu-card p-4">
        <p className="section-header">Fairness Checklist / निष्पक्षता सत्यापन</p>
        <p className="text-xs mb-3" style={{ color: 'var(--text-secondary)' }}>
          Reviewers must consider innocent explanations before escalating to formal investigation.
        </p>
        <div className="space-y-2">
          {explanations.map((e, i) => (
            <label key={i} className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" style={{ accentColor: 'var(--accent)' }} />
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{e}</span>
            </label>
          ))}
        </div>
        <label className="flex items-center gap-2 mt-3 cursor-pointer pt-2 border-t border-white/5">
          <input
            type="checkbox"
            checked={acknowledged}
            onChange={e => setAcknowledged(e.target.checked)}
            style={{ accentColor: 'var(--accent)' }}
          />
          <span className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
            I have reviewed the evidence and confirmed these explanations do not apply / मैंने सत्यापन किया है
          </span>
        </label>
      </div>

      {/* Notes & Actions */}
      <div className="neu-card p-4 space-y-2">
        <p className="section-header">Reviewer & Centre Response Notes</p>
        <textarea
          className="neu-input"
          style={{ minHeight: 72, resize: 'vertical' }}
          placeholder="Enter investigation notes or TC explanation to attach to the case…"
          value={tcNote}
          onChange={e => setTcNote(e.target.value)}
          aria-label="TC response"
        />
        <div className="flex gap-2 justify-end">
          <button
            className={`neu-btn neu-btn-sm ${acknowledged ? 'neu-btn-danger' : ''}`}
            disabled={!acknowledged || createCaseMutation.isPending}
            onClick={handleEscalate}
            style={!acknowledged ? { opacity: 0.4, cursor: 'not-allowed' } : {}}
          >
            <ArrowUp size={13} className={createCaseMutation.isPending ? 'animate-spin inline mr-1' : 'inline mr-1'} />
            {createCaseMutation.isPending ? 'Escalating…' : 'Escalate to Formal Case / औपचारिक प्रकरण बनाएं'}
          </button>
        </div>
      </div>
    </div>
  );
}

export function GhostBatchesPage() {
  const { batchId: paramId } = useParams<{ batchId?: string }>();
  const [selectedEvalId, setSelectedEvalId] = useState<string | null>(null);
  const [centreRollup, setCentreRollup] = useState<any | null>(null);

  const { data: ghostData, isPending, isError } = useGhostAssessments({ limit: 100 });
  const { data: batchesData } = useBatches({ limit: 100 });

  const evaluations = ghostData?.items ?? [];
  const batches = batchesData?.items ?? [];

  // Match default selected
  const activeEval = evaluations.find(e =>
    selectedEvalId ? e.id === selectedEvalId : paramId ? e.batch_id === paramId : true
  );

  // Fetch centre rollup if evaluation has centre_id
  useEffect(() => {
    if (activeEval?.centre_id) {
      getCentreGhostRollup(activeEval.centre_id)
        .then(setCentreRollup)
        .catch(() => setCentreRollup(null));
    }
  }, [activeEval?.centre_id]);

  return (
    <div className="page-root">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Ghost Batches / भूत-बैच पहचान
          </h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            Multi-day attendance reconciliation · Lead for human review · Transparent indicators
          </p>
        </div>
      </div>

      {/* Mandatory Regulatory Principle Banner */}
      <div className="neu-alert-info">
        <Info size={14} style={{ color: 'var(--accent)', flexShrink: 0, marginTop: 2 }} />
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          <strong style={{ color: 'var(--text-primary)' }}>Lead for Human Review / मानवीय समीक्षा के लिए संकेत:</strong>
          {' '}Ghost batch detection is an analytical indicator for supervisory inspection, never an automatic penalty.
          Days with NO_DATA or UNTRUSTED cameras are excluded from the evaluation denominator.
        </p>
      </div>

      {/* Centre Rollup Card if available */}
      {centreRollup && (
        <div className="neu-card p-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <Building2 size={16} className="text-accent" />
              <p className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>
                Centre Rollup: {centreRollup.centre_name}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Rollup Ghost Risk:</span>
              <span className="font-mono text-sm font-bold" style={{
                color: centreRollup.centre_ghost_risk_score > 0.5 ? 'var(--st-red)' : 'var(--st-green)'
              }}>
                {(centreRollup.centre_ghost_risk_score * 100).toFixed(1)}%
              </span>
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mt-3 text-center">
            <div className="p-2 rounded bg-black/20">
              <p className="text-[10px] text-gray-400">Total Batches</p>
              <p className="font-mono text-sm font-bold mt-0.5">{centreRollup.total_batches}</p>
            </div>
            <div className="p-2 rounded bg-black/20">
              <p className="text-[10px] text-emerald-400">Normal</p>
              <p className="font-mono text-sm font-bold mt-0.5 text-emerald-400">{centreRollup.normal_batches}</p>
            </div>
            <div className="p-2 rounded bg-black/20">
              <p className="text-[10px] text-amber-400">Watch</p>
              <p className="font-mono text-sm font-bold mt-0.5 text-amber-400">{centreRollup.watch_batches}</p>
            </div>
            <div className="p-2 rounded bg-black/20">
              <p className="text-[10px] text-red-400">Suspected Ghost</p>
              <p className="font-mono text-sm font-bold mt-0.5 text-red-400">{centreRollup.suspected_ghost_batches}</p>
            </div>
            <div className="p-2 rounded bg-black/20">
              <p className="text-[10px] text-purple-400">Escalated</p>
              <p className="font-mono text-sm font-bold mt-0.5 text-purple-400">{centreRollup.escalated_batches}</p>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
        {/* Batch list */}
        <div className="xl:col-span-2 neu-card overflow-hidden">
          <div className="px-4 py-3" style={{ borderBottom: 'var(--edge)' }}>
            <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Evaluations / मूल्यांकन सूची ({evaluations.length})
            </p>
          </div>
          <div className="neu-well overflow-x-auto" style={{ borderRadius: 0, border: 'none', boxShadow: 'none' }}>
            {isPending ? (
              <div className="p-8 text-center">
                <RefreshCw size={16} className="animate-spin inline-block mr-2 text-disabled" />
                <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Loading evaluations…</span>
              </div>
            ) : isError || !evaluations.length ? (
              <div className="p-8 text-center">
                <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>No ghost evaluations found in database.</p>
              </div>
            ) : (
              <table className="pramaan-table pramaan-table-clickable min-w-[380px]">
                <thead>
                  <tr>
                    {['Batch / बैच', 'Status / स्थिति', 'Score / स्कोर', 'Eligible'].map(h => <th key={h}>{h}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {evaluations
                    .slice()
                    .sort((a, b) => b.ghost_score - a.ghost_score)
                    .map(ev => {
                      const batch = batches.find(b => b.id === ev.batch_id);
                      const isSelected = activeEval?.id === ev.id;
                      const score100 = (ev.ghost_score || 0) * 100;
                      return (
                        <tr
                          key={ev.id}
                          onClick={() => setSelectedEvalId(ev.id)}
                          style={{
                            cursor: 'pointer',
                            background: isSelected ? 'rgba(111,140,255,0.08)' : undefined,
                          }}
                        >
                          <td>
                            <p className="font-medium text-sm" style={{ color: 'var(--text-primary)' }}>
                              {batch?.trade ?? (ev as any).batch_trade ?? ev.batch_id.slice(0, 10)}
                            </p>
                            <p className="text-[10px] font-mono" style={{ color: 'var(--text-disabled)' }}>
                              {ev.batch_id.slice(0, 12)}…
                            </p>
                          </td>
                          <td>{ghostStatusChip(ev.state)}</td>
                          <td>
                            <span className="font-mono font-bold" style={{
                              color: score100 >= 60 ? 'var(--st-ghost)' : score100 >= 30 ? 'var(--st-amber)' : 'var(--st-green)',
                            }}>
                              {score100.toFixed(0)}
                            </span>
                          </td>
                          <td>
                            <span className="font-mono text-xs">{ev.eligible_days}</span>
                            {ev.eligible_days < 2 && (
                              <span className="ml-1 chip chip-pending" style={{ fontSize: '0.6rem', padding: '1px 4px' }}>insuff.</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Detail panel */}
        <div className="xl:col-span-3">
          {activeEval ? (
            <BatchDetail
              evaluation={activeEval}
              batchTrade={batches.find(b => b.id === activeEval.batch_id)?.trade}
            />
          ) : (
            <div className="neu-well p-8 text-center">
              <p style={{ color: 'var(--text-disabled)' }}>
                Select an evaluation to see Ghost Score, indicator breakdown, multi-day calendar, and fairness panel.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
