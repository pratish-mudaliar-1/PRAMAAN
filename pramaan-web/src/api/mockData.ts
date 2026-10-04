import type {
  Centre, Camera, Session, Batch, GhostEvaluation, Flag,
  AuditEvent, EdgeDevice, ThresholdConfig, ViewEvent,
  ClaimedVsObservedPoint,
} from '@/types';

// â”€â”€â”€ Centres â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export const MOCK_CENTRES: Centre[] = [
  {
    id: 'CTR-A',
    name: 'MSDE Skill Lab Delhi',
    state: 'Delhi',
    scheme: 'PMKVY 4.0',
    status: 'RED',
    lat: 28.6139,
    lng: 77.209,
    last_heartbeat: '2026-10-04T16:55:00+05:30',
    open_flags: 3,
    suspected_swaps: 0,
    suspected_ghosts: 0,
  },
  {
    id: 'CTR-B',
    name: 'Tailoring Hub Jaipur',
    state: 'Rajasthan',
    scheme: 'PMKVY 4.0',
    status: 'AMBER',
    lat: 26.9124,
    lng: 75.7873,
    last_heartbeat: '2026-10-04T16:52:00+05:30',
    open_flags: 2,
    suspected_swaps: 0,
    suspected_ghosts: 0,
  },
  {
    id: 'CTR-C',
    name: 'Computer Centre Pune',
    state: 'Maharashtra',
    scheme: 'DDUGKY',
    status: 'EVIDENCE_COMPROMISED' as any,
    lat: 18.5204,
    lng: 73.8567,
    last_heartbeat: '2026-10-04T17:01:00+05:30',
    open_flags: 1,
    suspected_swaps: 1,
    suspected_ghosts: 0,
  },
  {
    id: 'CTR-D',
    name: 'Skill Centre Patna',
    state: 'Bihar',
    scheme: 'PMKVY 4.0',
    status: 'AMBER',
    lat: 25.5941,
    lng: 85.1376,
    last_heartbeat: '2026-10-04T16:48:00+05:30',
    open_flags: 1,
    suspected_swaps: 0,
    suspected_ghosts: 1,
  },
  {
    id: 'CTR-E',
    name: 'Regional Centre Bhopal',
    state: 'Madhya Pradesh',
    scheme: 'DDUGKY',
    status: 'NO-DATA',
    lat: 23.2599,
    lng: 77.4126,
    last_heartbeat: '2026-10-01T09:00:00+05:30',
    open_flags: 0,
    suspected_swaps: 0,
    suspected_ghosts: 0,
  },
  {
    id: 'CTR-F',
    name: 'Model Centre Bengaluru',
    state: 'Karnataka',
    scheme: 'PMKVY 4.0',
    status: 'GREEN',
    lat: 12.9716,
    lng: 77.5946,
    last_heartbeat: '2026-10-04T17:03:00+05:30',
    open_flags: 0,
    suspected_swaps: 0,
    suspected_ghosts: 0,
  },
];

// â”€â”€â”€ View Events (Camera C â€” swap scenario) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function genViewEvents(): ViewEvent[] {
  const base = new Date('2026-10-04T09:00:00+05:30');
  const events: ViewEvent[] = [];
  const states: Array<[number, string, number]> = [
    // [minutes offset, state, similarity]
    [0, 'SAME_VIEW', 0.89],
    [5, 'SAME_VIEW', 0.87],
    [10, 'SAME_VIEW', 0.91],
    [15, 'SAME_VIEW', 0.86],
    [20, 'SAME_VIEW', 0.88],
    [25, 'SAME_VIEW', 0.84],
    [30, 'SAME_VIEW', 0.82],
    [35, 'VIEW_DRIFTED', 0.71],
    [40, 'VIEW_MISMATCH', 0.28],
    [45, 'VIEW_MISMATCH', 0.21],
    [50, 'SUSPECTED_SWAP', 0.19],
    [55, 'SUSPECTED_SWAP', 0.18],
    [60, 'SUSPECTED_SWAP', 0.22],
    [65, 'SUSPECTED_SWAP', 0.17],
    [70, 'SUSPECTED_SWAP', 0.20],
  ];
  states.forEach(([mins, state, sim], i) => {
    const ts = new Date(base.getTime() + mins * 60000).toISOString();
    events.push({
      id: `VE-${i}`,
      camera_id: 'CAM-C-01',
      ts,
      similarity: sim + (Math.random() - 0.5) * 0.02,
      anchors_found: state === 'SAME_VIEW' ? 8 : state === 'VIEW_DRIFTED' ? 5 : 2,
      anchors_total: 9,
      baseline_ver: 2,
      state: state as any,
      reason: { note: 'Simulated scenario' },
    });
  });
  return events;
}

