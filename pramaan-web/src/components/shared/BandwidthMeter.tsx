import React from 'react';
import { cn, formatBytes, streamingEquivalentBytes } from '@/lib/utils';
import { Activity } from 'lucide-react';

interface BandwidthMeterProps {
  bytesSent: number;
  cameras: number;
  minutesOnline: number;
  className?: string;
}

export function BandwidthMeter({
  bytesSent,
  cameras,
  minutesOnline,
  className,
}: BandwidthMeterProps) {
  const streamingEquiv = streamingEquivalentBytes(cameras, minutesOnline);
  const ratio = bytesSent / Math.max(streamingEquiv, 1);
  const savingsPct = Math.max(0, (1 - ratio) * 100);

  // Design estimate: ~250 B/camera/minute vs ~2 Mbps stream
  const pramaanRate = cameras > 0 ? bytesSent / Math.max(minutesOnline, 1) / cameras : 0;
  const streamingRate = 2 * 1024 * 1024 / 8; // bytes/sec -> per minute * 60

  return (
    <div className={cn('card p-4 space-y-4', className)}>
      <div className="flex items-center gap-2">
        <Activity size={16} className="text-[#3B5BDB]" />
        <h3 className="text-sm font-semibold text-slate-800">Bandwidth — design estimate</h3>
        <span className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5 ml-auto">
          ⚗ hypothesis
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs text-slate-400 mb-0.5">PRAMAAN sent</p>
          <p className="text-xl font-mono font-bold text-[#3B5BDB]">{formatBytes(bytesSent)}</p>
          <p className="text-xs text-slate-500">~{Math.round(pramaanRate)} B/camera·min</p>
        </div>
        <div>
          <p className="text-xs text-slate-400 mb-0.5">Streaming equivalent</p>
          <p className="text-xl font-mono font-bold text-slate-600">{formatBytes(streamingEquiv)}</p>
          <p className="text-xs text-slate-500">@ 2 Mbps per camera</p>
        </div>
      </div>

      {/* Bar comparison */}
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <div className="w-20 text-xs text-slate-500 text-right shrink-0">PRAMAAN</div>
          <div className="flex-1 h-4 rounded bg-slate-100 overflow-hidden">
            <div
              className="h-full rounded bg-[#3B5BDB] transition-all duration-700"
              style={{ width: `${Math.min(ratio * 100, 100).toFixed(2)}%` }}
            />
          </div>
          <div className="text-xs font-mono text-slate-600 w-16 shrink-0">{formatBytes(bytesSent)}</div>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-20 text-xs text-slate-500 text-right shrink-0">Streaming</div>
          <div className="flex-1 h-4 rounded bg-slate-100 overflow-hidden">
            <div className="h-full rounded bg-slate-400" style={{ width: '100%' }} />
          </div>
          <div className="text-xs font-mono text-slate-600 w-16 shrink-0">{formatBytes(streamingEquiv)}</div>
        </div>
      </div>

      <div className="bg-emerald-50 border border-emerald-200 rounded px-3 py-2">
        <p className="text-xs font-semibold text-emerald-700">
          ~{savingsPct.toFixed(0)}% less data than continuous streaming
        </p>
        <p className="text-xs text-emerald-600 mt-0.5">
          Daily estimate per camera: ~{formatBytes(250 * 60 * 24)} vs ~{formatBytes(2 * 1024 * 1024 / 8 * 60 * 60 * 24)}
        </p>
      </div>
    </div>
  );
}
