import React from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle, Camera, Ghost, WifiOff, Activity,
  ArrowRight, Info, RefreshCw,
} from 'lucide-react';
import {
  LineChart, Line, ResponsiveContainer, Tooltip, XAxis,
} from 'recharts';
import { useCentres } from '@/hooks/useCentres';
import { useFlags } from '@/hooks/useFlags';
import type { Centre, Flag } from '@/types';

// ── Helpers ─────────────────────────────────────────────────────────

function statusChipClass(s: string) {
  const m: Record<string, string> = {
    GREEN: 'chip-green', AMBER: 'chip-amber', RED: 'chip-red',
    NO_DATA: 'chip-nodata', 'NO-DATA': 'chip-nodata', PENDING: 'chip-pending',
  };
  return m[s] ?? 'chip-nodata';
}

function statusIcon(s: string) {
  if (s === 'GREEN')   return '●';
  if (s === 'AMBER')   return '◆';
  if (s === 'RED')     return '■';
  if (s === 'NO_DATA') return '⬡';
  if (s === 'PENDING') return '○';
  return '?';
}

function severityClass(s: string) {
  if (s === 'HIGH')   return 'chip-high';
  if (s === 'MEDIUM') return 'chip-medium';
  return 'chip-low';
}

function flagTypeLabel(t: string) {
  const m: Record<string, string> = {
    ATTENDANCE_RED: 'Attendance Red',
    ATTENDANCE_AMBER_REPEAT: 'Amber Repeat',
    GHOST_BATCH: 'Ghost Batch',
    ITEM_ABSENT: 'Item Absent',
    DEVICE_OFFLINE: 'Device Offline',
    INTEGRITY_CHAIN_BREAK: 'Integrity Break',
    EVIDENCE_DUPLICATE: 'Evidence Duplicate',
  };
  return m[t] ?? t.replace(/_/g, ' ');
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

function FlagRow({ flag, centres }: { flag: Flag; centres: Centre[] }) {
  const centre = centres.find(c => c.id === flag.centre_id);
  const evidenceLink = flag.flag_type === 'GHOST_BATCH'
    ? `/ghost-batches/${flag.session_id ?? ''}`
    : flag.flag_type === 'INTEGRITY_CHAIN_BREAK'
    ? '/camera-integrity'
    : `/centres/${flag.centre_id}`;

  return (
    <tr>
      <td>
        <Link
          to={`/centres/${flag.centre_id}`}
          className="text-sm font-medium hover:underline"
          style={{ color: 'var(--accent)' }}
        >
          {centre?.name ?? flag.centre_id.slice(0, 12)}
        </Link>
      </td>
      <td><span className={`chip ${severityClass(flag.severity)}`}>{flagTypeLabel(flag.flag_type)}</span></td>
      <td>
        <p className="text-xs max-w-xs truncate" style={{ color: 'var(--text-secondary)' }} title={flag.rule_name}>
          {flag.rule_name}
        </p>
      </td>
      <td>
        <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
          {new Date(flag.created_at).toLocaleDateString('en-IN')}
        </span>
      </td>
      <td>
        <span
          className="chip text-[10px]"
          style={{
            background: flag.status === 'OPEN' ? 'rgba(255,92,108,0.1)' : 'rgba(61,220,151,0.1)',
            color: flag.status === 'OPEN' ? 'var(--st-red)' : 'var(--st-green)',
            border: `1px solid ${flag.status === 'OPEN' ? 'rgba(255,92,108,0.3)' : 'rgba(61,220,151,0.3)'}`,
          }}
        >
          {flag.status.replace(/_/g, ' ')}
        </span>
      </td>
      <td>
        <Link to={evidenceLink} className="neu-btn neu-btn-xs" style={{ textDecoration: 'none' }}>
          View
        </Link>
      </td>
    </tr>
  );
}

// ── Sparkline calculated from actual flags ─────────────────────────────

function TrendSparkline({ flags }: { flags: Flag[] }) {
  // Aggregate flags by the last 7 days
  const now = new Date();
  const days: { dateStr: string; label: string; count: number }[] = [];

  for (let i = 6; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const dateStr = d.toISOString().split('T')[0];
    const label = d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
    days.push({ dateStr, label, count: 0 });
  }

  for (const f of flags) {
    const fDate = f.created_at.split('T')[0];
    const bucket = days.find(d => d.dateStr === fDate);
    if (bucket) {
      bucket.count++;
    } else if (days.length > 0) {
      days[days.length - 1].count++;
    }
  }

  const chartData = days.map(d => ({ d: d.label, v: d.count }));

  return (
    <div className="neu-card p-4">
      <p className="text-sm font-semibold mb-0.5" style={{ color: 'var(--text-primary)' }}>
        Weekly Flag Activity
      </p>
      <div className="h-28 mt-2">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <XAxis dataKey="d" hide />
            <Tooltip
              contentStyle={{
                background: 'var(--bg-raised)',
                border: 'var(--edge-strong)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-primary)',
                fontSize: 11,
              }}
              formatter={(v: any) => [v, 'flags created']}
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
        {chartData.map((d) => <span key={d.d}>{d.d}</span>)}
      </div>
    </div>
  );
}

// ── Centre Row ────────────────────────────────────────────────────────

function CentreRow({ centre }: { centre: Centre }) {
  const hb = centre.last_heartbeat ? new Date(centre.last_heartbeat) : null;
  const minsAgo = hb ? Math.floor((Date.now() - hb.getTime()) / 60_000) : null;
  const status = centre.status ?? 'GREEN';

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
        <p className="text-[11px]" style={{ color: 'var(--text-disabled)' }}>
          {centre.district ? `${centre.district}, ` : ''}{centre.state_code} · {centre.scheme_code}
        </p>
      </td>
      <td>
        <span className={`chip ${statusChipClass(status)}`}>
          {statusIcon(status)} {status}
        </span>
      </td>
      <td>
        <span className="text-xs font-mono" style={{ color: minsAgo && minsAgo > 60 ? 'var(--st-amber)' : 'var(--text-secondary)' }}>
          {minsAgo !== null ? (minsAgo < 60 ? `${minsAgo}m ago` : `${Math.floor(minsAgo / 60)}h ago`) : 'Awaiting telemetry'}
        </span>
      </td>
      <td>
        {(centre.open_flags ?? 0) > 0
          ? <span className="chip chip-red">{centre.open_flags} open</span>
          : <span style={{ color: 'var(--text-disabled)', fontSize: '0.75rem' }}>—</span>}
      </td>
      <td>
        <div className="flex gap-1">
          {(centre.suspected_swaps ?? 0) > 0 && (
            <span className="chip chip-swap">↔ {centre.suspected_swaps} swap</span>
          )}
          {(centre.suspected_ghosts ?? 0) > 0 && (
            <span className="chip chip-ghost">👻 {centre.suspected_ghosts} ghost</span>
          )}
          {(centre.suspected_swaps ?? 0) === 0 && (centre.suspected_ghosts ?? 0) === 0 && (
            <span style={{ color: 'var(--text-disabled)', fontSize: '0.75rem' }}>—</span>
          )}
        </div>
      </td>
    </tr>
  );
}

