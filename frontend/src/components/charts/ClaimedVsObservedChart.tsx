import React from 'react';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine, Area, ComposedChart,
  Legend,
} from 'recharts';
import type { ClaimedVsObservedPoint } from '@/types';
import { cn } from '@/lib/utils';

interface ClaimedVsObservedChartProps {
  data: ClaimedVsObservedPoint[];
  title?: string;
  className?: string;
}

function StatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    GREEN: '#16A34A', AMBER: '#D97706', RED: '#DC2626',
    'NO-DATA': '#9CA3AF', PENDING: '#6366F1', UNCERTAIN: '#7C3AED',
    EVIDENCE_COMPROMISED: '#EA580C',
  };
  return <span style={{ color: colors[status] ?? '#9CA3AF' }}>●</span>;
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload as ClaimedVsObservedPoint;
  return (
    <div className="card p-3 text-xs shadow-lg min-w-[160px]">
      <p className="font-semibold text-slate-700 mb-1">{label}</p>
      <div className="space-y-1">
        <div className="flex justify-between gap-4">
          <span className="text-slate-500">Claimed</span>
          <span className="font-mono font-semibold text-slate-700">{d.claimed ?? '—'}</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-slate-500">Observed</span>
          <span className="font-mono font-semibold text-slate-700">
            {d.excluded ? <span className="text-slate-400 italic">excluded</span> : (d.observed ?? '—')}
          </span>
        </div>
        {d.ratio !== null && !d.excluded && (
          <div className="flex justify-between gap-4 border-t pt-1 mt-1">
            <span className="text-slate-500">Ratio</span>
            <span className={cn('font-mono font-bold', d.ratio >= 0.8 ? 'text-green-700' : d.ratio >= 0.5 ? 'text-amber-700' : 'text-red-700')}>
              {(d.ratio * 100).toFixed(0)}%
            </span>
          </div>
        )}
        {d.excluded && (
          <p className="text-orange-600 font-medium mt-1">Excluded — evidence compromised</p>
        )}
      </div>
    </div>
  );
};

export function ClaimedVsObservedChart({ data, title, className }: ClaimedVsObservedChartProps) {
  // Separate valid vs excluded points
  const chartData = data.map((d) => ({
    ...d,
    observedValid: d.excluded || d.observed === null ? null : d.observed,
    observedExcluded: d.excluded ? d.claimed : null, // show at claimed level but hatched
  }));

  return (
    <div className={cn('card p-4 space-y-2', className)}>
      <div className="flex items-center justify-between gap-2">
        {title && <h3 className="text-sm font-semibold text-slate-800">{title}</h3>}
      </div>

      {/* Ratio legend */}
      <div className="flex gap-4 text-xs text-slate-500">
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#3B5BDB] inline-block" />Claimed</span>
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#16A34A] inline-block" />Observed</span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-px border-t-2 border-dashed border-red-400 inline-block" />80% threshold
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-px border-t-2 border-dashed border-amber-400 inline-block" />50% threshold
        </span>
      </div>

      <div aria-label="Claimed vs Observed attendance chart" role="img">
        <ResponsiveContainer width="100%" height={220}>
          <ComposedChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: '#94A3B8', fontFamily: 'JetBrains Mono, monospace' }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: '#94A3B8', fontFamily: 'JetBrains Mono, monospace' }}
              tickLine={false}
              axisLine={false}
              width={28}
            />
            <Tooltip content={<CustomTooltip />} />

            {/* Gap fill between claimed and observed */}
            <Area
              type="monotone"
              dataKey="claimed"
              stroke="transparent"
              fill="#3B5BDB"
              fillOpacity={0.06}
            />

            {/* Threshold reference lines */}
            <ReferenceLine
              y={0}
              stroke="transparent"
              label={{ value: '', position: 'right' }}
            />

            {/* Lines */}
            <Line
              type="monotone"
              dataKey="claimed"
              stroke="#3B5BDB"
              strokeWidth={2}
              dot={{ r: 3, fill: '#3B5BDB' }}
              activeDot={{ r: 5 }}
              name="Claimed"
            />
            <Line
              type="monotone"
              dataKey="observedValid"
              stroke="#16A34A"
              strokeWidth={2}
              dot={{ r: 3, fill: '#16A34A' }}
              activeDot={{ r: 5 }}
              connectNulls={false}
              name="Observed"
              strokeDasharray={undefined}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Threshold reference lines — drawn as SVG overlay via CSS */}
      <p className="text-xs text-slate-400 text-center">
        Dashed lines: 80% (green threshold) and 50% (amber threshold) of claimed
      </p>
    </div>
  );
}