export const MOCK_VIEW_EVENTS: ViewEvent[] = genViewEvents();

// â”€â”€â”€ Claimed vs Observed (Ghost batch â€” CTR-D) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function genGhostData(): ClaimedVsObservedPoint[] {
  const start = new Date('2026-09-20');
  const points: ClaimedVsObservedPoint[] = [];
  for (let i = 0; i < 14; i++) {
    const d = new Date(start.getTime() + i * 86400000);
    const dateStr = d.toISOString().slice(0, 10);
    const claimed = 28 + Math.floor(Math.random() * 2); // nearly constant
    const observed = 2 + Math.floor(Math.random() * 4); // 2-5
    const ratio = observed / claimed;
    points.push({
      date: dateStr,
      claimed,
      observed,
      status: ratio >= 0.8 ? 'GREEN' : ratio >= 0.5 ? 'AMBER' : 'RED',
      excluded: false,
      ratio,
    });
  }
  // Make days 3, 7, 11 no-data (edge outage)
  [3, 7, 11].forEach((di) => {
    points[di].observed = null;
    points[di].status = 'NO-DATA';
    points[di].excluded = true;
    points[di].ratio = null;
  });
  return points;
}

export const MOCK_GHOST_DATA: ClaimedVsObservedPoint[] = genGhostData();

// â”€â”€â”€ Ghost Evaluation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export const MOCK_GHOST_EVAL: GhostEvaluation = {
  id: 'GE-D-001',
  batch_id: 'BATCH-D-01',
  evaluated_at: '2026-10-04T07:00:00+05:30',
  window_start: '2026-09-20',
  window_end: '2026-10-04',
  valid_sessions: 11,
  ghost_score: 78,
  status: 'SUSPECTED_GHOST',
  indicators: {
    i1_persistent_shortfall: 0.91,
    i2_near_zero: 0.82,
    i3_claim_uniformity: 0.95,
    i4_out_of_schedule: 0.00,
    i5_room_overlap: 0.10,
    i6_trend: 0.60,
  },
  excluded_sessions: ['SES-D-004', 'SES-D-008', 'SES-D-012'],
};

// â”€â”€â”€ Audit Events â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export const MOCK_AUDIT: AuditEvent[] = [
  {
    id: 'AUD-001',
    entity_type: 'flag',
    entity_id: 'FLAG-001',
    actor: 'system',
    action: 'flag_opened',
    ts: '2026-10-04T10:42:00+05:30',
    note: 'Camera similarity dropped to 0.19 â€” VIEW_MISMATCH state entered.',
  },
  {
    id: 'AUD-002',
    entity_type: 'flag',
    entity_id: 'FLAG-001',
    actor: 'system',
    action: 'flag_opened',
    ts: '2026-10-04T10:57:00+05:30',
    note: 'SUSPECTED_SWAP after 3 consecutive mismatch windows.',
  },
  {
    id: 'AUD-003',
    entity_type: 'session',
    entity_id: 'SES-C-009',
    actor: 'system',
    action: 'session_marked_no_data',
    ts: '2026-10-04T11:00:00+05:30',
    note: 'Counts excluded â€” evidence compromised by SUSPECTED_SWAP.',
  },
  {
    id: 'AUD-004',
    entity_type: 'flag',
    entity_id: 'FLAG-001',
    actor: 'officer.ravi@msde.gov.in',
    action: 'flag_reviewed',
    ts: '2026-10-04T14:30:00+05:30',
    note: 'Flagged for field inspection.',
  },
];

