import React from 'react';
import { cn } from '@/lib/utils';

interface SkeletonProps { className?: string; }

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn('skeleton rounded-md', className)}
      aria-hidden="true"
    />
  );
}

interface SkeletonRowsProps {
  rows?: number;
  cols?: number;
  className?: string;
}

export function SkeletonRows({ rows = 5, cols = 4, className }: SkeletonRowsProps) {
  return (
    <div className={cn('space-y-2', className)} aria-busy="true" aria-label="Loading…">
      {Array.from({ length: rows }).map((_, ri) => (
        <div key={ri} className="flex gap-3 items-center px-4 py-2">
          {Array.from({ length: cols }).map((_, ci) => (
            <Skeleton
              key={ci}
              className={cn(
                'h-4',
                ci === 0 ? 'w-24' : ci === cols - 1 ? 'w-16' : 'flex-1',
              )}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

export function SkeletonCard({ className }: SkeletonProps) {
  return (
    <div className={cn('card p-4 space-y-3', className)} aria-hidden="true">
      <Skeleton className="h-5 w-1/2" />
      <Skeleton className="h-3 w-3/4" />
      <Skeleton className="h-3 w-2/3" />
      <div className="flex gap-2 mt-4">
        <Skeleton className="h-8 w-20 rounded" />
        <Skeleton className="h-8 w-20 rounded" />
      </div>
    </div>
  );
}
