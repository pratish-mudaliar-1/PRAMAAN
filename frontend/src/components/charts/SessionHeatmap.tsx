import { cn } from '@/lib/utils';
import type { ClaimedVsObservedPoint, SessionStatus } from '@/types';

interface SessionHeatmapProps {
  data: ClaimedVsObservedPoint[];
  sessions?: string[]; // session labels (AM, PM, etc.)
  className?: string;
}

type CellStatus = SessionStatus | 'EXCLUDED' | 'EMPTY';

function getRatioStatus(ratio: number | null, excluded: boolean): CellStatus {
  if (excluded) return 'EXCLUDED';
  if (ratio === null) return 'NO_DATA';
  if (ratio >= 0.8) return 'GREEN';
  if (ratio >= 0.5) return 'AMBER';
  return 'RED';
}

const CELL_STYLES: Record<string, string> = {
  GREEN:      'bg-[#ECFDF5] text-[#065F46]',
  AMBER:      'bg-[#FFFBEB] text-[#92400E]',
  RED:        'bg-[#FEF2F2] text-[#991B1B]',
  NO_DATA:    'bg-[#F3F4F6] text-[#9CA3AF] pattern-hatch',
  'NO-DATA':  'bg-[#F3F4F6] text-[#9CA3AF] pattern-hatch',
  PENDING:    'bg-[#EEF2FF] text-[#3730A3]',
  EXCLUDED:   'bg-orange-50 text-orange-400 opacity-60',
  EMPTY:      'bg-slate-50 text-slate-300',
};

const CELL_ICONS: Record<string, string> = {
  GREEN: '✓', AMBER: '~', RED: '✗',
  NO_DATA: '—', 'NO-DATA': '—', PENDING: '◌',
  EXCLUDED: '⊘', EMPTY: '',
};

interface HeatmapCell {
  date: string;
  status: CellStatus;
  ratio: number | null;
  excluded: boolean;
  claimed: number;
  observed: number | null;
}

export function SessionHeatmap({ data, sessions = ['AM', 'PM'], className }: SessionHeatmapProps) {
  // Group data into weeks
  const weeks: HeatmapCell[][] = [];
  let currentWeek: HeatmapCell[] = [];

  data.forEach((d, i) => {
    const cell: HeatmapCell = {
      date: d.date,
      status: getRatioStatus(d.ratio, d.excluded),
      ratio: d.ratio,
      excluded: d.excluded,
      claimed: d.claimed,
      observed: d.observed,
    };
    currentWeek.push(cell);
    if (currentWeek.length === 7 || i === data.length - 1) {
      weeks.push([...currentWeek]);
      currentWeek = [];
    }
  });

  return (
    <div className={cn('card p-4 space-y-3', className)}>
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-800">Session status calendar</h3>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 text-xs">
        {(['GREEN', 'AMBER', 'RED', 'NO-DATA', 'EXCLUDED', 'EVIDENCE_COMPROMISED'] as const).map((s) => (
          <div key={s} className="flex items-center gap-1">
            <span
              className={cn(
                'w-5 h-5 rounded text-[10px] flex items-center justify-center font-bold',
                CELL_STYLES[s],
              )}
            >
              {CELL_ICONS[s]}
            </span>
            <span className="text-slate-500">
              {s === 'NO-DATA' ? 'No data' : s === 'EVIDENCE_COMPROMISED' ? 'Compromised' : s.charAt(0) + s.slice(1).toLowerCase()}
            </span>
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="overflow-x-auto" aria-label="Session status heatmap calendar" role="img">
        <div className="space-y-1 min-w-[480px]">
          {weeks.map((week, wi) => (
            <div key={wi} className="flex gap-1">
              {week.map((cell, di) => (
                <div
                  key={di}
                  className={cn(
                    'flex-1 rounded text-center py-1.5 cursor-default transition-transform hover:scale-110',
                    'flex flex-col items-center gap-0.5',
                    CELL_STYLES[cell.status],
                  )}
                  title={[
                    cell.date,
                    `Status: ${cell.status}`,
                    `Claimed: ${cell.claimed}`,
                    cell.observed !== null ? `Observed: ${cell.observed}` : '',
                    cell.ratio !== null ? `Ratio: ${(cell.ratio * 100).toFixed(0)}%` : '',
                    cell.excluded ? 'EXCLUDED from evidence' : '',
                  ].filter(Boolean).join('\n')}
                >
                  <span className="text-[10px] font-bold">{CELL_ICONS[cell.status]}</span>
                  <span className="text-[9px] font-mono leading-none opacity-70">
                    {cell.date.slice(5)}
                  </span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
      <p className="text-xs text-slate-400">
        ⊘ = excluded from ghost batch evidence (NO-DATA, compromised, etc.)
      </p>
    </div>
  );
}
