import React from 'react';
import { cn } from '@/lib/utils';

interface ScoreGaugeProps {
  score: number | null; // 0-100
  size?: number; // px
  label?: string;
  className?: string;
}

function getScoreColor(score: number): { stroke: string; text: string } {
  if (score < 30) return { stroke: '#16A34A', text: '#065F46' };
  if (score < 60) return { stroke: '#D97706', text: '#92400E' };
  return { stroke: '#DC2626', text: '#991B1B' };
}

export function ScoreGauge({ score, size = 96, label, className }: ScoreGaugeProps) {
  const radius = (size - 12) / 2;
  const circumference = Math.PI * radius; // semicircle
  const strokeWidth = 8;

  if (score === null) {
    return (
      <div
        className={cn('flex flex-col items-center gap-1', className)}
        style={{ width: size }}
        aria-label="Score: unavailable"
      >
        <div
          className="rounded-full bg-slate-100 flex items-center justify-center text-slate-400 text-sm font-mono"
          style={{ width: size, height: size / 1.8 }}
        >
          —
        </div>
        {label && <span className="text-xs text-slate-500">{label}</span>}
      </div>
    );
  }

  const clampedScore = Math.max(0, Math.min(100, score));
  const progress = (clampedScore / 100) * circumference;
  const { stroke, text } = getScoreColor(clampedScore);

  return (
    <div
      className={cn('flex flex-col items-center gap-1', className)}
      style={{ width: size }}
      role="meter"
      aria-valuenow={clampedScore}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`Ghost score: ${clampedScore}`}
    >
      <div className="relative" style={{ width: size, height: size / 1.8 + 6 }}>
        <svg
          width={size}
          height={size / 1.8 + 6}
          viewBox={`0 0 ${size} ${size / 1.8 + 6}`}
        >
          {/* Track */}
          <path
            d={`M ${strokeWidth / 2} ${size / 1.8} A ${radius} ${radius} 0 0 1 ${size - strokeWidth / 2} ${size / 1.8}`}
            fill="none"
            stroke="#E2E8F0"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
          />
          {/* Filled arc */}
          <path
            d={`M ${strokeWidth / 2} ${size / 1.8} A ${radius} ${radius} 0 0 1 ${size - strokeWidth / 2} ${size / 1.8}`}
            fill="none"
            stroke={stroke}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={`${progress} ${circumference}`}
            style={{
              transition: 'stroke-dasharray 0.6s cubic-bezier(0.2, 0, 0, 1)',
            }}
          />
          {/* Score text */}
          <text
            x={size / 2}
            y={size / 1.8 - 4}
            textAnchor="middle"
            fontSize={size * 0.22}
            fontWeight="700"
            fontFamily="JetBrains Mono, monospace"
            fill={text}
          >
            {clampedScore}
          </text>
          <text
            x={size / 2}
            y={size / 1.8 + 4}
            textAnchor="middle"
            fontSize={size * 0.1}
            fill="#94A3B8"
            fontFamily="Inter, sans-serif"
          >
            /100
          </text>
        </svg>
      </div>
      {label && <span className="text-xs text-slate-500 text-center">{label}</span>}
    </div>
  );
}