// â”€â”€â”€ Threshold configs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export const MOCK_THRESHOLDS: ThresholdConfig[] = [
  {
    key: 'attendance.ratio_green', value: 0.80,
    label: 'Attendance ratio â€” GREEN threshold',
    hypothesis_note: 'Sessions with observed â‰¥ 80% of claimed get GREEN status.',
    modified_by: 'system', modified_at: '2026-09-01T00:00:00Z',
  },
  {
    key: 'attendance.ratio_amber', value: 0.50,
    label: 'Attendance ratio â€” AMBER threshold',
    hypothesis_note: 'Sessions below 50% get RED (if persistent). 50â€“80% get AMBER.',
    modified_by: 'system', modified_at: '2026-09-01T00:00:00Z',
  },
  {
    key: 'attendance.red_persistence_windows', value: 2,
    label: 'Persistence windows for RED status',
    hypothesis_note: 'A session must be below the AMBER threshold in N consecutive check windows before RED is raised.',
    modified_by: 'system', modified_at: '2026-09-01T00:00:00Z',
  },
  {
    key: 'camera.t_same', value: 0.75,
    label: 'Camera â€” SAME_VIEW similarity threshold',
    hypothesis_note: 'Similarity â‰¥ this value â†’ SAME_VIEW. Lower values may cause false drifts.',
    modified_by: 'system', modified_at: '2026-09-01T00:00:00Z',
  },
  {
    key: 'camera.t_mismatch', value: 0.35,
    label: 'Camera â€” VIEW_MISMATCH similarity threshold',
    hypothesis_note: 'Similarity < this value â†’ VIEW_MISMATCH. Above this and below T_same â†’ VIEW_DRIFTED.',
    modified_by: 'system', modified_at: '2026-09-01T00:00:00Z',
  },
  {
    key: 'camera.swap_persist_windows', value: 3,
    label: 'Windows to confirm SUSPECTED_SWAP',
    hypothesis_note: 'Mismatch must persist for N consecutive 5-min windows before SUSPECTED_SWAP is raised.',
    modified_by: 'system', modified_at: '2026-09-01T00:00:00Z',
  },
  {
    key: 'ghost.min_valid_sessions', value: 5,
    label: 'Ghost detection â€” minimum valid sessions',
    hypothesis_note: 'Fewer than this many valid sessions â†’ show "Insufficient evidence", never a ghost verdict.',
    modified_by: 'system', modified_at: '2026-09-01T00:00:00Z',
  },
  {
    key: 'ghost.suspected_score', value: 60,
    label: 'Ghost Score â€” SUSPECTED_GHOST threshold',
    hypothesis_note: 'Ghost Score â‰¥ this â†’ SUSPECTED_GHOST status. Requires human review to escalate.',
    modified_by: 'system', modified_at: '2026-09-01T00:00:00Z',
  },
  {
    key: 'ghost.i1_weight', value: 0.40,
    label: 'Ghost indicator I1 weight (persistent shortfall)',
    hypothesis_note: 'Primary indicator. Higher weight reflects importance of sustained low occupancy.',
    modified_by: 'system', modified_at: '2026-09-01T00:00:00Z',
  },
];

