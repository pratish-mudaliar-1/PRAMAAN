// ─── Status Types ─────────────────────────────────────────────────────────────
// Values match backend enum vocabulary exactly.

/** Backend: attendance_status column on Session. */
export type SessionStatus =
  | 'GREEN' | 'AMBER' | 'RED'
  | 'NO_DATA' | 'PENDING';

/** Backend: camera_integrity_state on CameraIntegrityState. */
export type CameraViewState =
  | 'STABLE'          // was SAME_VIEW
  | 'DRIFT_SUSPECTED' // was VIEW_DRIFTED
  | 'SWAP_SUSPECTED'  // was SUSPECTED_SWAP
  | 'SWAP_CONFIRMED'
  | 'MOVED_CONFIRMED' // new — backend-only state
  | 'RESOLVED'        // camera integrity resolved
  | 'REBASELINED';    // was REBASELINE_PENDING

/** Backend: ghost_assessment_state on GhostAssessment. */
export type GhostStatus =
  | 'NORMAL'         // was CLEAR
  | 'WATCH'
  | 'SUSPECTED_GHOST'
  | 'ESCALATED'
  | 'RESOLVED';

export type ItemStatus = 'PRESENT' | 'ABSENT';

export type AllStatus = SessionStatus | CameraViewState | GhostStatus | ItemStatus;

// ─── Centre ──────────────────────────────────────────────────────────────────
// Note: backend returns state_code/scheme_code; fields mapped on fetch.

export interface Centre {
  id: string;
  name: string;
  code?: string;
  centre_code?: string;
  /** Backend field: state_code */
  state_code: string;
  /** Backend field: scheme_code */
  scheme_code: string;
  district: string;
  registration_no: string;
  is_active: boolean;
  // Derived/aggregated fields — not directly in backend response;
  // populated from /v1/centres/summary or computed client-side:
  status?: SessionStatus;
  open_flags?: number;
  suspected_swaps?: number;
  suspected_ghosts?: number;
  last_heartbeat?: string;
  // Geo — not yet in backend; kept optional for future:
  lat?: number;
  lng?: number;
}

// ─── Camera ───────────────────────────────────────────────────────────────────
// No backend /cameras endpoint yet (BG-01). Types reflect what the model stores.

export interface Camera {
  id: string;
  centre_id: string;
  zone_id: string;
  label?: string;
  camera_code?: string;
  is_active?: boolean;
  location_description?: string;
  model?: string;
  mac?: string;
  current_baseline_ver?: number;
  view_state?: CameraViewState;
  current_state?: string;
  confidence?: number;
  consecutive_suspicious?: number;
  last_similarity?: number | null;
  last_seen?: string;
  anchors_found?: number;
  anchors_total?: number;
  centre_name?: string;
  zone_code?: string;
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
  /** Backend field: ghost_assessment_state */
  ghost_state: GhostStatus;
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
  /** Backend field: attendance_status */
  attendance_status: SessionStatus;
  /** Backend field: attendance_ratio */
  attendance_ratio: number | null;
  last_evaluated_at?: string;
}

// ─── Ghost Assessment ─────────────────────────────────────────────────────────
// Maps to backend GhostAssessment model.

export interface GhostEvaluation {
  id: string;
  batch_id: string;
  centre_id: string;
  /** Backend field: computed_at */
  evaluated_at: string;
  window_start: string;
  window_end: string;
  /** Backend field: eligible_days (days, not session count) */
  eligible_days: number;
  ghost_days: number;
  nodata_days: number;
  untrusted_days: number;
  ghost_score: number;
  /** Backend field: state (ghost_assessment_state) */
  state: GhostStatus;
  /** Backend: JSONB explanation — matches backend keys */
  explanation: GhostExplanation;
  algorithm_version: string;
  per_day_detail?: PerDayDetail[];
}

/** Matches backend GhostAssessment.explanation JSONB keys. */
export interface GhostExplanation {
  persistence?: number;
  magnitude?: number;
  consistency?: number;
  evidence_quality?: number;
  cusum_score?: number;
  [key: string]: number | undefined;
}

