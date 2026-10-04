import React from 'react';
import { cn } from '@/lib/utils';

interface RatioBandProps {
  ratio: number | null; // 0-1
  className?: string;
  showValue?: boolean;
  height?: number;
}

export function RatioBand({ ratio, className, showValue = true, height = 20 }: RatioBandProps) {
  if (ratio === null) {
    return (
      <div className={cn('flex items-center gap-2', className)}>
        <div
          className="flex-1 rounded-full bg-slate-100 pattern-hatch"
          style={{ height }}
          aria-label="Ratio: unavailable"
        />
        {showValue && <span className="text-xs font-mono text-slate-400 w-8 text-right">—</span>}
      </div>
    );
  }

  const pct = Math.max(0, Math.min(100, ratio * 100));
  const color = ratio >= 0.80 ? '#16A34A' : ratio >= 0.50 ? '#D97706' : '#DC2626';

  return (
    <div
      className={cn('flex items-center gap-2', className)}
      role="meter"
      aria-valuenow={Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`Ratio: ${Math.round(pct)}%`}
    >
      <div className="relative flex-1 rounded-full bg-slate-100 overflow-hidden" style={{ height }}>
        {/* Fill */}
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
        {/* Threshold markers */}
        <div
          className="absolute top-0 bottom-0 w-px bg-white/80"
          style={{ left: '50%' }}
          title="50% threshold"
        />
        <div
          className="absolute top-0 bottom-0 w-px bg-white/80"
          style={{ left: '80%' }}
          title="80% threshold"
        />
      </div>
      {showValue && (
        <span
          className="text-xs font-mono w-9 text-right font-semibold tabular-nums"
          style={{ color }}
        >
          {Math.round(pct)}%
        </span>
      )}
    </div>
  );
}
