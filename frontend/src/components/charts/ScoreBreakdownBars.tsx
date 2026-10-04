import React from 'react';
import { cn } from '@/lib/utils';
import type { GhostIndicators } from '@/types';
import { SimulatedBadge } from '@/components/shared/SimulatedBadge';

interface IndicatorDef {
  key: keyof GhostIndicators;
  label: string;
  description: string;
  weight: number;
  color: string;
}

const INDICATORS: IndicatorDef[] = [
  {
    key: 'i1_persistent_shortfall',
    label: 'I1 — Persistent shortfall',
    description: 'Share of valid sessions where observed < 50% of claimed.',
    weight: 0.40,
    color: '#DC2626',
  },
  {
    key: 'i2_near_zero',
    label: 'I2 — Near-zero occupancy',
    description: 'Sessions where observed ≤ 10% of claimed.',
    weight: 0.20,
    color: '#EA580C',
  },
  {
    key: 'i3_claim_uniformity',
    label: 'I3 — Claim uniformity',
    description: 'Claimed count nearly constant while observed varies.',
    weight: 0.15,
    color: '#D97706',
  },
  {
    key: 'i4_out_of_schedule',
    label: 'I4 — Out-of-schedule claims',
    description: 'Attendance claimed when timetable has no session.',
    weight: 0.10,
    color: '#B45309',
  },
  {
    key: 'i5_room_overlap',
    label: 'I5 — Room overlap',
    description: 'Two batches claiming the same room simultaneously.',
    weight: 0.10,
    color: '#7C3AED',
  },
  {
    key: 'i6_trend',
    label: 'I6 — Trend',
    description: 'Claimed rising or flat while observed is falling.',
    weight: 0.05,
    color: '#6D28D9',
  },
];

interface ScoreBreakdownBarsProps {
  indicators: GhostIndicators;
  ghostScore: number;
  className?: string;
}

export function ScoreBreakdownBars({ indicators, ghostScore, className }: ScoreBreakdownBarsProps) {
  return (
    <div className={cn('card p-4 space-y-4', className)}>
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-slate-800">Ghost Score breakdown</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Weighted sum of indicators. Thresholds are initial hypotheses — calibrate on pilot data.
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-mono font-bold text-red-600">{ghostScore.toFixed(0)}</div>
          <div className="text-xs text-slate-400">/100</div>
        </div>
      </div>

      <div className="space-y-3">
        {INDICATORS.map((ind) => {
          const rawVal = indicators[ind.key]; // 0-1
          const contribution = rawVal * ind.weight * 100;
          const pct = Math.round(rawVal * 100);

          return (
            <div key={ind.key} className="space-y-1">
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
              {/* Plain-language text */}
              {rawVal > 0 && (
                <p className="text-xs font-medium" style={{ color: ind.color }}>
                  {getPlainText(ind.key, rawVal, indicators)}
                </p>
              )}
            </div>
          );
        })}
      </div>

      <div className="border-t pt-2 flex items-center gap-2">
        <SimulatedBadge />
        <p className="text-xs text-amber-700">⚗ All weights are initial hypotheses</p>
      </div>
    </div>
  );
}

function getPlainText(key: keyof GhostIndicators, val: number, ind: GhostIndicators): string {
  const pct = Math.round(val * 100);
  switch (key) {
    case 'i1_persistent_shortfall':
      return `In ${pct}% of valid sessions, observed was under half of claimed.`;
    case 'i2_near_zero':
      return `${pct}% of sessions had near-zero observed count (≤10% of claimed).`;
    case 'i3_claim_uniformity':
      return `Claimed counts showed low variation while observed varied — possible copy-paste pattern.`;
    case 'i4_out_of_schedule':
      return `${pct}% of sessions had claims outside the scheduled timetable.`;
    case 'i5_room_overlap':
      return `Room overlap detected in ${pct}% of claimed sessions.`;
    case 'i6_trend':
      return `Observed trend is declining while claimed stays flat or rises.`;
    default:
      return '';
  }
}