export interface PerDayDetail {
  date: string;
  claimed: number;
  o_hat: number | null;
  ratio: number | null;
  /** Backend per_day_status: GHOST | HEALTHY | NO_DATA | UNTRUSTED | PENDING */
  status: 'GHOST' | 'HEALTHY' | 'NO_DATA' | 'UNTRUSTED' | 'PENDING';
  evidence_quality: number | null;
}

// ─── Flag / Case ──────────────────────────────────────────────────────────────
// Values match backend FlagType and FlagStatus enums exactly.

export type FlagType =
  | 'ATTENDANCE_RED'
  | 'ATTENDANCE_AMBER_REPEAT'
  | 'GHOST_BATCH'
  | 'ITEM_ABSENT'
  | 'DEVICE_OFFLINE'
  | 'INTEGRITY_CHAIN_BREAK'
  | 'EVIDENCE_DUPLICATE';

export type FlagStatus =
  | 'OPEN'
  | 'UNDER_REVIEW'
  | 'CLOSED_CONFIRMED'
  | 'CLOSED_DISMISSED';

export interface Flag {
  id: string;
  /** Backend field: flag_type */
  flag_type: FlagType;
  status: FlagStatus;
  centre_id: string;
  session_id: string | null;
  zone_id: string | null;
  /** Backend field: rule_name */
  rule_name: string;
  description: string;
  severity: 'HIGH' | 'MEDIUM' | 'LOW';
  created_at: string;
  updated_at?: string;
  // Snapshot available on detail view only:
  snapshot?: FlagSnapshot;
}

export interface FlagSnapshot {
  inputs: Record<string, unknown>;
  thresholds: Record<string, unknown>;
  model_version: string;
}

// ─── Case ─────────────────────────────────────────────────────────────────────

export type CaseStatus = 'OPEN' | 'TC_RESPONDED' | 'CLOSED';
export type CasePriority = 'HIGH' | 'MEDIUM' | 'LOW';

export interface Case {
  id: string;
  case_number: string;
  centre_id: string;
  title: string;
  description?: string;
  status: CaseStatus;
  priority: CasePriority;
  assigned_to: string;
  sla_breached: boolean;
  created_at: string;
  assigned_at?: string;
  events?: CaseEvent[];
  tc_responses?: TcResponse[];
}

export interface CaseEvent {
  id: string;
  to_status: CaseStatus;
  actor: string;
  note: string;
  occurred_at: string;
}

export interface TcResponse {
  id: string;
  response_text: string;
  submitted_by: string;
  submitted_at: string;
}

// ─── Audit Log ────────────────────────────────────────────────────────────────
// Maps to backend AuditLog model fields.

export interface AuditEvent {
  id: string;
  /** Backend field: resource_type */
  resource_type: string;
  /** Backend field: resource_id */
  resource_id: string;
  actor: string;
  action: string;
  /** Backend field: occurred_at */
  occurred_at: string;
  /** Backend field: detail (JSONB — may contain arbitrary keys) */
  detail?: Record<string, unknown>;
  request_id?: string;
  ip_hash?: string;
}

// ─── Edge Device ──────────────────────────────────────────────────────────────
// Maps to backend Device model. No UI list endpoint yet (BG-06).

export interface EdgeDevice {
  id: string;
  centre_id: string;
  serial_number: string;
  /** Backend device_status: PENDING | ACTIVE | OFFLINE | SUSPENDED | REVOKED */
  status: 'PENDING' | 'ACTIVE' | 'OFFLINE' | 'SUSPENDED' | 'REVOKED';
  last_heartbeat_at: string | null;
  last_seen_at: string | null;
  model_version: string | null;
  firmware_version: string | null;
  last_telemetry: Record<string, unknown> | null;
}

// ─── Threshold ────────────────────────────────────────────────────────────────
// No backend API endpoint yet (BG-03).
// Backend ThresholdProfile has structured columns: t_green, t_amber, repeat_n, etc.

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

/** Used in per-day ghost batch charts. Maps to PerDayDetail shape. */
export interface ClaimedVsObservedPoint {
  date: string;
  claimed: number;
  observed: number | null;
  /** attendance_status-compatible value */
  status: SessionStatus | 'NO_DATA';
  excluded: boolean;
  ratio: number | null;
}
