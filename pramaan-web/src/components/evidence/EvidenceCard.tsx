import React from 'react';
import { cn, formatDateTime } from '@/lib/utils';
import { Eye, EyeOff } from 'lucide-react';

interface EvidenceCardProps {
  timestamp: string;
  personCount?: number;
  zone?: string;
  sessionId?: string;
  isBlurred?: boolean;
  privacyNote?: boolean;
  className?: string;
  // In production this would be a blurred keyframe URL
  // For demo we generate a placeholder
  imageUrl?: string;
}

function BlurredFramePlaceholder({ count }: { count?: number }) {
  // Stylised representation — no real faces, just count dots
  return (
    <div className="w-full aspect-video bg-slate-800 rounded-t-md flex flex-col items-center justify-center relative overflow-hidden">
      {/* Simulated blurred background */}
      <div className="absolute inset-0 bg-gradient-to-br from-slate-700 via-slate-800 to-slate-900" />
      <div className="absolute inset-0 grid grid-cols-6 grid-rows-4 gap-1 p-3 opacity-20">
        {Array.from({ length: 24 }).map((_, i) => (
          <div key={i} className="rounded bg-slate-600" />
        ))}
      </div>
      {/* Count representation */}
      {count !== undefined && (
        <div className="relative flex flex-wrap gap-2 justify-center max-w-[70%]">
          {Array.from({ length: Math.min(count, 30) }).map((_, i) => (
            <div
              key={i}
              className="w-6 h-8 rounded-full bg-slate-500/60 border border-slate-400/40 flex items-end justify-center pb-0.5"
            >
              <div className="w-3 h-3 rounded-full bg-slate-400/50" />
            </div>
          ))}
        </div>
      )}
      <div className="absolute bottom-2 left-2 right-2 flex justify-between items-end">
        {count !== undefined && (
          <span className="text-white/90 text-xs font-mono font-bold bg-black/40 px-2 py-0.5 rounded">
            {count} persons detected
          </span>
        )}
      </div>
    </div>
  );
}

export function EvidenceCard({
  timestamp,
  personCount,
  zone,
  sessionId,
  isBlurred = true,
  privacyNote = true,
  className,
  imageUrl,
}: EvidenceCardProps) {
  return (
    <div className={cn('card overflow-hidden text-sm', className)}>
      {imageUrl ? (
        <div className="w-full aspect-video bg-slate-800 rounded-t-md overflow-hidden relative">
          <img
            src={imageUrl}
            alt={`Evidence keyframe at ${timestamp}`}
            className={cn('w-full h-full object-cover', isBlurred && 'blur-md')}
          />
        </div>
      ) : (
        <BlurredFramePlaceholder count={personCount} />
      )}

      {privacyNote && (
        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 text-slate-300 text-xs">
          <EyeOff size={11} />
          <span>Privacy: faces blurred, counts only</span>
        </div>
      )}

      <div className="px-3 py-2 space-y-1">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-xs font-mono text-slate-400">{formatDateTime(timestamp)}</span>
          {zone && <span className="text-xs text-slate-500 truncate">{zone}</span>}
        </div>
        {personCount !== undefined && (
          <p className="text-sm font-semibold text-slate-700">
            Persons detected: <span className="font-mono">{personCount}</span>
          </p>
        )}
        {sessionId && (
          <p className="text-xs text-slate-400">Session {sessionId}</p>
        )}
      </div>
    </div>
  );
}
