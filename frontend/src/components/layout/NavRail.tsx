import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, MapPin, Flag, Camera, Ghost,
  Activity, Settings, BookOpen, Shield, ChevronLeft, ChevronRight,
} from 'lucide-react';
import { useFlags } from '@/hooks/useFlags';
import { useCameras } from '@/hooks/useCameras';
import { useGhostAssessments } from '@/hooks/useGhost';

interface NavRailProps {
  collapsed: boolean;
  onToggle: () => void;
  lang: 'en' | 'hi' | 'mr';
  role: string;
}

const ROLE_LABELS: Record<string, string> = {
  officer: 'Monitoring Officer',
  inspector: 'Field Inspector',
  tc_spoc: 'TC SPOC',
  auditor: 'Auditor',
};

export function NavRail({ collapsed, onToggle, lang, role }: NavRailProps) {
  const { data: flagsData } = useFlags({ status: 'OPEN', limit: 200 });
  const { data: camerasData } = useCameras({ limit: 100 });
  const { data: ghostData } = useGhostAssessments({ limit: 100 });

  const openFlagsCount = flagsData?.items.length ?? 0;
  const cameraIntegrityIssuesCount = (camerasData?.items ?? []).filter(c => {
    const st = (c as any).current_state || c.view_state;
    return ['SWAP_SUSPECTED', 'SUSPECTED_SWAP', 'DRIFT_SUSPECTED'].includes(st);
  }).length;
  const ghostCount = (ghostData?.items ?? []).filter(g =>
    ['SUSPECTED_GHOST', 'WATCH'].includes(g.state)
  ).length;

  const NAV_ITEMS = [
    { label: 'Overview',          labelHi: 'अवलोकन',            labelMr: 'आढावा',             href: '/',                icon: LayoutDashboard, badge: 0 },
    { label: 'Centres & Map',     labelHi: 'केंद्र और मानचित्र', labelMr: 'केंद्रे व नकाशा',   href: '/centres',         icon: MapPin,          badge: 0 },
    { label: 'Flags & Cases',     labelHi: 'सूचनाएं और प्रकरण', labelMr: 'सूचना व प्रकरणे',  href: '/flags',           icon: Flag,            badge: openFlagsCount },
    { label: 'Camera Integrity',  labelHi: 'कैमरा विश्वसनीयता', labelMr: 'कॅमेरा विश्वासार्हता', href: '/camera-integrity', icon: Camera,        badge: cameraIntegrityIssuesCount },
    { label: 'Ghost Batches',     labelHi: 'संदिग्ध बैच',       labelMr: 'संशयित कागदोपत्री तुकडी', href: '/ghost-batches', icon: Ghost,       badge: ghostCount },
    { label: 'Edge Console',      labelHi: 'एज कंसोल',          labelMr: 'एज कन्सोल',         href: '/edge-console',    icon: Activity,        badge: 0 },
    { label: 'Settings',          labelHi: 'सेटिंग्स',           labelMr: 'सेटिंग्ज',          href: '/settings',        icon: Settings,        badge: 0 },
    { label: 'Audit Log',         labelHi: 'ऑडिट लॉग',          labelMr: 'ऑडिट नोंद',         href: '/audit-log',       icon: BookOpen,        badge: 0 },
    { label: 'Accuracy & Limits', labelHi: 'सटीकता और सीमाएं', labelMr: 'अचूकता व मर्यादा',  href: '/accuracy',        icon: Shield,          badge: 0 },
  ];

  function getLabel(item: typeof NAV_ITEMS[0], langStr: string) {
    if (langStr === 'hi') return item.labelHi;
    if (langStr === 'mr') return item.labelMr;
    return item.label;
  }

  return (
    <nav
      className="nav-rail"
      style={{ width: collapsed ? 'var(--nav-collapsed)' : 'var(--nav-width)' }}
      aria-label="Main navigation"
    >
      {/* Logo */}
      <div
        className="flex items-center gap-2 px-3 py-4"
        style={{ borderBottom: 'var(--edge)', minHeight: 'var(--topbar-height)' }}
      >
        <div
          className="flex items-center justify-center shrink-0 font-bold text-white text-xs"
          style={{
            width: 32, height: 32,
            borderRadius: 8,
            background: 'linear-gradient(135deg, var(--accent) 0%, #9f6bff 100%)',
            boxShadow: 'var(--raised-sm)',
            border: 'var(--edge)',
            flexShrink: 0,
          }}
        >
          PR
        </div>
        {!collapsed && (
          <div className="overflow-hidden">
            <p className="font-bold text-sm leading-none" style={{ color: 'var(--text-primary)' }}>
              PRAMAAN
            </p>
            <p className="text-[10px] leading-none mt-0.5" style={{ color: 'var(--text-disabled)' }}>
              SIH 2026 · PS 26245
            </p>
          </div>
        )}
      </div>

      {/* Nav links */}
      <div className="flex-1 overflow-y-auto py-2 px-2 space-y-0.5">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const label = getLabel(item, lang);
          return (
            <NavLink
              key={item.href}
              to={item.href}
              end={item.href === '/'}
              title={collapsed ? item.label : undefined}
              className={({ isActive }) =>
                [
                  'flex items-center gap-2 px-2 py-2 rounded-[10px] text-sm font-medium transition-all relative',
                  'focus-visible:outline-none',
                  isActive
                    ? 'text-white'
                    : 'hover:bg-white/5',
                ].join(' ')
              }
              style={({ isActive }) => isActive ? {
                background: 'rgba(111,140,255,0.18)',
                color: 'var(--accent)',
                boxShadow: 'var(--raised-sm)',
                border: '1px solid rgba(111,140,255,0.25)',
              } : {
                color: 'var(--text-secondary)',
              }}
            >
              <Icon size={15} className="shrink-0" />
              {!collapsed && (
                <span
                  className="flex-1 truncate text-[13px]"
                  style={{ fontFamily: lang !== 'en' ? 'var(--font-devanagari)' : undefined }}
                >
                  {label}
                </span>
              )}
              {!collapsed && item.badge > 0 && (
                <span
                  className="text-[10px] font-bold rounded-full px-1.5 py-0.5 leading-none"
                  style={{ background: 'var(--st-red)', color: '#fff' }}
                >
                  {item.badge}
                </span>
              )}
              {collapsed && item.badge > 0 && (
                <span
                  className="absolute right-1 top-1 w-2 h-2 rounded-full"
                  style={{ background: 'var(--st-red)' }}
                />
              )}
            </NavLink>
          );
        })}
      </div>

      {/* Role indicator */}
      {!collapsed && (
        <div className="px-3 py-2" style={{ borderTop: 'var(--edge)' }}>
          <div className="flex items-center gap-2">
            <div
              className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 text-[10px] font-bold"
              style={{ background: 'rgba(111,140,255,0.2)', color: 'var(--accent)', border: '1px solid rgba(111,140,255,0.3)' }}
            >
              {role[0]?.toUpperCase()}
            </div>
            <div className="overflow-hidden">
              <p className="text-xs font-medium truncate" style={{ color: 'var(--text-secondary)' }}>
                {ROLE_LABELS[role] ?? role}
              </p>
              <p className="text-[10px]" style={{ color: 'var(--text-disabled)' }}>Authenticated</p>
            </div>
          </div>
        </div>
      )}

      {/* Collapse toggle */}
      <button
        onClick={onToggle}
        className="flex items-center justify-center py-2 px-3 w-full transition-colors focus-visible:outline-none"
        style={{
          borderTop: 'var(--edge)',
          color: 'var(--text-disabled)',
          background: 'transparent',
          cursor: 'pointer',
        }}
        onMouseOver={(e) => (e.currentTarget.style.color = 'var(--text-primary)')}
        onMouseOut={(e) => (e.currentTarget.style.color = 'var(--text-disabled)')}
        aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
      >
        {collapsed
          ? <ChevronRight size={14} />
          : <div className="flex items-center gap-2 text-xs"><ChevronLeft size={14} /><span>Collapse</span></div>
        }
      </button>
    </nav>
  );
}
