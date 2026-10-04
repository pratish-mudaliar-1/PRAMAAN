import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import { StatusChip, STATUS_CONFIG } from '@/components/status/StatusChip';
import { ScoreGauge } from '@/components/status/ScoreGauge';
import { RatioBand } from '@/components/status/RatioBand';
import { SimulatedBadge } from '@/components/shared/SimulatedBadge';
import { SkeletonRows, SkeletonCard } from '@/components/shared/SkeletonRows';
import { EmptyState, ErrorState } from '@/components/shared/EmptyState';
import { RuleExplanationCard } from '@/components/shared/RuleExplanationCard';
import { PersistenceStepper } from '@/components/shared/PersistenceStepper';
import { AuditTimeline } from '@/components/shared/AuditTimeline';
import { ThresholdEditor } from '@/components/shared/ThresholdEditor';
import { BandwidthMeter } from '@/components/shared/BandwidthMeter';
import { EvidenceCard } from '@/components/evidence/EvidenceCard';
import { CompareSlider } from '@/components/evidence/CompareSlider';
import { ClaimedVsObservedChart } from '@/components/charts/ClaimedVsObservedChart';
import { SimilarityTimeline } from '@/components/charts/SimilarityTimeline';
import { SessionHeatmap } from '@/components/charts/SessionHeatmap';
import { ScoreBreakdownBars } from '@/components/charts/ScoreBreakdownBars';
import {
  MOCK_AUDIT, MOCK_THRESHOLDS, MOCK_VIEW_EVENTS,
  MOCK_GHOST_DATA, MOCK_GHOST_EVAL,
} from '@/api/mockData';
import { CheckSquare, InboxIcon } from 'lucide-react';

// ─── Section wrapper ──────────────────────────────────────────────────────────

function Section({ title, id, children }: { title: string; id: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-6">
      <h2 className="text-lg font-semibold text-slate-800 mb-3 flex items-center gap-2">
        <span className="text-xs font-mono text-slate-400 bg-slate-100 px-2 py-0.5 rounded">#{id}</span>
        {title}
      </h2>
      <div className="space-y-4">{children}</div>
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="card p-4">
      <p className="text-xs font-mono text-slate-400 mb-3 uppercase tracking-wide">{label}</p>
      <div className="flex flex-wrap gap-3 items-center">{children}</div>
    </div>
  );
}

// ─── TOC ─────────────────────────────────────────────────────────────────────

const TOC = [
  { id: 'status-chip', label: '1. StatusChip' },
  { id: 'score-gauge', label: '2. ScoreGauge' },
  { id: 'ratio-band', label: '3. RatioBand' },
  { id: 'simulated-badge', label: '4. SimulatedBadge' },
  { id: 'empty-error', label: '5. EmptyState / ErrorState' },
  { id: 'skeleton', label: '6. SkeletonRows' },
  { id: 'rule-card', label: '7. RuleExplanationCard' },
  { id: 'persistence', label: '8. PersistenceStepper' },
  { id: 'audit', label: '9. AuditTimeline' },
  { id: 'threshold', label: '10. ThresholdEditor' },
  { id: 'bandwidth', label: '11. BandwidthMeter' },
  { id: 'evidence-card', label: '12. EvidenceCard' },
  { id: 'compare-slider', label: '13. CompareSlider' },
  { id: 'cvo-chart', label: '14. ClaimedVsObservedChart' },
  { id: 'similarity', label: '15. SimilarityTimeline' },
  { id: 'heatmap', label: '16. SessionHeatmap' },
  { id: 'score-bars', label: '17. ScoreBreakdownBars' },
  { id: 'status-semantics', label: '18. Status Semantics Table' },
];

// ─── Main Gallery ─────────────────────────────────────────────────────────────

