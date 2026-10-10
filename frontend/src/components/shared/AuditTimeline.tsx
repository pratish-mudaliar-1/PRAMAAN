import React from 'react';
import { cn, formatDateTime } from '@/lib/utils';
import type { AuditEvent } from '@/types';
import { User, Settings, Flag, Camera, FileText, CheckCircle } from 'lucide-react';

const ACTION_ICON: Record<string, React.ElementType> = {
  flag_opened: Flag,
  flag_closed: CheckCircle,
  tc_response: FileText,
  threshold_changed: Settings,
  baseline_approved: Camera,
  default: User,
};

interface AuditTimelineProps {
  events: AuditEvent[];
  className?: string;
  maxItems?: number;
}

export function AuditTimeline({ events, className, maxItems }: AuditTimelineProps) {
  const displayed = maxItems ? events.slice(0, maxItems) : events;

  if (events.length === 0) {
    return (
      <p className={cn('text-sm text-slate-400 text-center py-4', className)}>
        No audit events yet.
      </p>
    );
  }

  return (
    <ol className={cn('relative', className)} aria-label="Audit trail">
      {displayed.map((event, i) => {
        const Icon = ACTION_ICON[event.action] ?? ACTION_ICON.default;
        const isLast = i === displayed.length - 1;
        return (
          <li key={event.id} className="flex gap-3 pb-4 relative">
            {/* Connector line */}
            {!isLast && (
              <div className="absolute left-3 top-7 bottom-0 w-px bg-slate-200" />
            )}
            {/* Icon */}
            <div className="w-6 h-6 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center shrink-0 mt-0.5 z-10">
              <Icon size={11} className="text-slate-500" />
            </div>
            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-baseline gap-2 flex-wrap">
                <span className="text-sm font-medium text-slate-800">{event.action.replace(/_/g, ' ')}</span>
                <span className="text-xs text-slate-400 font-mono">
                  {formatDateTime(event.occurred_at)}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                by{' '}
                <span className="font-medium text-slate-600">{event.actor}</span>
                {event.detail?.note ? <> · {String(event.detail.note)}</> : null}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
