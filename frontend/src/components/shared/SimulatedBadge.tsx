import React from 'react';
import { cn } from '@/lib/utils';

interface SimulatedBadgeProps {
  className?: string;
  variant?: 'bar' | 'pill';
}

export function SimulatedBadge({ className, variant = 'pill' }: SimulatedBadgeProps) {
  if (variant === 'bar') {
    return (
      <div
        className={cn(
          'w-full flex items-center justify-center gap-2 py-1 px-3',
          'bg-amber-950 text-amber-300 text-xs font-mono font-semibold tracking-widest',
          'border-b border-amber-800',
          className,
        )}
        role="note"
        aria-label="This dashboard displays simulated data only"
      >
        <span className="inline-block w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
        SIMULATED DATA — NOT REAL MONITORING OUTPUT
        <span className="inline-block w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
      </div>
    );
  }

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono font-semibold',
        'bg-[#1C1917] text-[#FCD34D] tracking-wide',
        'border border-[#92400E]/40',
        className,
      )}
      role="note"
      aria-label="Simulated data"
    >
      <span className="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0" />
      SIMULATED
    </span>
  );
}
