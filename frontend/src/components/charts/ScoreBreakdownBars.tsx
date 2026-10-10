import { cn } from '@/lib/utils';
import type { GhostExplanation } from '@/types';

interface IndicatorDef {
  key: keyof GhostExplanation;
  label: string;
  description: string;
  weight: number;
  color: string;
}

const INDICATORS: IndicatorDef[] = [
  {
    key: 'persistence',
    label: 'Persistent Shortfall',
    description: 'Fraction of eligible sessions where observed attendance was significantly below claimed.',
    weight: 0.35,
    color: '#DC2626',
  },
  {
    key: 'magnitude',
    label: 'Magnitude of Gap',
    description: 'Average depth of attendance shortfall below the red threshold.',
    weight: 0.30,
    color: '#EA580C',
  },
  {
    key: 'consistency',
    label: 'Claim Uniformity',
    description: 'Unusual lack of variance in claimed attendance compared to observed variation.',
    weight: 0.20,
    color: '#D97706',
  },
  {
    key: 'evidence_quality',
    label: 'Evidence Quality',
    description: 'Fraction of evaluation window with validated, trusted observation data.',
    weight: 0.15,
    color: '#2563EB',
  },
];

interface ScoreBreakdownBarsProps {
  explanation: GhostExplanation;
  ghostScore: number;
  className?: string;
}

export function ScoreBreakdownBars({ explanation, ghostScore, className }: ScoreBreakdownBarsProps) {
  return (
    <div className={cn('card p-4 space-y-4', className)}>
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-slate-800">Ghost Score Breakdown</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Backend explainability components — weighted sum of evidence indicators.
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-mono font-bold text-red-600">{ghostScore.toFixed(0)}</div>
          <div className="text-xs text-slate-400">/100</div>
        </div>
      </div>

      <div className="space-y-3">
        {INDICATORS.map((ind) => {
          const rawVal = Number(explanation[ind.key] ?? 0); // 0-1
          const contribution = rawVal * ind.weight * 100;
          const pct = Math.round(rawVal * 100);

          return (
            <div key={String(ind.key)} className="space-y-1">
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-xs font-semibold text-slate-700">{ind.label}</span>
                <span className="text-xs font-mono text-slate-500 shrink-0">
                  {pct}% × {(ind.weight * 100).toFixed(0)}% wt = +{contribution.toFixed(1)}
                </span>
              </div>
              <div className="relative h-5 bg-slate-100 rounded overflow-hidden">
                <div
                  className="h-full rounded transition-all duration-700"
                  style={{
                    width: `${pct}%`,
                    backgroundColor: ind.color,
                    opacity: 0.85,
                  }}
                />
              </div>
              <p className="text-xs text-slate-500">{ind.description}</p>
              {rawVal > 0 && (
                <p className="text-xs font-medium" style={{ color: ind.color }}>
                  {getPlainText(ind.key, rawVal)}
                </p>
              )}
            </div>
          );
        })}
      </div>

      <div className="border-t pt-2 flex items-center justify-between text-xs text-slate-500">
        <div className="flex items-center gap-2">
          <span>Weights calibrated by backend reconciliation engine</span>
        </div>
        {explanation.cusum_score !== undefined && (
          <span className="font-mono text-slate-600">
            CUSUM: {Number(explanation.cusum_score).toFixed(2)}
          </span>
        )}
      </div>
    </div>
  );
}

function getPlainText(key: keyof GhostExplanation, val: number): string {
  const pct = Math.round(val * 100);
  switch (key) {
    case 'persistence':
      return `Persistent shortfall observed in ${pct}% of evaluated sessions.`;
    case 'magnitude':
      return `Attendance gap magnitude scored at ${pct}% severity.`;
    case 'consistency':
      return `Claim uniformity indicator scored at ${pct}% (low natural variation).`;
    case 'evidence_quality':
      return `Observation data coverage and trust confidence at ${pct}%.`;
    default:
      return '';
  }
}

