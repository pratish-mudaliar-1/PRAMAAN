// ─── Status Types ────────────────────────────────────────────────────────────

export type SessionStatus =
  | 'GREEN' | 'AMBER' | 'RED'
  | 'NO-DATA' | 'PENDING' | 'UNCERTAIN'
  | 'EVIDENCE_COMPROMISED';

export type CameraViewState =
  | 'SAME_VIEW' | 'VIEW_DRIFTED' | 'VIEW_MISMATCH'
  | 'SUSPECTED_SWAP' | 'SWAP_CONFIRMED' | 'REBASELINE_PENDING' | 'UNCERTAIN';

export type GhostStatus =
  | 'CLEAR' | 'WATCH' | 'SUSPECTED_GHOST' | 'ESCALATED';

export type ItemStatus = 'PRESENT' | 'ABSENT' | 'UNCERTAIN';

export type AllStatus = SessionStatus | CameraViewState | GhostStatus | ItemStatus;

// ─── Centre ──────────────────────────────────────────────────────────────────

export interface Centre {
  id: string;
  name: string;
  state: string;
  scheme: string;
  status: SessionStatus;
  lat: number;
  lng: number;
  last_heartbeat: string;
  open_flags: number;
  suspected_swaps: number;
  suspected_ghosts: number;
}

// ─── Camera ───────────────────────────────────────────────────────────────────

export interface Camera {
  id: string;
  centre_id: string;
  zone_id: string;
  label: string;
  model: string;
  mac: string;
  current_baseline_ver: number;
  view_state: CameraViewState;
  last_similarity: number | null;
  last_seen: string;
  anchors_found: number;
  anchors_total: number;
}

export interface CameraBaseline {
  id: string;
  camera_id: string;
  version: number;
  captured_by: string;
  captured_at: string;
  lighting_tag: 'DAY' | 'EVENING';
  status: 'ACTIVE' | 'SUPERSEDED';
  approved_by: string | null;
  phash: string;
}

export interface ViewEvent {
  id: string;
  camera_id: string;
  ts: string;
  similarity: number;
  anchors_found: number;
  anchors_total: number;
  baseline_ver: number;
  state: CameraViewState;
  reason: Record<string, unknown>;
}

// ─── Batch / Session ──────────────────────────────────────────────────────────

export interface Batch {
  id: string;
  centre_id: string;
  trade: string;
  scheme: string;
  start_date: string;
  end_date: string;
  ghost_status: GhostStatus;
  ghost_score: number | null;
}

export interface Session {
  id: string;
  batch_id: string;
  zone_id: string;
  scheduled_start: string;
  scheduled_end: string;
  claimed_count: number;
  trainer_count: number;
  status: SessionStatus;
  observed_p90: number | null;
  ratio: number | null;
  rule_fired: string | null;
}

// ─── Ghost Evaluation ─────────────────────────────────────────────────────────

export interface GhostEvaluation {
  id: string;
  batch_id: string;
  evaluated_at: string;
  window_start: string;
  window_end: string;
  valid_sessions: number;
  ghost_score: number;
  status: GhostStatus;
  indicators: GhostIndicators;
  excluded_sessions: string[];
}

export interface GhostIndicators {
  i1_persistent_shortfall: number;
  i2_near_zero: number;
  i3_claim_uniformity: number;
  i4_out_of_schedule: number;
  i5_room_overlap: number;
  i6_trend: number;
}

// ─── Flag / Case ──────────────────────────────────────────────────────────────

export type FlagType =
  | 'OCCUPANCY' | 'ITEM_ABSENT' | 'FEED_HEALTH'
  | 'DUPLICATE_EVIDENCE' | 'CAMERA_SWAP' | 'GHOST_BATCH';

export type FlagStatus = 'OPEN' | 'TC_RESPONDED' | 'UNDER_REVIEW' | 'CLOSED';

export interface Flag {
  id: string;
  type: FlagType;
  status: FlagStatus;
  centre_id: string;
  centre_name: string;
  rule_fired: string;
  evidence_link: string | null;
  created_at: string;
  sla_deadline: string;
  tc_response: string | null;
  severity: 'HIGH' | 'MEDIUM' | 'LOW';
}

// ─── Audit Log ────────────────────────────────────────────────────────────────

export interface AuditEvent {
  id: string;
  entity_type: string;
  entity_id: string;
  actor: string;
  action: string;
  ts: string;
  note?: string;
}

// ─── Edge / Bandwidth ─────────────────────────────────────────────────────────

export interface EdgeDevice {
  id: string;
  centre_id: string;
  label: string;
  status: 'ONLINE' | 'OFFLINE' | 'DEGRADED';
  queue_depth: number;
  bytes_sent_today: number;
  last_heartbeat: string;
  model_version: string;
}

// ─── Threshold ────────────────────────────────────────────────────────────────

export interface ThresholdConfig {
  key: string;
  value: number;
  label: string;
  hypothesis_note: string;
  modified_by: string;
  modified_at: string;
}

// ─── Observation ─────────────────────────────────────────────────────────────

export interface ObservationPoint {
  ts: string;
  persons: number;
  feed_ok: boolean;
}

export interface ClaimedVsObservedPoint {
  date: string;
  claimed: number;
  observed: number | null;
  status: SessionStatus;
  excluded: boolean;
  ratio: number | null;
}
