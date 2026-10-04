import React from 'react';
import { BookOpen, Clock, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatDateTime } from '@/lib/utils';

interface RuleExplanationCardProps {
  ruleName: string;
  numbers: string;
  timeWindow: string;
  evidenceLink?: string;
  detail?: string;
  className?: string;
}

export function RuleExplanationCard({
  ruleName,
  numbers,
  timeWindow,
  evidenceLink,
  detail,
  className,
}: RuleExplanationCardProps) {
  return (
    <div className={cn('card p-4 border-l-4 border-l-[#3B5BDB]', className)}>
      <div className="flex items-start gap-3">
        <div className="mt-0.5 w-7 h-7 rounded bg-[#E7EEFE] flex items-center justify-center shrink-0">
          <BookOpen size={14} className="text-[#3B5BDB]" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-mono font-semibold text-[#3730A3] uppercase tracking-wide mb-1">
            Rule fired
          </p>
          <p className="text-sm font-semibold text-slate-800">{ruleName}</p>
          {detail && <p className="text-sm text-slate-600 mt-1">{detail}</p>}
          <div className="flex flex-wrap gap-4 mt-3">
            <div>
              <p className="text-xs text-slate-400 mb-0.5">Numbers</p>
              <p className="text-sm font-mono font-semibold text-slate-700">{numbers}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400 mb-0.5">Time window</p>
              <p className="text-sm font-mono text-slate-700 flex items-center gap-1">
                <Clock size={11} />
                {timeWindow}
              </p>
            </div>
          </div>
          {evidenceLink && (
            <a
              href={evidenceLink}
              className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-[#3B5BDB] hover:underline"
            >
              View evidence <ChevronRight size={12} />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
