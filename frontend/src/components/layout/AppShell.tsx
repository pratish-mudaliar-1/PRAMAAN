import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { NavRail } from './NavRail';
import { TopBar } from './TopBar';
import { useRealtimeEvents } from '@/hooks/useRealtimeEvents';

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false);
  const [lang, setLang] = useState<'en' | 'hi' | 'mr'>('en');
  const [role, setRole] = useState<'officer' | 'inspector' | 'tc_spoc' | 'auditor'>('officer');
  const [isOnline, setIsOnline] = useState(true);
  const [highContrast, setHighContrast] = useState(false);

  // Maintain active real-time WebSocket connection and auto-invalidate cache
  useRealtimeEvents();

  React.useEffect(() => {
    document.documentElement.classList.toggle('hc', highContrast);
  }, [highContrast]);

  return (
    <div className="flex flex-col h-screen overflow-hidden" style={{ background: 'var(--bg-base)' }}>
      <div className="flex flex-1 overflow-hidden">
        <NavRail
          collapsed={collapsed}
          onToggle={() => setCollapsed((c) => !c)}
          lang={lang}
          role={role}
        />

        <div className="flex flex-col flex-1 overflow-hidden">
          <TopBar
            lang={lang}
            onLangChange={setLang}
            role={role}
            onRoleChange={setRole}
            isOnline={isOnline}
            onToggleOnline={() => setIsOnline((o) => !o)}
            highContrast={highContrast}
            onToggleHighContrast={() => setHighContrast((hc) => !hc)}
          />
          <main
            className="flex-1 overflow-auto"
            id="main-content"
            aria-label="Main content area"
            style={{ background: 'var(--bg-base)' }}
          >
            <Outlet context={{ role, lang, isOnline, setIsOnline }} />
          </main>
        </div>
      </div>
    </div>
  );
}
