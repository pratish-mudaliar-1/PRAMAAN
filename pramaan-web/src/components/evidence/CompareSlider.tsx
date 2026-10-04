import React, { useRef, useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { EyeOff } from 'lucide-react';

interface CompareSliderProps {
  beforeLabel?: string;
  afterLabel?: string;
  className?: string;
  beforeContent?: React.ReactNode;
  afterContent?: React.ReactNode;
  anchors?: Array<{ x: number; y: number; found: boolean; label: string }>;
}

function RoomPlaceholder({
  variant,
  anchors,
}: {
  variant: 'baseline' | 'current';
  anchors?: Array<{ x: number; y: number; found: boolean; label: string }>;
}) {
  const items =
    variant === 'baseline'
      ? [
          { x: 10, y: 15, w: 20, h: 35, label: 'whiteboard' },
          { x: 35, y: 50, w: 12, h: 20, label: 'machine-1' },
          { x: 52, y: 50, w: 12, h: 20, label: 'machine-2' },
          { x: 69, y: 50, w: 12, h: 20, label: 'machine-3' },
          { x: 80, y: 10, w: 15, h: 25, label: 'door' },
        ]
      : [
          { x: 10, y: 15, w: 20, h: 35, label: 'different-wall' },
          { x: 40, y: 40, w: 40, h: 30, label: 'different-equipment' },
        ];

  const bgColor = variant === 'baseline' ? '#1e293b' : '#1a1a2e';

  return (
    <div
      className="w-full h-full relative overflow-hidden"
      style={{ background: bgColor }}
    >
      {/* Room elements */}
      {items.map((item) => (
        <div
          key={item.label}
          className="absolute rounded opacity-40 border border-white/10"
          style={{
            left: `${item.x}%`,
            top: `${item.y}%`,
            width: `${item.w}%`,
            height: `${item.h}%`,
            background: variant === 'baseline' ? '#334155' : '#2d1b4e',
          }}
          title={item.label}
        />
      ))}
      {/* Anchor overlays */}
      {anchors?.map((a, i) => (
        <div
          key={i}
          className={cn(
            'absolute w-4 h-4 rounded-full border-2 -translate-x-1/2 -translate-y-1/2 flex items-center justify-center text-[8px] font-bold',
            a.found
              ? 'bg-green-500/30 border-green-400 text-green-300'
              : 'bg-red-500/30 border-red-400 text-red-300',
          )}
          style={{ left: `${a.x}%`, top: `${a.y}%` }}
          title={`${a.label}: ${a.found ? 'found' : 'missing'}`}
        >
          {a.found ? '✓' : '✗'}
        </div>
      ))}
      <div className="absolute bottom-2 left-2 text-[10px] font-mono text-white/40 uppercase tracking-widest">
        {variant === 'baseline' ? 'registered view' : 'current frame'}
      </div>
    </div>
  );
}

export function CompareSlider({
  beforeLabel = 'Registered baseline',
  afterLabel = 'Current view',
  className,
  beforeContent,
  afterContent,
  anchors,
}: CompareSliderProps) {
  const [position, setPosition] = useState(50);
  const containerRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const updatePosition = useCallback((clientX: number) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const pct = ((clientX - rect.left) / rect.width) * 100;
    setPosition(Math.max(5, Math.min(95, pct)));
  }, []);

  const onMouseMove = useCallback(
    (e: React.MouseEvent) => { if (dragging.current) updatePosition(e.clientX); },
    [updatePosition],
  );
  const onTouchMove = useCallback(
    (e: React.TouchEvent) => { if (dragging.current) updatePosition(e.touches[0].clientX); },
    [updatePosition],
  );

  return (
    <div className={cn('space-y-1', className)}>
      <div className="flex justify-between text-xs text-slate-500 px-1">
        <span className="flex items-center gap-1">
          <EyeOff size={10} /> {beforeLabel}
        </span>
        <span className="flex items-center gap-1">
          {afterLabel} <EyeOff size={10} />
        </span>
      </div>
      <div
        ref={containerRef}
        className="relative w-full aspect-video bg-slate-900 rounded-lg overflow-hidden cursor-ew-resize select-none"
        onMouseMove={onMouseMove}
        onMouseUp={() => { dragging.current = false; }}
        onMouseLeave={() => { dragging.current = false; }}
        onTouchMove={onTouchMove}
        onTouchEnd={() => { dragging.current = false; }}
        aria-label="Compare slider: drag to compare registered view and current view"
        role="img"
      >
        {/* Before (full width) */}
        <div className="absolute inset-0">
          {beforeContent ?? <RoomPlaceholder variant="baseline" anchors={anchors} />}
        </div>

        {/* After (clipped) */}
        <div
          className="absolute inset-0"
          style={{ clipPath: `inset(0 0 0 ${position}%)` }}
        >
          {afterContent ?? <RoomPlaceholder variant="current" />}
        </div>

        {/* Divider */}
        <div
          className="compare-slider-handle"
          style={{ left: `${position}%` }}
          onMouseDown={() => { dragging.current = true; }}
          onTouchStart={() => { dragging.current = true; }}
        />

        {/* Labels */}
        <div className="absolute top-2 left-2 text-[10px] font-mono text-white/60 bg-black/40 px-2 py-0.5 rounded pointer-events-none">
          ← Baseline
        </div>
        <div className="absolute top-2 right-2 text-[10px] font-mono text-white/60 bg-black/40 px-2 py-0.5 rounded pointer-events-none">
          Current →
        </div>
        {/* Privacy notice */}
        <div className="absolute bottom-2 left-0 right-0 flex justify-center pointer-events-none">
          <div className="text-[10px] flex items-center gap-1 text-white/60 bg-black/50 px-2 py-0.5 rounded">
            <EyeOff size={9} /> Privacy: faces blurred, counts only
          </div>
        </div>
      </div>
      <p className="text-xs text-center text-slate-400">← Drag to compare →</p>
    </div>
  );
}
