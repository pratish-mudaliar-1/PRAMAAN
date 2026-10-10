import React from 'react';
import { AlertTriangle, Info } from 'lucide-react';

export function AccuracyLimitsPage() {
  return (
    <div className="page-root">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Accuracy &amp; Limits
          </h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            Honesty about what this system can and cannot do
          </p>
        </div>
      </div>

      {/* Accuracy banner */}
      <div className="neu-alert-amber">
        <AlertTriangle size={14} style={{ color: 'var(--st-amber)', flexShrink: 0, marginTop: 2 }} />
        <div>
          <p className="text-sm font-semibold" style={{ color: 'var(--st-amber)' }}>
            No accuracy figures have been measured
          </p>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            The demo uses a labelled synthetic dataset. Real-world accuracy on actual training centres has not been evaluated.
            Any accuracy claim would be premature and dishonest.
          </p>
        </div>
      </div>

      {/* No face recognition */}
      <div className="neu-card p-4">
        <p className="section-header">Privacy guarantees</p>
        <div className="space-y-3">
          {[
            { title: 'No face recognition',           desc: 'PRAMAAN does not identify, recognise or track individuals. Person detection returns counts only — no identity or biometric data is stored or transmitted.' },
            { title: 'No person re-identification',   desc: 'Persons are not tracked across frames, zones or sessions. The system cannot say "this person appeared in session A and session B".' },
            { title: 'Evidence blurred',               desc: 'All keyframes shown in the UI have faces and identifying features blurred before transmission. Raw camera frames never leave the edge device.' },
            { title: 'Privacy badge on all evidence', desc: 'Every evidence card shows "Privacy: faces blurred, counts only" so viewers always know the evidence has been processed.' },
          ].map(item => (
            <div key={item.title} className="flex items-start gap-3">
              <div
                className="w-5 h-5 rounded-full shrink-0 mt-0.5 flex items-center justify-center text-xs font-bold"
                style={{ background: 'rgba(61,220,151,0.15)', color: 'var(--st-green)' }}
              >
                ✓
              </div>
              <div>
                <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{item.title}</p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>{item.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Known limitations */}
      <div className="neu-card p-4">
        <p className="section-header">Known limitations</p>
        <div className="space-y-3">
          {[
            { title: 'Mannequins and posters',   desc: 'Person detectors may count mannequins, large photographs or poster cut-outs as persons. Gross discrepancies only — fine-grained counts are not reliable.' },
            { title: 'Off-camera trainees',       desc: 'Trainees seated outside the camera field of view are not counted. Zone coverage factors (k) attempt to compensate but are estimates.' },
            { title: 'Occlusion',                 desc: 'When trainees are obscured by furniture, pillars or equipment, counts are under-estimates. Heavily occluded windows are marked UNCERTAIN.' },
            { title: 'Lighting variation',        desc: 'Poor lighting, glare or sudden changes can affect person and item detection. Registered view baselines capture day and evening references.' },
            { title: 'Labelled demo set only',    desc: 'Confusion matrices in this demo are from the synthetic labelled dataset only. They do not represent performance on real training centres.' },
            { title: 'Camera swaps — IR cameras', desc: 'Infrared and thermal cameras have different scene appearance. Baseline capture must use the correct camera type; mixed baselines may cause false drifts.' },
          ].map(item => (
            <div key={item.title} className="flex items-start gap-3">
              <AlertTriangle size={13} style={{ color: 'var(--st-amber)', flexShrink: 0, marginTop: 3 }} />
              <div>
                <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{item.title}</p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>{item.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Honesty */}
      <div className="neu-card p-4">
        <p className="section-header">System claims vs what's measured</p>
        <div className="neu-well-sm overflow-x-auto">
          <table className="pramaan-table min-w-[500px]">
            <thead>
              <tr>
                <th>Claim</th>
                <th>Status</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              {[
                { claim: 'Attendance ratio accuracy',      status: 'To be measured', note: 'Requires labelled ground-truth sessions from real TCs' },
                { claim: 'Camera swap detection accuracy', status: 'To be measured', note: 'Requires controlled swap experiments on real hardware' },
                { claim: 'Ghost batch precision/recall',   status: 'To be measured', note: 'Requires verified ghost and clean batches from the field' },
                { claim: 'Item detection accuracy',        status: 'To be measured', note: 'Varies by item class, lighting and zone layout' },
                { claim: 'Bandwidth (250 B/cam/min)',      status: 'Design estimate', note: 'Actual size depends on zone count, item list length and signature scheme' },
                { claim: 'Evidence latency (~4 min)',      status: 'Design estimate', note: 'Depends on edge compute capacity and network conditions' },
              ].map(r => (
                <tr key={r.claim}>
                  <td>{r.claim}</td>
                  <td>
                    <span className={`chip ${r.status === 'To be measured' ? 'chip-pending' : 'chip-uncertain'}`}>
                      {r.status}
                    </span>
                  </td>
                  <td><span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{r.note}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="neu-alert-info">
        <Info size={14} style={{ color: 'var(--accent)', flexShrink: 0, marginTop: 2 }} />
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          PRAMAAN is a monitoring aid that generates leads for human review. It is not a judicial system.
          Every flag has a TC response path and an audit trail. No enforcement action should be taken
          based solely on a flag without human review.
        </p>
      </div>
    </div>
  );
}