// â”€â”€â”€ Flags â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export const MOCK_FLAGS: Flag[] = [
  {
    id: 'FLAG-001',
    type: 'CAMERA_SWAP',
    status: 'OPEN',
    centre_id: 'CTR-C',
    centre_name: 'Computer Centre Pune',
    rule_fired: 'VIEW_MISMATCH persisted â‰¥ 3 windows; 7 of 9 anchors missing',
    evidence_link: '/camera-integrity/CAM-C-01',
    created_at: '2026-10-04T10:57:00+05:30',
    sla_deadline: '2026-10-06T10:57:00+05:30',
    tc_response: null,
    severity: 'HIGH',
  },
  {
    id: 'FLAG-002',
    type: 'GHOST_BATCH',
    status: 'OPEN',
    centre_id: 'CTR-D',
    centre_name: 'Skill Centre Patna',
    rule_fired: 'Ghost Score 78/100 â€” I1: 91% sessions below 50%, I3: claim uniformity 0.95 CV',
    evidence_link: '/ghost-batches/BATCH-D-01',
    created_at: '2026-10-04T07:00:00+05:30',
    sla_deadline: '2026-10-07T07:00:00+05:30',
    tc_response: null,
    severity: 'HIGH',
  },
  {
    id: 'FLAG-003',
    type: 'OCCUPANCY',
    status: 'TC_RESPONDED',
    centre_id: 'CTR-A',
    centre_name: 'MSDE Skill Lab Delhi',
    rule_fired: 'Session ratio 0.36 (9 observed / 25 claimed) â€” below RED threshold 0.50, 2 windows',
    evidence_link: '/sessions/SES-A-004',
    created_at: '2026-09-28T14:00:00+05:30',
    sla_deadline: '2026-10-05T14:00:00+05:30',
    tc_response: 'Several trainees were on a field visit on this day. Attendance marked in system by error.',
    severity: 'MEDIUM',
  },
  {
    id: 'FLAG-004',
    type: 'ITEM_ABSENT',
    status: 'OPEN',
    centre_id: 'CTR-B',
    centre_name: 'Tailoring Hub Jaipur',
    rule_fired: 'Item class "Industrial Sewing Machine" unseen in 3 unoccluded windows on 2 distinct days',
    evidence_link: '/centres/CTR-B/infrastructure',
    created_at: '2026-10-03T11:00:00+05:30',
    sla_deadline: '2026-10-10T11:00:00+05:30',
    tc_response: null,
    severity: 'MEDIUM',
  },
];

// â”€â”€â”€ Edge devices â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export const MOCK_EDGE_DEVICES: EdgeDevice[] = [
  { id: 'EDGE-A', centre_id: 'CTR-A', label: 'CTR-A Edge Node', status: 'ONLINE',
    queue_depth: 0, bytes_sent_today: 432000, last_heartbeat: '2026-10-04T17:02:00+05:30',
    model_version: 'mock-v1.2.0' },
  { id: 'EDGE-B', centre_id: 'CTR-B', label: 'CTR-B Edge Node', status: 'DEGRADED',
    queue_depth: 3, bytes_sent_today: 398000, last_heartbeat: '2026-10-04T16:59:00+05:30',
    model_version: 'mock-v1.2.0' },
  { id: 'EDGE-C', centre_id: 'CTR-C', label: 'CTR-C Edge Node', status: 'ONLINE',
    queue_depth: 0, bytes_sent_today: 415000, last_heartbeat: '2026-10-04T17:01:00+05:30',
    model_version: 'mock-v1.2.0' },
  { id: 'EDGE-D', centre_id: 'CTR-D', label: 'CTR-D Edge Node', status: 'ONLINE',
    queue_depth: 0, bytes_sent_today: 441000, last_heartbeat: '2026-10-04T17:00:00+05:30',
    model_version: 'mock-v1.2.0' },
  { id: 'EDGE-E', centre_id: 'CTR-E', label: 'CTR-E Edge Node', status: 'OFFLINE',
    queue_depth: 4320, bytes_sent_today: 0, last_heartbeat: '2026-10-01T09:00:00+05:30',
    model_version: 'mock-v1.2.0' },
  { id: 'EDGE-F', centre_id: 'CTR-F', label: 'CTR-F Edge Node', status: 'ONLINE',
    queue_depth: 0, bytes_sent_today: 428000, last_heartbeat: '2026-10-04T17:03:00+05:30',
    model_version: 'mock-v1.2.0' },
];


