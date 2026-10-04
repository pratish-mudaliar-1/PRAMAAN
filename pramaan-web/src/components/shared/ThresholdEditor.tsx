import React, { useState } from 'react';
import { cn, formatDateTime } from '@/lib/utils';
import { Edit2, Check, X, ChevronDown, History } from 'lucide-react';
import type { ThresholdConfig } from '@/types';

interface ThresholdEditorProps {
  config: ThresholdConfig;
  onSave?: (key: string, value: number) => Promise<void>;
  readonly?: boolean;
  className?: string;
}

interface HistoryItem {
  value: number;
  actor: string;
  ts: string;
}

const MOCK_HISTORY: Record<string, HistoryItem[]> = {};

export function ThresholdEditor({
  config,
  onSave,
  readonly = false,
  className,
}: ThresholdEditorProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(String(config.value));
  const [saving, setSaving] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  async function handleSave() {
    const parsed = parseFloat(draft);
    if (isNaN(parsed)) return;
    setSaving(true);
    try {
      await onSave?.(config.key, parsed);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={cn('group', className)}>
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-slate-800">{config.label}</span>
            <span className="text-xs font-mono text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
              {config.key}
            </span>
          </div>
          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-0.5 mt-1 inline-block">
            ⚗ hypothesis — calibrate on pilot
          </p>
          {config.hypothesis_note && (
            <p className="text-xs text-slate-500 mt-1">{config.hypothesis_note}</p>
          )}
        </div>

        <div className="flex items-center gap-1 shrink-0">
          {editing ? (
            <>
              <input
                type="number"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                className="w-20 text-sm font-mono text-right border border-[#3B5BDB] rounded px-2 py-1 outline-none focus:ring-2 focus:ring-[#3B5BDB]/30"
                step="0.01"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSave();
                  if (e.key === 'Escape') { setEditing(false); setDraft(String(config.value)); }
                }}
              />
              <button
                onClick={handleSave}
                disabled={saving}
                className="p-1 rounded text-green-600 hover:bg-green-50 disabled:opacity-50"
                aria-label="Save"
              >
                <Check size={14} />
              </button>
              <button
                onClick={() => { setEditing(false); setDraft(String(config.value)); }}
                className="p-1 rounded text-slate-400 hover:bg-slate-100"
                aria-label="Cancel"
              >
                <X size={14} />
              </button>
            </>
          ) : (
            <>
              <span className="text-sm font-mono font-semibold text-slate-700 min-w-[3rem] text-right">
                {config.value}
              </span>
              {!readonly && (
                <button
                  onClick={() => setEditing(true)}
                  className="p-1 rounded text-slate-400 hover:text-[#3B5BDB] hover:bg-[#E7EEFE] opacity-0 group-hover:opacity-100 transition-opacity"
                  aria-label={`Edit ${config.label}`}
                >
                  <Edit2 size={13} />
                </button>
              )}
            </>
          )}
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="p-1 rounded text-slate-400 hover:text-slate-600 hover:bg-slate-100"
            aria-label="Show history"
            aria-expanded={showHistory}
          >
            <History size={13} />
          </button>
        </div>
      </div>

      {showHistory && (
        <div className="mt-2 ml-0 pl-3 border-l-2 border-slate-200 text-xs text-slate-500 space-y-1">
          <p className="font-medium text-slate-600 mb-1">Change history</p>
          <p className="text-slate-400 italic">
            Last modified {formatDateTime(config.modified_at)} by {config.modified_by}
          </p>
          <p className="text-slate-400">No further history in this demo.</p>
        </div>
      )}
    </div>
  );
}
