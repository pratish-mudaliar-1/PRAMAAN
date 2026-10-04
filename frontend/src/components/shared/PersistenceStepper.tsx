import React from 'react';
import { cn } from '@/lib/utils';
import { CheckCircle, Clock, Circle } from 'lucide-react';

interface PersistenceStepperProps {
  filled: number;   // windows that triggered
  total: number;    // total windows in persistence window
  required: number; // windows needed to confirm
  currentState: string;
  className?: string;
}

export function PersistenceStepper({
  filled,
  total,
  required,
  currentState,
  className,
}: PersistenceStepperProps) {
  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span className="font-medium">Persistence check</span>
        <span className="font-mono">
          {filled} of {required} windows triggered
        </span>
      </div>
      <div className="flex gap-1 flex-wrap">
        {Array.from({ length: total }).map((_, i) => {
          const isFilled = i < filled;
          const isRequired = i < required;
          return (
            <div
              key={i}
              className={cn(
                'w-6 h-6 rounded-sm flex items-center justify-center transition-colors',
                isFilled && isRequired
                  ? 'bg-red-100 text-red-500'
                  : isFilled
                  ? 'bg-amber-100 text-amber-500'
                  : isRequired
                  ? 'bg-slate-100 text-slate-300'
                  : 'bg-slate-50 text-slate-200',
              )}
              title={`Window ${i + 1}: ${isFilled ? 'triggered' : 'clear'}`}
            >
              {isFilled ? (
                <CheckCircle size={12} strokeWidth={2.5} />
              ) : (
                <Circle size={12} strokeWidth={1.5} />
              )}
            </div>
          );
        })}
      </div>
      <p className="text-xs text-slate-500">
        {filled >= required
          ? `Threshold reached — current state: ${currentState}`
          : `${required - filled} more consecutive window(s) needed for confirmation`}
      </p>
    </div>
  );
}