// ── MOCK_CAMERAS (added by Phase 1) ──────────────────────────────────
export const MOCK_CAMERAS: Camera[] = [
  { id: 'CAM-A-01', centre_id: 'CTR-A', zone_id: 'Z1', label: 'Lab-A Front', model: 'HikVision DS-2CD', mac: 'AA:BB:CC:DD:01:01', current_baseline_ver: 1, view_state: 'SAME_VIEW', last_similarity: 0.91, last_seen: '2026-10-04T17:00:00+05:30', anchors_found: 9, anchors_total: 9 },
  { id: 'CAM-A-02', centre_id: 'CTR-A', zone_id: 'Z2', label: 'Lab-A Rear', model: 'HikVision DS-2CD', mac: 'AA:BB:CC:DD:01:02', current_baseline_ver: 1, view_state: 'SAME_VIEW', last_similarity: 0.88, last_seen: '2026-10-04T17:00:00+05:30', anchors_found: 8, anchors_total: 9 },
  { id: 'CAM-B-01', centre_id: 'CTR-B', zone_id: 'Z1', label: 'Tailoring Front', model: 'Dahua IPC-HFW', mac: 'AA:BB:CC:DD:02:01', current_baseline_ver: 2, view_state: 'VIEW_DRIFTED', last_similarity: 0.72, last_seen: '2026-10-04T16:55:00+05:30', anchors_found: 7, anchors_total: 9 },
  { id: 'CAM-C-01', centre_id: 'CTR-C', zone_id: 'Z1', label: 'Comp-Centre Front', model: 'Axis M3106', mac: 'AA:BB:CC:DD:03:01', current_baseline_ver: 3, view_state: 'SUSPECTED_SWAP', last_similarity: 0.19, last_seen: '2026-10-04T10:42:00+05:30', anchors_found: 2, anchors_total: 9 },
  { id: 'CAM-D-01', centre_id: 'CTR-D', zone_id: 'Z1', label: 'Skill-Centre Main', model: 'HikVision DS-2CD', mac: 'AA:BB:CC:DD:04:01', current_baseline_ver: 1, view_state: 'SAME_VIEW', last_similarity: 0.87, last_seen: '2026-10-04T17:00:00+05:30', anchors_found: 9, anchors_total: 9 },
  { id: 'CAM-E-01', centre_id: 'CTR-E', zone_id: 'Z1', label: 'Offline-Centre Main', model: 'Dahua IPC-HFW', mac: 'AA:BB:CC:DD:05:01', current_baseline_ver: 1, view_state: 'UNCERTAIN', last_similarity: null, last_seen: '2026-10-01T09:00:00+05:30', anchors_found: 0, anchors_total: 8 },
  { id: 'CAM-F-01', centre_id: 'CTR-F', zone_id: 'Z1', label: 'Healthy-Centre Main', model: 'HikVision DS-2CD', mac: 'AA:BB:CC:DD:06:01', current_baseline_ver: 1, view_state: 'SAME_VIEW', last_similarity: 0.94, last_seen: '2026-10-04T17:02:00+05:30', anchors_found: 9, anchors_total: 9 },
];

// ── MOCK_CAMERA_BASELINES ─────────────────────────────────────────────
export const MOCK_CAMERA_BASELINES: CameraBaseline[] = [
  { id: 'BL-C-01-V1', camera_id: 'CAM-C-01', version: 1, captured_by: 'inspector.sharma@msde.gov.in', captured_at: '2026-09-01T10:00:00+05:30', lighting_tag: 'DAY', status: 'SUPERSEDED', approved_by: 'officer.ravi@msde.gov.in', phash: 'a3f2b1c4d5e6f7a8' },
  { id: 'BL-C-01-V2', camera_id: 'CAM-C-01', version: 2, captured_by: 'inspector.sharma@msde.gov.in', captured_at: '2026-09-15T10:00:00+05:30', lighting_tag: 'DAY', status: 'SUPERSEDED', approved_by: 'officer.ravi@msde.gov.in', phash: 'b4a3c2d1e5f6a7b8' },
  { id: 'BL-C-01-V3', camera_id: 'CAM-C-01', version: 3, captured_by: 'inspector.sharma@msde.gov.in', captured_at: '2026-09-25T10:00:00+05:30', lighting_tag: 'DAY', status: 'ACTIVE', approved_by: 'officer.ravi@msde.gov.in', phash: 'c5b4a3d2e1f6a7c8' },
  { id: 'BL-A-01-V1', camera_id: 'CAM-A-01', version: 1, captured_by: 'inspector.mehta@msde.gov.in', captured_at: '2026-09-01T10:00:00+05:30', lighting_tag: 'DAY', status: 'ACTIVE', approved_by: 'officer.ravi@msde.gov.in', phash: 'd6e5f4a3b2c1d7e8' },
  { id: 'BL-F-01-V1', camera_id: 'CAM-F-01', version: 1, captured_by: 'inspector.kumar@msde.gov.in', captured_at: '2026-09-01T10:00:00+05:30', lighting_tag: 'DAY', status: 'ACTIVE', approved_by: 'officer.priya@msde.gov.in', phash: 'e7f6a5b4c3d2e1f8' },
];

