import React from 'react';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine, ReferenceArea,
} from 'recharts';
import type { ViewEvent } from '@/types';
import { cn } from '@/lib/utils';
import { SimulatedBadge } from '@/components/shared/SimulatedBadge';
import { StatusChip } from '@/components/status/StatusChip';

interface SimilarityTimelineProps {
  events: ViewEvent[];
  tSame?: number;
  tMismatch?: number;
  className?: string;
}

const STATE_COLORS: Record<string, string> = {
  SAME_VIEW: '#16A34A',
  VIEW_DRIFTED: '#D97706',
  VIEW_MISMATCH: '#EA580C',
  SUSPECTED_SWAP: '#DC2626',
  SWAP_CONFIRMED: '#7F1D1D',
  UNCERTAIN: '#7C3AED',
  REBASELINE_PENDING: '#3730A3',
};

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload as ViewEvent;
  return (
    <div className="card p-3 text-xs shadow-lg min-w-[180px]">
      <p className="font-mono text-slate-400 mb-1">{new Date(d.ts).toLocaleString('en-IN')}</p>
      <div className="space-y-1">
        <div className="flex justify-between gap-3">
          <span className="text-slate-500">Similarity</span>
          <span className="font-mono font-bold" style={{ color: STATE_COLORS[d.state] ?? '#6B7280' }}>
            {d.similarity.toFixed(3)}
          </span>
        </div>
        <div className="flex justify-between gap-3">
          <span className="text-slate-500">Anchors found</span>
          <span className="font-mono">{d.anchors_found}/{d.anchors_total}</span>
        </div>
        <div className="flex justify-between gap-3">
          <span className="text-slate-500">Baseline</span>
          <span className="font-mono">v{d.baseline_ver}</span>
        </div>
        <div className="pt-1 border-t mt-1">
          <StatusChip status={d.state} size="sm" />
        </div>
      </div>
    </div>
  );
};

export function SimilarityTimeline({
  events,
  tSame = 0.75,
  tMismatch = 0.35,
  className,
}: SimilarityTimelineProps) {
  const chartData = events.map((e) => ({
    ...e,
    time: new Date(e.ts).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
    coloredSim: e.similarity,
  }));

  // State change markers
  const stateChanges = events.filter((e, i) => i === 0 || e.state !== events[i - 1].state);

  return (
    <div className={cn('card p-4 space-y-2', className)}>
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-800">Scene similarity over time</h3>
        <SimulatedBadge />
      </div>

      <div className="flex gap-4 text-xs text-slate-500 flex-wrap">
        <span className="flex items-center gap-1">
          <span className="w-3 h-0.5 border-t-2 border-dashed border-green-500 inline-block" />
          T_same = {tSame}
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-0.5 border-t-2 border-dashed border-orange-500 inline-block" />
          T_mismatch = {tMismatch}
        </span>
        <span className="flex items-center gap-1">
          <span className="text-amber-700 font-medium">⚗ initial hypotheses</span>
        </span>
      </div>

      <div aria-label="Camera similarity score timeline" role="img">
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />

            {/* Threshold bands */}
            <ReferenceArea y1={tSame} y2={1.0} fill="#ECFDF5" fillOpacity={0.5} />
            <ReferenceArea y1={tMismatch} y2={tSame} fill="#FFFBEB" fillOpacity={0.5} />
            <ReferenceArea y1={0} y2={tMismatch} fill="#FEF2F2" fillOpacity={0.5} />

            <ReferenceLine
              y={tSame}
              stroke="#16A34A"
              strokeDasharray="4 2"
              strokeWidth={1.5}
              label={{ value: tSame, position: 'right', fontSize: 10, fill: '#16A34A' }}
            />
            <ReferenceLine
              y={tMismatch}
              stroke="#EA580C"
              strokeDasharray="4 2"
              strokeWidth={1.5}
              label={{ value: tMismatch, position: 'right', fontSize: 10, fill: '#EA580C' }}
            />

            <XAxis
              dataKey="time"
              tick={{ fontSize: 10, fill: '#94A3B8', fontFamily: 'JetBrains Mono, monospace' }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              domain={[0, 1]}
              tick={{ fontSize: 10, fill: '#94A3B8', fontFamily: 'JetBrains Mono, monospace' }}
              tickLine={false}
              axisLine={false}
              width={30}
              tickFormatter={(v) => v.toFixed(1)}
            />
            <Tooltip content={<CustomTooltip />} />

            <Line
              type="monotone"
              dataKey="similarity"
              stroke="#3B5BDB"
              strokeWidth={2}
              dot={(props: any) => {
                const d = props.payload as ViewEvent;
                const color = STATE_COLORS[d.state] ?? '#3B5BDB';
                return (
                  <circle
                    key={props.index}
                    cx={props.cx}
                    cy={props.cy}
                    r={3.5}
                    fill={color}
                    stroke="white"
                    strokeWidth={1}
                  />
                );
              }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* State change markers legend */}
      <div className="flex flex-wrap gap-2 pt-1">
        {stateChanges.map((e, i) => (
          <div key={i} className="flex items-center gap-1">
            <span
              className="w-2 h-2 rounded-full"
              style={{ background: STATE_COLORS[e.state] ?? '#6B7280' }}
            />
            <span className="text-xs text-slate-500">
              {new Date(e.ts).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })} → {e.state.replace(/_/g, ' ')}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