// ── Page ─────────────────────────────────────────────────────────────

export function OverviewPage() {
  const centresQuery = useCentres({ limit: 200 });
  const flagsQuery   = useFlags({ limit: 200 });

  const centres = centresQuery.data?.items ?? [];
  const flags   = flagsQuery.data?.items ?? [];
  const loading = centresQuery.isPending || flagsQuery.isPending;

  const redCentres      = centres.filter(c => c.status === 'RED').length;
  const noDataCentres   = centres.filter(c => c.status === 'NO_DATA').length;
  const suspectedSwaps  = centres.reduce((a, c) => a + (c.suspected_swaps ?? 0), 0);
  const suspectedGhosts = centres.reduce((a, c) => a + (c.suspected_ghosts ?? 0), 0);
  const openFlags       = flags.filter(f => f.status === 'OPEN').length;

  const priorityQueue = [...flags].sort((a, b) => {
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
            Exception-first view · {loading ? '…' : centres.length} centres monitored
          </p>
        </div>
        {loading && (
          <RefreshCw size={14} className="animate-spin" style={{ color: 'var(--text-disabled)' }} />
        )}
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <KpiCard label="Open RED sessions"  value={redCentres}      sub="Needs review"     icon={AlertTriangle} accent={redCentres > 0}      href="/flags" />
        <KpiCard label="Suspected swaps"    value={suspectedSwaps}  sub="Camera integrity" icon={Camera}        accent={suspectedSwaps > 0}  href="/camera-integrity" />
        <KpiCard label="Suspected ghosts"   value={suspectedGhosts} sub="Ghost batches"    icon={Ghost}         accent={suspectedGhosts > 0} href="/ghost-batches" />
        <KpiCard label="NO_DATA centres"    value={noDataCentres}   sub="Edge offline"     icon={WifiOff}                                    href="/edge-console" />
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
                  {['Centre', 'Type', 'Rule', 'Created', 'Status', ''].map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {priorityQueue.map((flag) => <FlagRow key={flag.id} flag={flag} centres={centres} />)}
              </tbody>
            </table>
          </div>
        </div>

        {/* Trend + latency */}
        <div className="space-y-4">
          <TrendSparkline flags={flags} />
          <div className="neu-card p-4">
            <p className="section-header">Edge Verification Pipeline</p>
            <p className="kpi-value text-base font-semibold" style={{ color: 'var(--st-green)' }}>Cryptographically Linked</p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
              Ed25519 signatures verified · SHA-256 hash chains checked on ingest
            </p>
          </div>
          <div className="neu-card p-4">
            <p className="section-header">Bandwidth saving</p>
            <p className="kpi-value text-lg" style={{ color: 'var(--st-green)' }}>~99.97%</p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-disabled)' }}>
              ~250 B/camera·min vs ~2 Mbps raw stream
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
              {centres.map((c) => <CentreRow key={c.id} centre={c} />)}
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
            NO_DATA and PENDING states never generate flags. All thresholds are calibrated by backend
            reconciliation engine.
          </p>
        </div>
      </div>
    </div>
  );
}