// ── MOCK_CAMERA_VIEW_EVENTS (distinct name from genViewEvents) ────────
export const MOCK_CAMERA_VIEW_EVENTS: ViewEvent[] = [
  { id: 'VE-001', camera_id: 'CAM-C-01', ts: '2026-10-04T10:00:00+05:30', similarity: 0.83, anchors_found: 9, anchors_total: 9, baseline_ver: 3, state: 'SAME_VIEW', reason: {} },
  { id: 'VE-002', camera_id: 'CAM-C-01', ts: '2026-10-04T10:05:00+05:30', similarity: 0.81, anchors_found: 9, anchors_total: 9, baseline_ver: 3, state: 'SAME_VIEW', reason: {} },
  { id: 'VE-003', camera_id: 'CAM-C-01', ts: '2026-10-04T10:10:00+05:30', similarity: 0.84, anchors_found: 9, anchors_total: 9, baseline_ver: 3, state: 'SAME_VIEW', reason: {} },
  { id: 'VE-004', camera_id: 'CAM-C-01', ts: '2026-10-04T10:15:00+05:30', similarity: 0.82, anchors_found: 9, anchors_total: 9, baseline_ver: 3, state: 'SAME_VIEW', reason: {} },
  { id: 'VE-005', camera_id: 'CAM-C-01', ts: '2026-10-04T10:20:00+05:30', similarity: 0.85, anchors_found: 9, anchors_total: 9, baseline_ver: 3, state: 'SAME_VIEW', reason: {} },
  { id: 'VE-006', camera_id: 'CAM-C-01', ts: '2026-10-04T10:25:00+05:30', similarity: 0.80, anchors_found: 8, anchors_total: 9, baseline_ver: 3, state: 'SAME_VIEW', reason: {} },
  { id: 'VE-007', camera_id: 'CAM-C-01', ts: '2026-10-04T10:30:00+05:30', similarity: 0.79, anchors_found: 8, anchors_total: 9, baseline_ver: 3, state: 'SAME_VIEW', reason: {} },
  { id: 'VE-008', camera_id: 'CAM-C-01', ts: '2026-10-04T10:35:00+05:30', similarity: 0.41, anchors_found: 5, anchors_total: 9, baseline_ver: 3, state: 'VIEW_MISMATCH', reason: { trigger: 'sim_drop' } },
  { id: 'VE-009', camera_id: 'CAM-C-01', ts: '2026-10-04T10:40:00+05:30', similarity: 0.22, anchors_found: 3, anchors_total: 9, baseline_ver: 3, state: 'VIEW_MISMATCH', reason: { trigger: 'sim_drop' } },
  { id: 'VE-010', camera_id: 'CAM-C-01', ts: '2026-10-04T10:45:00+05:30', similarity: 0.19, anchors_found: 2, anchors_total: 9, baseline_ver: 3, state: 'SUSPECTED_SWAP', reason: { persist: 3 } },
  { id: 'VE-011', camera_id: 'CAM-C-01', ts: '2026-10-04T10:50:00+05:30', similarity: 0.21, anchors_found: 2, anchors_total: 9, baseline_ver: 3, state: 'SUSPECTED_SWAP', reason: { persist: 4 } },
  { id: 'VE-012', camera_id: 'CAM-C-01', ts: '2026-10-04T10:55:00+05:30', similarity: 0.18, anchors_found: 2, anchors_total: 9, baseline_ver: 3, state: 'SUSPECTED_SWAP', reason: { persist: 5 } },
  { id: 'VE-101', camera_id: 'CAM-A-01', ts: '2026-10-04T10:00:00+05:30', similarity: 0.91, anchors_found: 9, anchors_total: 9, baseline_ver: 1, state: 'SAME_VIEW', reason: {} },
  { id: 'VE-102', camera_id: 'CAM-A-01', ts: '2026-10-04T10:30:00+05:30', similarity: 0.89, anchors_found: 9, anchors_total: 9, baseline_ver: 1, state: 'SAME_VIEW', reason: {} },
];

