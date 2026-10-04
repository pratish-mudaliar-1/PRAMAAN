import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Search, Bell, Sun, Contrast } from 'lucide-react';

interface TopBarProps {
  lang: 'en' | 'hi' | 'mr';
  onLangChange: (l: 'en' | 'hi' | 'mr') => void;
  role: 'officer' | 'inspector' | 'tc_spoc' | 'auditor';
  onRoleChange: (r: 'officer' | 'inspector' | 'tc_spoc' | 'auditor') => void;
  isOnline: boolean;
  onToggleOnline: () => void;
  highContrast: boolean;
  onToggleHighContrast: () => void;
  notificationCount: number;
}

export function TopBar({
  lang, onLangChange, role, onRoleChange,
  isOnline, onToggleOnline,
  highContrast, onToggleHighContrast,
  notificationCount,
}: TopBarProps) {
  const [notifOpen, setNotifOpen] = useState(false);

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
      <button
        onClick={onToggleOnline}
        className="flex items-center gap-1.5 neu-btn neu-btn-xs"
        title={isOnline ? 'Simulated online — click to toggle offline' : 'Simulated offline — click to go online'}
        aria-label={isOnline ? 'Online' : 'Offline'}
      >
        <span className={`conn-dot conn-dot-${isOnline ? 'online' : 'offline'}`} />
        <span className="text-xs" style={{ color: isOnline ? 'var(--st-green)' : 'var(--st-red)' }}>
          {isOnline ? 'Online' : 'Offline'}
        </span>
      </button>

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
        aria-label="Demo role switcher"
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
          aria-label={`Notifications: ${notificationCount} unread`}
        >
          <Bell size={14} />
          {notificationCount > 0 && (
            <span
              className="absolute -top-1 -right-1 text-[9px] font-bold rounded-full px-1 leading-4 min-w-[14px] text-center"
              style={{ background: 'var(--st-red)', color: '#fff' }}
            >
              {notificationCount}
            </span>
          )}
        </button>

        {notifOpen && (
          <div
            className="pramaan-modal absolute right-0 top-8 z-50"
            style={{ width: 320, padding: '1rem' }}
          >
            <p className="section-header mb-2">Notifications</p>
            {[
              { msg: 'SUSPECTED_SWAP — CAM-C-01 (Computer Centre Pune)', t: '10:57', sev: 'red' },
              { msg: 'Ghost Score ≥ 60 — BATCH-D-01 (Skill Centre Patna)', t: '07:00', sev: 'amber' },
              { msg: 'Edge offline — CTR-E (3 days)', t: '3d ago', sev: 'nodata' },
            ].map((n, i) => (
              <div key={i} className="flex items-start gap-2 py-2" style={{ borderBottom: i < 2 ? 'var(--edge)' : 'none' }}>
                <span
                  className="w-2 h-2 rounded-full mt-1 shrink-0"
                  style={{ background: `var(--st-${n.sev})` }}
                />
                <div className="flex-1">
                  <p className="text-xs" style={{ color: 'var(--text-primary)' }}>{n.msg}</p>
                  <p className="text-[10px]" style={{ color: 'var(--text-disabled)' }}>{n.t}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Simulated badge (compact) */}
      <span className="simulated-badge">SIMULATED</span>
    </header>
  );
}
