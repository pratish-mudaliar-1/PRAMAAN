import React from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle, Camera, Ghost, WifiOff, Activity,
  ArrowRight, TrendingUp, Info,
} from 'lucide-react';
import {
  LineChart, Line, ResponsiveContainer, Tooltip,
} from 'recharts';
import { MOCK_CENTRES, MOCK_FLAGS } from '@/api/mockData';

// ── Helpers ─────────────────────────────────────────────────────────

function statusChipClass(s: string) {
  const m: Record<string, string> = {
    GREEN: 'chip-green', AMBER: 'chip-amber', RED: 'chip-red',
    'NO-DATA': 'chip-nodata', PENDING: 'chip-pending', UNCERTAIN: 'chip-uncertain',
    EVIDENCE_COMPROMISED: 'chip-compromised',
  };
  return m[s] ?? 'chip-nodata';
}

function statusIcon(s: string) {
  if (s === 'GREEN')  return '●';
  if (s === 'AMBER')  return '◆';
  if (s === 'RED')    return '■';
  if (s === 'NO-DATA') return '⬡';
  if (s === 'PENDING') return '○';
  if (s === 'UNCERTAIN') return '◌';
  return '?';
}

function severityClass(s: string) {
  if (s === 'HIGH')   return 'chip-high';
  if (s === 'MEDIUM') return 'chip-medium';
  return 'chip-low';
}

function flagTypeLabel(t: string) {
  const m: Record<string, string> = {
    OCCUPANCY: 'Occupancy', ITEM_ABSENT: 'Item absent',
    FEED_HEALTH: 'Feed health', DUPLICATE_EVIDENCE: 'Duplicate evidence',
    CAMERA_SWAP: 'Camera swap', GHOST_BATCH: 'Ghost batch',
  };
  return m[t] ?? t;
}

function formatSLA(deadline: string) {
  const diff = new Date(deadline).getTime() - Date.now();
  const h = Math.floor(diff / 3_600_000);
  if (diff < 0)  return <span className="sla-critical font-mono text-xs">Overdue</span>;
  if (h < 12)    return <span className="sla-critical font-mono text-xs">{h}h left</span>;
  if (h < 48)    return <span className="sla-warning  font-mono text-xs">{h}h left</span>;
  return <span className="sla-ok font-mono text-xs">{Math.floor(h / 24)}d left</span>;
}

// ── KPI Card ─────────────────────────────────────────────────────────

interface KpiProps {
  label: string; value: number | string; sub: string;
  icon: React.ElementType; accent?: boolean; href?: string;
}

function KpiCard({ label, value, sub, icon: Icon, accent, href }: KpiProps) {
  const content = (
    <div
      className="neu-card p-4 flex flex-col gap-2 cursor-pointer hover:translate-y-[-2px] transition-transform"
      style={accent ? { borderColor: 'rgba(255,92,108,0.4)' } : {}}
    >
      <div className="flex items-center justify-between">
        <p className="kpi-label">{label}</p>
        <div
          className="w-7 h-7 rounded-[8px] flex items-center justify-center"
          style={{
            background: accent ? 'rgba(255,92,108,0.12)' : 'rgba(111,140,255,0.1)',
            color: accent ? 'var(--st-red)' : 'var(--accent)',
          }}
        >
          <Icon size={14} />
        </div>
      </div>
      <p className="kpi-value" style={{ color: accent ? 'var(--st-red)' : 'var(--text-primary)' }}>
        {value}
      </p>
      <p className="text-xs" style={{ color: 'var(--text-disabled)' }}>{sub}</p>
    </div>
  );
  return href ? <Link to={href} style={{ textDecoration: 'none' }}>{content}</Link> : content;
}

// ── Flag Row ──────────────────────────────────────────────────────────

function FlagRow({ flag }: { flag: typeof MOCK_FLAGS[0] }) {
  return (
    <tr>
      <td>
        <Link
          to={`/centres/${flag.centre_id}`}
          className="text-sm font-medium hover:underline"
          style={{ color: 'var(--accent)' }}
        >
          {flag.centre_name}
        </Link>
      </td>
      <td><span className={`chip ${severityClass(flag.severity)}`}>{flagTypeLabel(flag.type)}</span></td>
      <td>
        <p className="text-xs max-w-xs truncate" style={{ color: 'var(--text-secondary)' }} title={flag.rule_fired}>
          {flag.rule_fired}
        </p>
      </td>
      <td>{formatSLA(flag.sla_deadline)}</td>
      <td>
        <span
          className="chip text-[10px]"
          style={{
            background: flag.status === 'OPEN' ? 'rgba(255,92,108,0.1)' : 'rgba(61,220,151,0.1)',
            color: flag.status === 'OPEN' ? 'var(--st-red)' : 'var(--st-green)',
            border: `1px solid ${flag.status === 'OPEN' ? 'rgba(255,92,108,0.3)' : 'rgba(61,220,151,0.3)'}`,
          }}
        >
          {flag.status.replace('_', ' ')}
        </span>
      </td>
      <td>
        {flag.evidence_link && (
          <Link to={flag.evidence_link} className="neu-btn neu-btn-xs" style={{ textDecoration: 'none' }}>
            View
          </Link>
        )}
      </td>
    </tr>
  );
}

