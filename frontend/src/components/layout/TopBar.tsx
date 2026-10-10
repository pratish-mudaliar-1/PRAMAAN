import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Search, Bell, Contrast, ShieldCheck } from 'lucide-react';
import { useFlags } from '@/hooks/useFlags';

interface TopBarProps {
  lang: 'en' | 'hi' | 'mr';
  onLangChange: (l: 'en' | 'hi' | 'mr') => void;
  role: 'officer' | 'inspector' | 'tc_spoc' | 'auditor';
  onRoleChange: (r: 'officer' | 'inspector' | 'tc_spoc' | 'auditor') => void;
  isOnline: boolean;
  onToggleOnline: () => void;
  highContrast: boolean;
  onToggleHighContrast: () => void;
  notificationCount?: number;
}

export function TopBar({
  lang, onLangChange, role, onRoleChange,
  isOnline, onToggleOnline,
  highContrast, onToggleHighContrast,
}: TopBarProps) {
  const [notifOpen, setNotifOpen] = useState(false);
  const { data: flagsData } = useFlags({ status: 'OPEN', limit: 10 });

  const openFlags = flagsData?.items ?? [];
  const unreadCount = openFlags.length;

  const langs: Array<{ code: 'en' | 'hi' | 'mr'; label: string }> = [
    { code: 'en', label: 'EN' },
    { code: 'hi', label: 'हिन्दी' },
    { code: 'mr', label: 'मराठी' },
  ];

  const roles: Array<{ code: 'officer' | 'inspector' | 'tc_spoc' | 'auditor'; label: string }> = [
    { code: 'officer',   label: 'Officer'   },
    { code: 'inspector', label: 'Inspector' },
    { code: 'tc_spoc',  label: 'TC SPOC'   },
    { code: 'auditor',  label: 'Auditor'   },
  ];

  return (
    <header
      className="flex items-center gap-3 px-4 shrink-0"
      style={{
        height: 'var(--topbar-height)',
        background: 'var(--bg-raised)',
        borderBottom: 'var(--edge)',
        boxShadow: 'var(--raised-sm)',
      }}
    >
      {/* Search */}
      <div className="relative flex-1 max-w-xs">
        <Search
          size={14}
          className="absolute left-3 top-1/2 -translate-y-1/2"
          style={{ color: 'var(--text-disabled)' }}
        />
        <input
          className="neu-input pl-8"
          style={{ maxWidth: '100%' }}
          placeholder="Search centres, batches, cameras…"
          aria-label="Global search"
        />
      </div>

      <div className="flex-1" />

      {/* Connectivity */}
      <div
        className="flex items-center gap-1.5 neu-btn neu-btn-xs"
        title="Live backend WebSocket connection"
      >
        <span className="conn-dot conn-dot-online" />
        <span className="text-xs" style={{ color: 'var(--st-green)' }}>
          Online
        </span>
      </div>

      {/* Language switcher */}
      <div className="neu-segment-group" role="group" aria-label="Language switcher">
        {langs.map((l) => (
          <button
            key={l.code}
            className={`neu-segment ${lang === l.code ? 'active' : ''}`}
            style={{ fontFamily: l.code !== 'en' ? 'var(--font-devanagari)' : undefined }}
            onClick={() => onLangChange(l.code)}
            aria-pressed={lang === l.code}
          >
            {l.label}
          </button>
        ))}
      </div>

      {/* Role switcher */}
      <select
        value={role}
        onChange={(e) => onRoleChange(e.target.value as typeof role)}
        className="neu-input"
        style={{ width: 'auto', padding: '0.3rem 0.6rem', fontSize: '0.8rem' }}
        aria-label="Role selector"
      >
        {roles.map((r) => (
          <option key={r.code} value={r.code}>{r.label}</option>
        ))}
      </select>

      {/* High-contrast toggle */}
      <button
        onClick={onToggleHighContrast}
        className={`neu-btn neu-btn-xs ${highContrast ? 'neu-btn-primary' : ''}`}
        title="Toggle high-contrast mode"
        aria-label="Toggle high contrast"
        aria-pressed={highContrast}
      >
        <Contrast size={13} />
      </button>

      {/* Notifications */}
      <div className="relative">
        <button
          className="neu-btn neu-btn-xs relative"
          onClick={() => setNotifOpen((o) => !o)}
          aria-label={`Notifications: ${unreadCount} open flags`}
        >
          <Bell size={14} />
          {unreadCount > 0 && (
            <span
              className="absolute -top-1 -right-1 text-[9px] font-bold rounded-full px-1 leading-4 min-w-[14px] text-center"
              style={{ background: 'var(--st-red)', color: '#fff' }}
            >
              {unreadCount}
            </span>
          )}
        </button>

        {notifOpen && (
          <div
            className="pramaan-modal absolute right-0 top-8 z-50"
            style={{ width: 340, padding: '1rem' }}
          >
            <div className="flex items-center justify-between mb-2">
              <p className="section-header">Active Anomaly Flags</p>
              <Link to="/flags" onClick={() => setNotifOpen(false)} className="text-xs" style={{ color: 'var(--accent)' }}>
                View all
              </Link>
            </div>
            {openFlags.length === 0 ? (
              <p className="text-xs" style={{ color: 'var(--text-disabled)' }}>No active flags requiring attention.</p>
            ) : (
              openFlags.map((f) => (
                <Link
                  key={f.id}
                  to="/flags"
                  onClick={() => setNotifOpen(false)}
                  className="flex items-start gap-2 py-2 hover:bg-white/5 px-1 rounded transition-colors"
                  style={{ borderBottom: 'var(--edge)', textDecoration: 'none' }}
                >
                  <span
                    className="w-2 h-2 rounded-full mt-1 shrink-0"
                    style={{ background: f.severity === 'HIGH' ? 'var(--st-red)' : 'var(--st-amber)' }}
                  />
                  <div className="flex-1">
                    <p className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>
                      {f.flag_type.replace(/_/g, ' ')}
                    </p>
                    <p className="text-[11px] truncate" style={{ color: 'var(--text-secondary)' }}>
                      {f.rule_name}
                    </p>
                    <p className="text-[10px] font-mono mt-0.5" style={{ color: 'var(--text-disabled)' }}>
                      {new Date(f.created_at).toLocaleTimeString('en-IN')}
                    </p>
                  </div>
                </Link>
              ))
            )}
          </div>
        )}
      </div>

      <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-[6px]" style={{ background: 'rgba(61,220,151,0.08)', border: '1px solid rgba(61,220,151,0.2)' }}>
        <ShieldCheck size={12} style={{ color: 'var(--st-green)' }} />
        <span className="text-[10px] font-mono font-semibold" style={{ color: 'var(--st-green)' }}>
          LIVE MVP
        </span>
      </div>
    </header>
  );
}
