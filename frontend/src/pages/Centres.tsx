import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Search, RefreshCw } from 'lucide-react';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import { useCentres } from '@/hooks/useCentres';
import { StatusChip } from '@/components/status/StatusChip';
import 'leaflet/dist/leaflet.css';

const STATUS_COLORS: Record<string, string> = {
  GREEN: '#3ddc97', AMBER: '#ffb84d', RED: '#ff5c6c',
  NO_DATA: '#8b93a7', 'NO-DATA': '#8b93a7', PENDING: '#7da2d6',
};

export function CentresPage() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [view, setView] = useState<'list' | 'map'>('list');

  const { data, isPending, isError, refetch } = useCentres({ limit: 200 });
  const allCentres = data?.items ?? [];

  const filtered = allCentres.filter(c => {
    const matchSearch =
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.state_code.toLowerCase().includes(search.toLowerCase());
    const matchStatus = statusFilter === 'ALL' || (c.status ?? 'GREEN') === statusFilter;
    return matchSearch && matchStatus;
  });

  const statuses = ['ALL', 'RED', 'AMBER', 'GREEN', 'NO_DATA', 'PENDING'];

  return (
    <div className="page-root">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Centres &amp; Map
          </h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            {isPending ? 'Loading…' : `${allCentres.length} training centres monitored`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isPending && <RefreshCw size={14} className="animate-spin" style={{ color: 'var(--text-disabled)' }} />}
          {isError && (
            <button onClick={() => refetch()} className="neu-btn neu-btn-xs" title="Retry">
              Retry
            </button>
          )}
        </div>
      </div>

      {/* Search + filter + view toggle */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-xs">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-disabled)' }} />
          <input
            className="neu-input pl-8"
            placeholder="Search centre, state code…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            aria-label="Search centres"
          />
        </div>

        <div className="neu-segment-group" role="group" aria-label="Filter by status">
          {statuses.map(s => (
            <button
              key={s}
              className={`neu-segment ${statusFilter === s ? 'active' : ''}`}
              onClick={() => setStatusFilter(s)}
            >
              {s === 'ALL' ? 'All' : s.replace(/_/g, ' ')}
            </button>
          ))}
        </div>

        <div className="neu-segment-group" role="group" aria-label="View switcher">
          <button className={`neu-segment ${view === 'list' ? 'active' : ''}`} onClick={() => setView('list')}>List</button>
          <button className={`neu-segment ${view === 'map'  ? 'active' : ''}`} onClick={() => setView('map')}>Map</button>
        </div>
      </div>

      {/* Map view */}
      {view === 'map' && (
        <div className="neu-card overflow-hidden" style={{ height: 420 }}>
          <MapContainer
            center={[22.5, 80]}
            zoom={5}
            style={{ height: '100%', width: '100%' }}
            aria-label="Training centres map"
          >
            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            {filtered.map(c => {
              const lat = c.lat ?? 22.5;
              const lng = c.lng ?? 80;
              const status = c.status ?? 'GREEN';
              return (
                <CircleMarker
                  key={c.id}
                  center={[lat, lng]}
                  radius={10}
                  fillColor={STATUS_COLORS[status] ?? '#8b93a7'}
                  fillOpacity={0.85}
                  color="rgba(255,255,255,0.4)"
                  weight={1}
                >
                  <Popup>
                    <div style={{ background: 'var(--bg-raised)', color: 'var(--text-primary)', padding: 8, minWidth: 180, borderRadius: 8 }}>
                      <p className="font-semibold text-sm">{c.name}</p>
                      <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{c.state_code} · {c.scheme_code}</p>
                      <StatusChip status={status} size="xs" />
                      {(c.open_flags ?? 0) > 0 && <p className="text-xs mt-1" style={{ color: 'var(--st-red)' }}>{c.open_flags} open flag(s)</p>}
                      <Link to={`/centres/${c.id}`} style={{ color: 'var(--accent)', fontSize: 11, display: 'block', marginTop: 4 }}>View detail →</Link>
                    </div>
                  </Popup>
                </CircleMarker>
              );
            })}
          </MapContainer>
        </div>
      )}

      {/* List view */}
      {view === 'list' && (
        <div className="neu-card overflow-hidden">
          <div className="px-4 py-3" style={{ borderBottom: 'var(--edge)' }}>
            <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              {filtered.length} centre{filtered.length !== 1 ? 's' : ''} shown
            </p>
          </div>
          <div className="neu-well overflow-x-auto" style={{ borderRadius: 0, border: 'none', boxShadow: 'none' }}>
            <table className="pramaan-table min-w-[700px]" role="grid" aria-label="Centres list">
              <thead>
                <tr>
                  {['Centre', 'State', 'Scheme', 'Status', 'Open flags', 'Integrity', 'Heartbeat', ''].map(h => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={8} style={{ textAlign: 'center', color: 'var(--text-disabled)', padding: '2rem' }}>
                      No centres match the current filters.
                    </td>
                  </tr>
                ) : filtered.map(c => {
                  const minsAgo = c.last_heartbeat
                    ? Math.floor((Date.now() - new Date(c.last_heartbeat).getTime()) / 60_000)
                    : null;
                  const status = c.status ?? 'GREEN';
                  return (
                    <tr key={c.id}>
                      <td>
                        <Link
                          to={`/centres/${c.id}`}
                          className="font-medium hover:underline"
                          style={{ color: 'var(--accent)' }}
                        >
                          {c.name}
                        </Link>
                      </td>
                      <td style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>{c.state_code}</td>
                      <td style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>{c.scheme_code}</td>
                      <td><StatusChip status={status} /></td>
                      <td>
                        {(c.open_flags ?? 0) > 0
                          ? <span className="chip chip-red">{c.open_flags}</span>
                          : <span style={{ color: 'var(--text-disabled)' }}>—</span>}
                      </td>
                      <td>
                        <div className="flex gap-1 flex-wrap">
                          {(c.suspected_swaps ?? 0) > 0 && <span className="chip chip-swap">↔ {c.suspected_swaps}</span>}
                          {(c.suspected_ghosts ?? 0) > 0 && <span className="chip chip-ghost">👻 {c.suspected_ghosts}</span>}
                          {(c.suspected_swaps ?? 0) === 0 && (c.suspected_ghosts ?? 0) === 0 && (
                            <span style={{ color: 'var(--text-disabled)' }}>—</span>
                          )}
                        </div>
                      </td>
                      <td>
                        <span
                          className="text-xs font-mono"
                          style={{ color: minsAgo && minsAgo > 60 ? 'var(--st-amber)' : 'var(--text-secondary)' }}
                        >
                          {minsAgo !== null ? (minsAgo < 60 ? `${minsAgo}m` : `${Math.floor(minsAgo / 60)}h`) : '—'} ago
                        </span>
                      </td>
                      <td>
                        <Link to={`/centres/${c.id}`} className="neu-btn neu-btn-xs" style={{ textDecoration: 'none' }}>
                          Detail →
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="neu-card p-4">
        <p className="section-header">Status legend</p>
        <div className="flex gap-3 flex-wrap">
          {['GREEN','AMBER','RED','NO_DATA','PENDING'].map(s => (
            <StatusChip key={s} status={s} />
          ))}
        </div>
        <p className="text-xs mt-3" style={{ color: 'var(--text-disabled)' }}>
          NO_DATA = edge offline or camera fault. PENDING = session not yet evaluated.
          None of these generate flags.
        </p>
      </div>
    </div>
  );
}
