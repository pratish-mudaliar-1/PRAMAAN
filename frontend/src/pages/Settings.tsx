import React, { useState, useEffect } from 'react';
import { Info, Save, RefreshCw, CheckCircle, AlertTriangle } from 'lucide-react';
import { useThresholds, useUpdateThresholds } from '@/hooks/useThresholds';
import type { ThresholdUpdateRequest } from '@/api/thresholds';

export function SettingsPage() {
  const { data: profile, isPending, isError } = useThresholds();
  const updateMutation = useUpdateThresholds();

  const [form, setForm] = useState<ThresholdUpdateRequest>({
    t_green: 0.80,
    t_amber: 0.50,
    repeat_n: 2,
    min_feed_health_fraction: 0.80,
    item_absent_min_windows: 3,
    item_absent_min_days: 2,
    phash_hamming_threshold: 12,
    approval_note: 'Updated via settings console',
  });

  const [savedMessage, setSavedMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (profile) {
      setForm({
        t_green: profile.t_green,
        t_amber: profile.t_amber,
        repeat_n: profile.repeat_n,
        min_feed_health_fraction: profile.min_feed_health_fraction,
        item_absent_min_windows: profile.item_absent_min_windows,
        item_absent_min_days: profile.item_absent_min_days,
        phash_hamming_threshold: profile.phash_hamming_threshold,
        approval_note: profile.approval_note || 'Profile active',
      });
    }
  }, [profile]);

  const handleSave = async () => {
    setErrorMessage(null);
    setSavedMessage(null);
    try {
      await updateMutation.mutateAsync(form);
      setSavedMessage('Thresholds saved and persisted to database. Immutable audit entry logged.');
      setTimeout(() => setSavedMessage(null), 5000);
    } catch (e: any) {
      setErrorMessage(e?.detail || e?.message || 'Failed to persist thresholds');
    }
  };

  if (isPending) {
    return (
      <div className="page-root">
        <div className="neu-card p-8 flex items-center justify-center gap-3">
          <RefreshCw size={16} className="animate-spin" style={{ color: 'var(--text-disabled)' }} />
          <p style={{ color: 'var(--text-secondary)' }}>Loading active threshold configuration…</p>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="page-root">
        <div className="neu-card p-8 text-center">
          <p style={{ color: 'var(--st-red)' }}>Failed to load threshold configuration from server.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-root">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Settings &amp; Thresholds
          </h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            Active Profile: Version {profile?.version} · Scheme: {profile?.scheme_code || 'ALL'}
          </p>
        </div>
      </div>

      {/* Persistence Feedback */}
      {savedMessage && (
        <div className="neu-alert-info">
          <CheckCircle size={15} style={{ color: 'var(--st-green)', flexShrink: 0 }} />
          <p className="text-xs font-semibold" style={{ color: 'var(--st-green)' }}>{savedMessage}</p>
        </div>
      )}

      {errorMessage && (
        <div className="neu-alert-red">
          <AlertTriangle size={15} style={{ color: 'var(--st-red)', flexShrink: 0 }} />
          <p className="text-xs font-semibold" style={{ color: 'var(--st-red)' }}>{errorMessage}</p>
        </div>
      )}

      {/* Attendance reconciliation */}
      <div className="neu-card overflow-hidden">
        <div className="px-4 py-3" style={{ borderBottom: 'var(--edge)' }}>
          <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Attendance Reconciliation</p>
        </div>
        <div className="p-4 space-y-5">
          {/* T_GREEN */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                Green attendance threshold (T_GREEN)
              </label>
              <span className="font-mono text-sm" style={{ color: 'var(--accent)' }}>
                {form.t_green.toFixed(2)}
              </span>
            </div>
            <div className="neu-well-sm p-3">
              <input
                type="range"
                min="0.5"
                max="1.0"
                step="0.05"
                value={form.t_green}
                onChange={e => setForm(f => ({ ...f, t_green: parseFloat(e.target.value) }))}
                style={{ width: '100%', accentColor: 'var(--accent)', background: 'transparent' }}
              />
              <p className="text-xs mt-2" style={{ color: 'var(--text-secondary)' }}>
                Sessions with observed ratio ≥ T_GREEN are classified as GREEN.
              </p>
            </div>
          </div>

          {/* T_AMBER */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                Amber attendance threshold (T_AMBER)
              </label>
              <span className="font-mono text-sm" style={{ color: 'var(--accent)' }}>
                {form.t_amber.toFixed(2)}
              </span>
            </div>
            <div className="neu-well-sm p-3">
              <input
                type="range"
                min="0.1"
                max="0.8"
                step="0.05"
                value={form.t_amber}
                onChange={e => setForm(f => ({ ...f, t_amber: parseFloat(e.target.value) }))}
                style={{ width: '100%', accentColor: 'var(--accent)', background: 'transparent' }}
              />
              <p className="text-xs mt-2" style={{ color: 'var(--text-secondary)' }}>
                Sessions with observed ratio below T_AMBER trigger RED, between T_AMBER and T_GREEN trigger AMBER.
              </p>
            </div>
          </div>

          {/* REPEAT_N */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                Amber persistence count (REPEAT_N)
              </label>
              <span className="font-mono text-sm" style={{ color: 'var(--accent)' }}>
                {form.repeat_n}
              </span>
            </div>
            <div className="neu-well-sm p-3">
              <input
                type="range"
                min="1"
                max="5"
                step="1"
                value={form.repeat_n}
                onChange={e => setForm(f => ({ ...f, repeat_n: parseInt(e.target.value, 10) }))}
                style={{ width: '100%', accentColor: 'var(--accent)', background: 'transparent' }}
              />
              <p className="text-xs mt-2" style={{ color: 'var(--text-secondary)' }}>
                Consecutive AMBER sessions required before an AMBER_REPEAT anomaly flag is raised.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Feed health & camera integrity */}
      <div className="neu-card overflow-hidden">
        <div className="px-4 py-3" style={{ borderBottom: 'var(--edge)' }}>
          <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Feed Health &amp; Camera Integrity</p>
        </div>
        <div className="p-4 space-y-5">
          {/* MIN_FEED_HEALTH */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                Minimum Feed Health Fraction
              </label>
              <span className="font-mono text-sm" style={{ color: 'var(--accent)' }}>
                {form.min_feed_health_fraction.toFixed(2)}
              </span>
            </div>
            <div className="neu-well-sm p-3">
              <input
                type="range"
                min="0.5"
                max="1.0"
                step="0.05"
                value={form.min_feed_health_fraction}
                onChange={e => setForm(f => ({ ...f, min_feed_health_fraction: parseFloat(e.target.value) }))}
                style={{ width: '100%', accentColor: 'var(--accent)', background: 'transparent' }}
              />
              <p className="text-xs mt-2" style={{ color: 'var(--text-secondary)' }}>
                Fraction of frames with feed_ok required to consider the session evidence conclusive.
              </p>
            </div>
          </div>

          {/* PHASH_HAMMING_THRESHOLD */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                Perceptual Hash Hamming Distance Threshold
              </label>
              <span className="font-mono text-sm" style={{ color: 'var(--accent)' }}>
                {form.phash_hamming_threshold} bits
              </span>
            </div>
            <div className="neu-well-sm p-3">
              <input
                type="range"
                min="4"
                max="32"
                step="1"
                value={form.phash_hamming_threshold}
                onChange={e => setForm(f => ({ ...f, phash_hamming_threshold: parseInt(e.target.value, 10) }))}
                style={{ width: '100%', accentColor: 'var(--accent)', background: 'transparent' }}
              />
              <p className="text-xs mt-2" style={{ color: 'var(--text-secondary)' }}>
                Maximum bit difference to classify images as identical/near-duplicate frames.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Note & Save */}
      <div className="neu-card p-4 space-y-3">
        <label className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
          Audit Note / Justification for Change
        </label>
        <input
          type="text"
          className="neu-input w-full text-xs"
          placeholder="Reason for modifying baseline thresholds…"
          value={form.approval_note || ''}
          onChange={e => setForm(f => ({ ...f, approval_note: e.target.value }))}
        />
        <div className="flex items-center justify-between pt-2">
          <p className="text-xs font-mono" style={{ color: 'var(--text-disabled)' }}>
            Approved by: {profile?.approved_by || 'system_init'}
          </p>
          <button
            className="neu-btn neu-btn-primary"
            onClick={handleSave}
            disabled={updateMutation.isPending}
          >
            <Save size={14} className={updateMutation.isPending ? 'animate-spin' : ''} />
            {updateMutation.isPending ? 'Saving to Database…' : 'Save Thresholds to DB'}
          </button>
        </div>
      </div>
    </div>
  );
}