export function ComponentGallery() {
  const [thresholds, setThresholds] = useState(MOCK_THRESHOLDS.slice(0, 4));

  const ANCHOR_DEMO = [
    { x: 12, y: 18, found: true, label: 'whiteboard' },
    { x: 38, y: 55, found: true, label: 'machine-1' },
    { x: 55, y: 55, found: false, label: 'machine-2' },
    { x: 72, y: 55, found: false, label: 'machine-3' },
    { x: 82, y: 12, found: false, label: 'door' },
    { x: 25, y: 32, found: true, label: 'bench-1' },
    { x: 65, y: 32, found: false, label: 'window' },
  ];

  return (
    <div className="min-h-screen bg-[#F8FAFC]">
      {/* Page header */}
      <div className="bg-white border-b border-slate-200 px-6 py-4 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto flex items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-slate-900">PRAMAAN Component Gallery</h1>
            <p className="text-sm text-slate-500 mt-0.5">
              Phase 1 design system · 18 components · All status variants
            </p>
          </div>
          <div className="flex items-center gap-2">
            <SimulatedBadge />
            <span className="text-xs text-slate-400">Phase 1</span>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-8 flex gap-8">
        {/* Sticky TOC */}
        <aside className="w-48 shrink-0 hidden lg:block">
          <nav className="sticky top-24 space-y-1" aria-label="Gallery navigation">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Components</p>
            {TOC.map((item) => (
              <a
                key={item.id}
                href={`#${item.id}`}
                className={cn(
                  'block text-xs text-slate-500 hover:text-[#3B5BDB] py-1 px-2 rounded',
                  'hover:bg-[#E7EEFE] transition-colors',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#3B5BDB]',
                )}
              >
                {item.label}
              </a>
            ))}
          </nav>
        </aside>

        {/* Content */}
        <main className="flex-1 space-y-12 min-w-0">

          {/* 1. StatusChip */}
          <Section title="StatusChip" id="status-chip">
            <Row label="Session / Item statuses — SM">
              {['GREEN','AMBER','RED','NO-DATA','PENDING','UNCERTAIN','EVIDENCE_COMPROMISED',
                'PRESENT','ABSENT'].map((s) => (
                <StatusChip key={s} status={s} size="sm" />
              ))}
            </Row>
            <Row label="Camera view states — MD">
              {['SAME_VIEW','VIEW_DRIFTED','VIEW_MISMATCH','SUSPECTED_SWAP',
                'SWAP_CONFIRMED','REBASELINE_PENDING'].map((s) => (
                <StatusChip key={s} status={s} size="md" />
              ))}
            </Row>
            <Row label="Ghost statuses — LG">
              {['CLEAR','WATCH','SUSPECTED_GHOST','ESCALATED'].map((s) => (
                <StatusChip key={s} status={s} size="lg" />
              ))}
            </Row>
            <Row label="Icon only (SM)">
              {['GREEN','AMBER','RED','NO-DATA','PENDING','UNCERTAIN'].map((s) => (
                <StatusChip key={s} status={s} size="sm" showLabel={false} />
              ))}
            </Row>
            <div className="card p-3 bg-amber-50 border border-amber-200">
              <p className="text-xs text-amber-800 font-medium">
                ✓ All status chips use icon + label + pattern (colour is never the sole differentiator).
                NO-DATA uses a hatch background; PENDING uses a dashed border; UNCERTAIN uses a dot pattern.
              </p>
            </div>
          </Section>

          {/* 2. ScoreGauge */}
          <Section title="ScoreGauge" id="score-gauge">
            <Row label="Various scores">
              <ScoreGauge score={78} label="CTR-D Ghost" />
              <ScoreGauge score={42} label="CTR-A Near-miss" />
              <ScoreGauge score={12} label="CTR-F Healthy" />
              <ScoreGauge score={100} label="Max score" />
              <ScoreGauge score={0} label="Min score" />
              <ScoreGauge score={null} label="Insufficient data" />
            </Row>
            <Row label="Large size (128px)">
              <ScoreGauge score={78} size={128} label="Suspected Ghost" />
              <ScoreGauge score={null} size={128} label="Unavailable" />
            </Row>
          </Section>

          {/* 3. RatioBand */}
          <Section title="RatioBand" id="ratio-band">
            <div className="card p-4 space-y-3">
              <p className="text-xs font-mono text-slate-400 uppercase tracking-wide mb-2">
                Ratio from 0 to 1 — threshold markers at 50% and 80%
              </p>
              {[1.0, 0.85, 0.72, 0.50, 0.36, 0.09, null].map((r, i) => (
                <div key={i} className="flex items-center gap-3">
                  <span className="text-xs text-slate-500 w-20 text-right shrink-0 font-mono">
                    ratio = {r ?? 'null'}
                  </span>
                  <RatioBand ratio={r} className="flex-1" />
                </div>
              ))}
            </div>
          </Section>

          {/* 4. SimulatedBadge */}
          <Section title="SimulatedBadge" id="simulated-badge">
            <Row label="Pill variant">
              <SimulatedBadge variant="pill" />
            </Row>
            <div className="card overflow-hidden">
              <SimulatedBadge variant="bar" />
              <p className="p-4 text-sm text-slate-600">
                The bar variant is always shown at the very top of the application shell.
                It cannot be dismissed.
              </p>
            </div>
          </Section>

          {/* 5. EmptyState / ErrorState */}
          <Section title="EmptyState & ErrorState" id="empty-error">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="card">
                <EmptyState
                  title="No flags to review"
                  message="All centres are within expected parameters for this date range."
                  icon={InboxIcon}
                />
              </div>
              <div className="card">
                <ErrorState
                  message="Unable to load camera events. The edge device may be offline."
                  recoverable={true}
                  onRetry={() => alert('Retry clicked')}
                />
              </div>
              <div className="card">
                <EmptyState
                  title="Insufficient evidence"
                  message="This batch has fewer than 5 valid sessions. No ghost verdict can be issued."
                  icon={CheckSquare}
                  action={<button className="text-xs text-[#3B5BDB] underline">Request field inspection</button>}
                />
              </div>
              <div className="card">
                <ErrorState
                  message="Database connection lost. Contact system administrator."
                  recoverable={false}
                />
              </div>
            </div>
          </Section>

          {/* 6. SkeletonRows */}
          <Section title="SkeletonRows & SkeletonCard" id="skeleton">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="card overflow-hidden">
                <p className="text-xs font-mono text-slate-400 px-4 pt-4 uppercase tracking-wide">Table skeleton</p>
                <SkeletonRows rows={4} cols={5} />
              </div>
              <div className="space-y-3">
                <SkeletonCard />
                <SkeletonCard />
              </div>
            </div>
          </Section>

          {/* 7. RuleExplanationCard */}
          <Section title="RuleExplanationCard" id="rule-card">
            <RuleExplanationCard
              ruleName="Attendance ratio below RED threshold (0.50) — 2 consecutive windows"
              numbers="Observed: 9 persons · Claimed: 25 · Ratio: 0.36 (36%)"
              timeWindow="28 Sep 2026, 09:30–12:30 (core session window)"
              detail="The P90 person count across the session's core window was 9. This was checked in 2 consecutive 30-minute check windows, both below the 0.50 threshold. The session has been marked RED."
              evidenceLink="#"
            />
            <RuleExplanationCard
              ruleName="Camera similarity below mismatch threshold — SUSPECTED_SWAP"
              numbers="Similarity: 0.19 · Anchors found: 2/9 · Baseline: v2"
              timeWindow="4 Oct 2026, 10:42–11:12 (3 consecutive 5-min windows)"
              detail="Scene similarity fell from 0.83 to 0.19 at 10:42 and stayed below 0.35 for 15 minutes. 7 of 9 registered anchors not found. No feed-health fault detected. Counts from this camera were excluded from reconciliation."
            />
          </Section>

          {/* 8. PersistenceStepper */}
          <Section title="PersistenceStepper" id="persistence">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="card p-4">
                <p className="text-xs font-mono text-slate-400 mb-3">3/3 — SUSPECTED_SWAP confirmed</p>
                <PersistenceStepper filled={3} total={5} required={3} currentState="SUSPECTED_SWAP" />
              </div>
              <div className="card p-4">
                <p className="text-xs font-mono text-slate-400 mb-3">2/3 — not yet confirmed</p>
                <PersistenceStepper filled={2} total={5} required={3} currentState="VIEW_MISMATCH" />
              </div>
              <div className="card p-4">
                <p className="text-xs font-mono text-slate-400 mb-3">0/2 — clear</p>
                <PersistenceStepper filled={0} total={5} required={2} currentState="SAME_VIEW" />
              </div>
              <div className="card p-4">
                <p className="text-xs font-mono text-slate-400 mb-3">RED persistence — 2/2</p>
                <PersistenceStepper filled={2} total={4} required={2} currentState="RED" />
              </div>
            </div>
          </Section>

          {/* 9. AuditTimeline */}
          <Section title="AuditTimeline" id="audit">
            <div className="card p-4">
              <AuditTimeline events={MOCK_AUDIT} />
            </div>
          </Section>

          {/* 10. ThresholdEditor */}
          <Section title="ThresholdEditor" id="threshold">
            <div className="card p-4 space-y-4 divide-y divide-slate-100">
              {thresholds.map((t, i) => (
                <div key={t.key} className={i > 0 ? 'pt-4' : ''}>
                  <ThresholdEditor
                    config={t}
                    onSave={async (key, val) => {
                      setThresholds((prev) =>
                        prev.map((p) => p.key === key ? { ...p, value: val } : p)
                      );
                    }}
                  />
                </div>
              ))}
            </div>
            <div className="card p-4 space-y-4 divide-y divide-slate-100 opacity-70">
              <p className="text-xs font-mono text-slate-400 mb-2">Read-only variant (auditor role)</p>
              <ThresholdEditor config={thresholds[0]} readonly />
            </div>
          </Section>

          {/* 11. BandwidthMeter */}
          <Section title="BandwidthMeter" id="bandwidth">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <BandwidthMeter bytesSent={432000} cameras={4} minutesOnline={1440} />
              <BandwidthMeter bytesSent={0} cameras={4} minutesOnline={0} />
            </div>
          </Section>

          {/* 12. EvidenceCard */}
          <Section title="EvidenceCard" id="evidence-card">
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
              <EvidenceCard
                timestamp="2026-09-28T10:45:00+05:30"
                personCount={9}
                zone="Zone A — Lab"
                sessionId="SES-A-004"
                privacyNote={true}
              />
              <EvidenceCard
                timestamp="2026-10-04T10:42:00+05:30"
                personCount={22}
                zone="Zone B — Hall"
                sessionId="SES-C-009"
                privacyNote={true}
              />
              <EvidenceCard
                timestamp="2026-09-22T14:10:00+05:30"
                personCount={3}
                zone="Zone A — Lab"
                sessionId="SES-D-003"
                privacyNote={true}
              />
            </div>
          </Section>

          {/* 13. CompareSlider */}
          <Section title="CompareSlider" id="compare-slider">
            <CompareSlider
              beforeLabel="Registered baseline (Day, v2)"
              afterLabel="Current frame — 4 Oct 10:42"
              anchors={ANCHOR_DEMO}
            />
            <div className="card p-3 bg-slate-50">
              <p className="text-xs text-slate-500">
                Green dots = anchors found in current frame. Red dots = registered anchors not found.
                Drag the handle to compare the registered view against the current frame.
              </p>
            </div>
          </Section>

          {/* 14. ClaimedVsObservedChart */}
          <Section title="ClaimedVsObservedChart" id="cvo-chart">
            <ClaimedVsObservedChart
              data={MOCK_GHOST_DATA}
              title="CTR-D Skill Centre Patna — Batch BATCH-D-01 (last 14 days)"
            />
          </Section>

          {/* 15. SimilarityTimeline */}
          <Section title="SimilarityTimeline" id="similarity">
            <SimilarityTimeline
              events={MOCK_VIEW_EVENTS}
              tSame={0.75}
              tMismatch={0.35}
            />
          </Section>

          {/* 16. SessionHeatmap */}
          <Section title="SessionHeatmap" id="heatmap">
            <SessionHeatmap data={MOCK_GHOST_DATA} />
          </Section>

          {/* 17. ScoreBreakdownBars */}
          <Section title="ScoreBreakdownBars" id="score-bars">
            <ScoreBreakdownBars
              indicators={MOCK_GHOST_EVAL.indicators}
              ghostScore={MOCK_GHOST_EVAL.ghost_score}
            />
          </Section>

          {/* 18. Status Semantics Table */}
          <Section title="Status Semantics Reference" id="status-semantics">
            <div className="card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse" role="grid" aria-label="Status semantics reference table">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-200">
                      <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Chip</th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Pattern</th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Meaning</th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Can become RED/Ghost?</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {[
                      ['GREEN', 'Solid', 'Ratio ≥ 0.80', '—'],
                      ['AMBER', 'Solid', 'Ratio 0.50–0.80', '—'],
                      ['RED', 'Solid', 'Ratio < 0.50, persistent', '—'],
                      ['NO-DATA', 'Hatch', 'Camera/edge offline', '✗ Never'],
                      ['PENDING', 'Dashed border', 'Session incomplete', '✗ Never'],
                      ['UNCERTAIN', 'Dot pattern', 'Occlusion or ambiguity', '✗ Never'],
                      ['EVIDENCE_COMPROMISED', 'Solid + ShieldOff icon', 'Counts excluded (swap active)', '✗ — NO-DATA instead'],
                      ['SAME_VIEW', 'Solid', 'Similarity ≥ T_same', '—'],
                      ['VIEW_DRIFTED', 'Solid', 'T_mismatch ≤ sim < T_same', '—'],
                      ['VIEW_MISMATCH', 'Solid', 'sim < T_mismatch, 1 window', '—'],
                      ['SUSPECTED_SWAP', 'Solid', 'Mismatch persists ≥ M windows', 'Excluded from reconciliation'],
                      ['SWAP_CONFIRMED', 'Solid', 'Confirmed by reviewer/inspector', '—'],
                      ['REBASELINE_PENDING', 'Dashed', 'Approved change in progress', '✗ Not a swap'],
                      ['CLEAR', 'Solid', 'Ghost score low', '—'],
                      ['WATCH', 'Solid', 'Ghost score rising', '—'],
                      ['SUSPECTED_GHOST', 'Solid', 'Ghost score high; human review needed', '—'],
                      ['ESCALATED', 'Solid', 'Human-escalated; inspection ordered', '—'],
                    ].map(([status, pattern, meaning, note]) => (
                      <tr key={status} className="hover:bg-slate-50 transition-colors">
                        <td className="px-4 py-2.5">
                          <StatusChip status={status} size="sm" />
                        </td>
                        <td className="px-4 py-2.5 text-xs text-slate-600">{pattern}</td>
                        <td className="px-4 py-2.5 text-xs text-slate-600 max-w-[200px]">{meaning}</td>
                        <td className="px-4 py-2.5 text-xs text-slate-500">{note || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="card p-3 bg-green-50 border-green-200">
              <p className="text-xs text-green-800 font-medium">
                ✓ Principle: NO-DATA, PENDING, UNCERTAIN, EVIDENCE_COMPROMISED, and REBASELINE_PENDING
                can NEVER become RED, SUSPECTED_GHOST, SUSPECTED_SWAP, or ABSENT verdicts.
              </p>
            </div>
          </Section>

          {/* Footer */}
          <div className="border-t border-slate-200 pt-8 pb-4 text-center">
            <p className="text-sm text-slate-500">
              PRAMAAN Component Gallery · Phase 1 · SIH 2026 PS 26245
            </p>
            <p className="text-xs text-slate-400 mt-1">
              All data shown is simulated. No real monitoring output.
            </p>
            <SimulatedBadge className="mx-auto mt-2" />
          </div>

        </main>
      </div>
    </div>
  );
}
