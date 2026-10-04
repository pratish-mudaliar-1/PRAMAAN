import React from 'react';
import { InboxIcon, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface EmptyStateProps {
  title?: string;
  message: string;
  icon?: React.ElementType;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  title = 'Nothing here',
  message,
  icon: Icon = InboxIcon,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 py-16 px-6 text-center',
        className,
      )}
      role="status"
    >
      <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center">
        <Icon size={24} className="text-slate-400" />
      </div>
      <div>
        <p className="text-sm font-semibold text-slate-700">{title}</p>
        <p className="text-sm text-slate-500 mt-1 max-w-xs">{message}</p>
      </div>
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

interface ErrorStateProps {
  message: string;
  recoverable?: boolean;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({ message, recoverable = true, onRetry, className }: ErrorStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 py-12 px-6 text-center',
        className,
      )}
      role="alert"
    >
      <div className="w-12 h-12 rounded-full bg-red-50 flex items-center justify-center">
        <AlertCircle size={24} className="text-red-500" />
      </div>
      <div>
        <p className="text-sm font-semibold text-red-700">
          {recoverable ? 'Something went wrong' : 'Unable to load'}
        </p>
        <p className="text-sm text-slate-500 mt-1 max-w-xs">{message}</p>
      </div>
      {recoverable && onRetry && (
        <button
          onClick={onRetry}
          className="mt-1 text-sm font-medium text-accent-DEFAULT hover:underline focus-visible:outline-none"
        >
          Try again
        </button>
      )}
    </div>
  );
}