// ── MOCK_BATCHES ──────────────────────────────────────────────────────
export const MOCK_BATCHES: Batch[] = [
  { id: 'BATCH-A-01', centre_id: 'CTR-A', trade: 'Computer Hardware', scheme: 'PMKVY', start_date: '2026-09-15', end_date: '2026-11-15', ghost_status: 'CLEAR', ghost_score: 5 },
  { id: 'BATCH-D-01', centre_id: 'CTR-D', trade: 'Solar Panel Installation', scheme: 'PMKVY', start_date: '2026-09-10', end_date: '2026-11-10', ghost_status: 'SUSPECTED_GHOST', ghost_score: 78 },
  { id: 'BATCH-D-02', centre_id: 'CTR-D', trade: 'Electrician', scheme: 'PMKVY', start_date: '2026-09-05', end_date: '2026-11-05', ghost_status: 'WATCH', ghost_score: 38 },
  { id: 'BATCH-F-01', centre_id: 'CTR-F', trade: 'Healthcare Assistant', scheme: 'PMKVY', start_date: '2026-09-12', end_date: '2026-11-12', ghost_status: 'CLEAR', ghost_score: 4 },
  { id: 'BATCH-B-01', centre_id: 'CTR-B', trade: 'Tailoring & Garment Making', scheme: 'DDUGKY', start_date: '2026-09-18', end_date: '2026-11-18', ghost_status: 'CLEAR', ghost_score: 8 },
];

// ── MOCK_GHOST_EVALUATIONS ────────────────────────────────────────────
export const MOCK_GHOST_EVALUATIONS: GhostEvaluation[] = [
  { id: 'GEVAL-001', batch_id: 'BATCH-D-01', evaluated_at: '2026-10-04T07:00:00+05:30', window_start: '2026-09-20T00:00:00+05:30', window_end: '2026-10-04T00:00:00+05:30', valid_sessions: 9, ghost_score: 78, status: 'SUSPECTED_GHOST', indicators: { i1_persistent_shortfall: 0.91, i2_near_zero: 0.78, i3_claim_uniformity: 0.95, i4_out_of_schedule: 0.10, i5_room_overlap: 0.00, i6_trend: 0.60 }, excluded_sessions: ['SES-D-007'] },
  { id: 'GEVAL-002', batch_id: 'BATCH-D-02', evaluated_at: '2026-10-04T07:00:00+05:30', window_start: '2026-09-20T00:00:00+05:30', window_end: '2026-10-04T00:00:00+05:30', valid_sessions: 6, ghost_score: 38, status: 'WATCH', indicators: { i1_persistent_shortfall: 0.50, i2_near_zero: 0.20, i3_claim_uniformity: 0.40, i4_out_of_schedule: 0.05, i5_room_overlap: 0.00, i6_trend: 0.30 }, excluded_sessions: [] },
  { id: 'GEVAL-003', batch_id: 'BATCH-A-01', evaluated_at: '2026-10-04T07:00:00+05:30', window_start: '2026-09-20T00:00:00+05:30', window_end: '2026-10-04T00:00:00+05:30', valid_sessions: 8, ghost_score: 5, status: 'CLEAR', indicators: { i1_persistent_shortfall: 0.00, i2_near_zero: 0.00, i3_claim_uniformity: 0.08, i4_out_of_schedule: 0.02, i5_room_overlap: 0.00, i6_trend: 0.05 }, excluded_sessions: [] },
  { id: 'GEVAL-004', batch_id: 'BATCH-F-01', evaluated_at: '2026-10-04T07:00:00+05:30', window_start: '2026-09-20T00:00:00+05:30', window_end: '2026-10-04T00:00:00+05:30', valid_sessions: 7, ghost_score: 4, status: 'CLEAR', indicators: { i1_persistent_shortfall: 0.00, i2_near_zero: 0.00, i3_claim_uniformity: 0.06, i4_out_of_schedule: 0.00, i5_room_overlap: 0.00, i6_trend: 0.04 }, excluded_sessions: [] },
];
// phase1 ok