// ── Sparkline ─────────────────────────────────────────────────────────

const TREND_DATA = [
  { d: '28 Sep', v: 12 }, { d: '29', v: 15 }, { d: '30', v: 11 },
  { d: '1 Oct', v: 18 }, { d: '2', v: 14 }, { d: '3', v: 22 }, { d: '4', v: 19 },
];

function TrendSparkline() {
  return (
    <div className="neu-card p-4">
      <p className="text-sm font-semibold mb-0.5" style={{ color: 'var(--text-primary)' }}>
        Open flags — last 7 days
      </p>
      <p className="text-xs mb-3" style={{ color: 'var(--text-disabled)' }}>Exception count trend</p>
      <div className="neu-well-sm p-2" style={{ height: 80 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={TREND_DATA}>
            <Tooltip
              contentStyle={{
                background: 'var(--bg-raised)',
                border: 'var(--edge-strong)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-primary)',
                fontSize: 11,
              }}
              formatter={(v: number) => [v, 'flags']}
              labelStyle={{ color: 'var(--text-secondary)' }}
            />
            <Line
              type="monotone"
              dataKey="v"
              stroke="var(--accent)"
              strokeWidth={2}
              dot={{ r: 3, fill: 'var(--accent)', stroke: 'var(--bg-raised)', strokeWidth: 2 }}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div
        className="flex justify-between text-[10px] mt-1 font-mono"
        style={{ color: 'var(--text-disabled)' }}
      >
        {TREND_DATA.map((d) => <span key={d.d}>{d.d}</span>)}
      </div>
    </div>
  );
}

// ── Centre Row ────────────────────────────────────────────────────────

function CentreRow({ centre }: { centre: typeof MOCK_CENTRES[0] }) {
  const hb = new Date(centre.last_heartbeat);
  const minsAgo = Math.floor((Date.now() - hb.getTime()) / 60_000);

  return (
    <tr>
      <td>
        <Link
          to={`/centres/${centre.id}`}
          className="font-medium hover:underline"
          style={{ color: 'var(--accent)' }}
        >
          {centre.name}
        </Link>
        <p className="text-[11px]" style={{ color: 'var(--text-disabled)' }}>{centre.state} · {centre.scheme}</p>
      </td>
      <td>
        <span className={`chip ${statusChipClass(centre.status)}`}>
          {statusIcon(centre.status)} {centre.status}
        </span>
      </td>
      <td>
        <span className="text-xs font-mono" style={{ color: minsAgo > 60 ? 'var(--st-amber)' : 'var(--text-secondary)' }}>
          {minsAgo < 60 ? `${minsAgo}m ago` : `${Math.floor(minsAgo / 60)}h ago`}
        </span>
      </td>
      <td>
        {centre.open_flags > 0
          ? <span className="chip chip-red">{centre.open_flags} open</span>
          : <span style={{ color: 'var(--text-disabled)', fontSize: '0.75rem' }}>—</span>}
      </td>
      <td>
        <div className="flex gap-1">
          {centre.suspected_swaps > 0 && (
            <span className="chip chip-swap">↔ {centre.suspected_swaps} swap</span>
          )}
          {centre.suspected_ghosts > 0 && (
            <span className="chip chip-ghost">👻 {centre.suspected_ghosts} ghost</span>
          )}
          {centre.suspected_swaps === 0 && centre.suspected_ghosts === 0 && (
            <span style={{ color: 'var(--text-disabled)', fontSize: '0.75rem' }}>—</span>
          )}
        </div>
      </td>
    </tr>
  );
}

// ── Page ─────────────────────────────────────────────────────────────

export function OverviewPage() {
  const redCentres      = MOCK_CENTRES.filter(c => c.status === 'RED').length;
  const noDataCentres   = MOCK_CENTRES.filter(c => c.status === 'NO-DATA').length;
  const suspectedSwaps  = MOCK_CENTRES.reduce((a, c) => a + c.suspected_swaps, 0);
  const suspectedGhosts = MOCK_CENTRES.reduce((a, c) => a + c.suspected_ghosts, 0);
  const openFlags       = MOCK_FLAGS.filter(f => f.status === 'OPEN').length;

  const priorityQueue = [...MOCK_FLAGS].sort((a, b) => {
    const ord = { HIGH: 0, MEDIUM: 1, LOW: 2 } as const;
    return ord[a.severity] - ord[b.severity];
  });

  return (
    <div className="page-root">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Monitoring Overview
          </h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            Exception-first view · {MOCK_CENTRES.length} centres monitored
          </p>
        </div>
        <span className="simulated-badge">SIMULATED DATA</span>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <KpiCard label="Open RED sessions"  value={redCentres}      sub="Needs review"     icon={AlertTriangle} accent={redCentres > 0}      href="/flags" />
        <KpiCard label="Suspected swaps"    value={suspectedSwaps}  sub="Camera integrity" icon={Camera}        accent={suspectedSwaps > 0}  href="/camera-integrity" />
        <KpiCard label="Suspected ghosts"   value={suspectedGhosts} sub="Ghost batches"    icon={Ghost}         accent={suspectedGhosts > 0} href="/ghost-batches" />
        <KpiCard label="NO-DATA centres"    value={noDataCentres}   sub="Edge offline"     icon={WifiOff}                                    href="/edge-console" />
        <KpiCard label="Open flags"         value={openFlags}       sub="Total active"     icon={Activity}                                   href="/flags" />
      </div>

      {/* Priority queue + trend */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Exception queue */}
        <div className="lg:col-span-2 neu-card overflow-hidden">
          <div
            className="px-4 py-3 flex items-center justify-between"
            style={{ borderBottom: 'var(--edge)' }}
          >
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Priority exception queue
            </h2>
            <Link
              to="/flags"
              className="flex items-center gap-1 text-xs hover:underline"
              style={{ color: 'var(--accent)' }}
            >
              All flags <ArrowRight size={11} />
            </Link>
          </div>
          <div className="neu-well overflow-x-auto" style={{ borderRadius: 0, border: 'none', boxShadow: 'none' }}>
            <table className="pramaan-table min-w-[640px]" role="grid" aria-label="Priority exception queue">
              <thead>
                <tr>
                  {['Centre', 'Type', 'Rule fired', 'SLA', 'Status', ''].map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {priorityQueue.map((flag) => <FlagRow key={flag.id} flag={flag} />)}
              </tbody>
            </table>
          </div>
        </div>

        {/* Trend + latency */}
        <div className="space-y-4">
          <TrendSparkline />
          <div className="neu-card p-4">
            <p className="section-header">Avg evidence latency</p>
            <p className="kpi-value">~4 min</p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-disabled)' }}>
              Design estimate · hypothesis
            </p>
          </div>
          <div className="neu-card p-4">
            <p className="section-header">Bandwidth saving</p>
            <p className="kpi-value text-lg" style={{ color: 'var(--st-green)' }}>~99.97%</p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-disabled)' }}>
              ~250 B/camera·min vs ~2 Mbps stream · design estimate
            </p>
          </div>
        </div>
      </div>

      {/* Centre status table */}
      <div className="neu-card overflow-hidden">
        <div className="px-4 py-3 flex items-center justify-between" style={{ borderBottom: 'var(--edge)' }}>
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            All centres — current status
          </h2>
          <Link
            to="/centres"
            className="flex items-center gap-1 text-xs hover:underline"
            style={{ color: 'var(--accent)' }}
          >
            Map view <ArrowRight size={11} />
          </Link>
        </div>
        <div className="neu-well overflow-x-auto" style={{ borderRadius: 0, border: 'none', boxShadow: 'none' }}>
          <table className="pramaan-table" role="grid" aria-label="Centre status table">
            <thead>
              <tr>
                {['Centre', 'Status', 'Last heartbeat', 'Open flags', 'Integrity flags'].map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {MOCK_CENTRES.map((c) => <CentreRow key={c.id} centre={c} />)}
            </tbody>
          </table>
        </div>
      </div>

      {/* Honesty box */}
      <div className="neu-alert-info">
        <div
          className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5"
          style={{ background: 'rgba(111,140,255,0.2)', color: 'var(--accent)' }}
        >
          <Info size={13} />
        </div>
        <div>
          <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Flags are leads, not penalties
          </p>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            Every flag represents a discrepancy that needs review. It does not confirm misconduct.
            NO-DATA and PENDING states never generate flags. All thresholds are initial hypotheses —
            see{' '}
            <Link to="/settings" style={{ color: 'var(--accent)' }}>Settings → Thresholds</Link>
            {' '}and{' '}
            <Link to="/accuracy" style={{ color: 'var(--accent)' }}>Accuracy &amp; Limits</Link>.
          </p>
        </div>
      </div>
    </div>
  );
}
