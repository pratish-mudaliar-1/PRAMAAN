# PRAMAAN Frontend Inventory
Phase 0 - read-only. All data from code inspection.

## 1. Routes & Screens

| Route | Component | Data source | Mock data used |
|---|---|---|---|
| / | OverviewPage | MOCK_CENTRES, MOCK_FLAGS, hardcoded TREND_DATA | YES - all mock |
| /centres | CentresPage | MOCK_CENTRES | YES |
| /centres/:id | CentreDetailPage | MOCK_CENTRES, MOCK_CAMERAS, MOCK_BATCHES, MOCK_GHOST_EVALUATIONS | YES |
| /flags | FlagsCasesPage | MOCK_FLAGS | YES |
| /camera-integrity | CameraIntegrityPage | MOCK_CAMERAS, MOCK_CAMERA_BASELINES, MOCK_VIEW_EVENTS | YES |
| /camera-integrity/:cameraId | CameraIntegrityPage | same | YES |
| /ghost-batches | GhostBatchesPage | MOCK_GHOST_EVALUATIONS, MOCK_BATCHES | YES |
| /ghost-batches/:batchId | GhostBatchesPage | same | YES |
| /edge-console | EdgeConsolePage | MOCK_EDGE_DEVICES | YES |
| /settings | SettingsPage | MOCK_THRESHOLDS | YES |
| /audit-log | AuditLogPage | MOCK_AUDIT | YES |
| /accuracy | AccuracyLimitsPage | Hardcoded static text | N/A (static) |
| /gallery | ComponentGallery | None (design reference) | N/A |

ALL routes currently use 100% mock data. Zero real API calls exist in the application.

## 2. Frontend Types vs Backend Reality

### Centre type (frontend types.ts)
Fields: id, name, state, scheme, status, lat, lng, last_heartbeat, open_flags, suspected_swaps, suspected_ghosts

Backend returns: id, name, code, state_code, district, scheme_code, registration_no, is_active
MISMATCHES: state vs state_code, scheme vs scheme_code, status MISSING, lat/lng MISSING, last_heartbeat MISSING, open_flags/suspected_swaps/suspected_ghosts MISSING

### Session type (frontend types.ts)
Fields: id, batch_id, zone_id, scheduled_start, scheduled_end, claimed_count, trainer_count, status, observed_p90, ratio, rule_fired

Backend returns: id, batch_id, zone_id, scheduled_start, scheduled_end, claimed_count, trainer_count, attendance_status, attendance_ratio
MISMATCHES: status vs attendance_status, observed_p90 MISSING, ratio vs attendance_ratio, rule_fired MISSING

### SessionStatus enum (frontend)
GREEN, AMBER, RED, NO-DATA, PENDING, UNCERTAIN, EVIDENCE_COMPROMISED

Backend attendance_status: GREEN, AMBER, RED, NO_DATA, PENDING
MISMATCHES: NO-DATA vs NO_DATA (hyphen vs underscore), UNCERTAIN and EVIDENCE_COMPROMISED do not exist in backend

### Flag type (frontend)
Fields: id, type, status, centre_id, centre_name, rule_fired, evidence_link, created_at, sla_deadline, tc_response, severity

Backend returns: id, flag_type, status, centre_id, session_id, zone_id, rule_name, description, created_at, severity
MISMATCHES: type vs flag_type, rule_fired vs rule_name (different semantics), centre_name MISSING, evidence_link MISSING, sla_deadline MISSING, tc_response MISSING

### FlagType enum (frontend)
OCCUPANCY, ITEM_ABSENT, FEED_HEALTH, DUPLICATE_EVIDENCE, CAMERA_SWAP, GHOST_BATCH

Backend flag_type: ATTENDANCE_RED, ATTENDANCE_AMBER_REPEAT, GHOST_BATCH, ITEM_ABSENT, DEVICE_OFFLINE, INTEGRITY_CHAIN_BREAK, EVIDENCE_DUPLICATE
MISMATCHES: OCCUPANCY does not exist (backend uses ATTENDANCE_RED/AMBER_REPEAT), FEED_HEALTH does not exist, DUPLICATE_EVIDENCE vs EVIDENCE_DUPLICATE, CAMERA_SWAP does not exist (backend uses INTEGRITY_CHAIN_BREAK)

### FlagStatus enum (frontend)
OPEN, TC_RESPONDED, UNDER_REVIEW, CLOSED

Backend flag_status: OPEN, UNDER_REVIEW, CLOSED_CONFIRMED, CLOSED_DISMISSED
MISMATCHES: TC_RESPONDED does not exist in backend flags (it's a Case status), CLOSED does not exist (backend has CLOSED_CONFIRMED, CLOSED_DISMISSED)

### GhostEvaluation type (frontend)
Fields: id, batch_id, evaluated_at, window_start, window_end, valid_sessions, ghost_score, status, indicators (i1-i6), excluded_sessions

Backend GhostAssessment: id, batch_id, centre_id, window_start, window_end, eligible_days, ghost_days, nodata_days, untrusted_days, pending_days, per_day_detail, ghost_score, state, explanation, algorithm_version, computed_at
MISMATCHES: valid_sessions vs eligible_days, status vs state (CLEAR does not exist in backend - backend has NORMAL), indicators (i1-i6 do not exist - backend has explanation JSONB with persistence/magnitude/consistency/evidence_quality/cusum_score), excluded_sessions MISSING

### GhostStatus enum (frontend)
CLEAR, WATCH, SUSPECTED_GHOST, ESCALATED

Backend ghost_assessment_state: NORMAL, WATCH, SUSPECTED_GHOST, ESCALATED, RESOLVED
MISMATCH: CLEAR vs NORMAL

### Camera type (frontend)
Fields: id, centre_id, zone_id, label, model, mac, current_baseline_ver, view_state, last_similarity, last_seen, anchors_found, anchors_total

Backend has NO camera endpoint. CameraIntegrityState model exists with: camera_id, state (different vocabulary), since, confidence, explanation. NO cameras list API.

### CameraViewState enum (frontend)
SAME_VIEW, VIEW_DRIFTED, VIEW_MISMATCH, SUSPECTED_SWAP, SWAP_CONFIRMED, REBASELINE_PENDING, UNCERTAIN

Backend camera_integrity_state: STABLE, DRIFT_SUSPECTED, SWAP_SUSPECTED, SWAP_CONFIRMED, MOVED_CONFIRMED, RESOLVED, REBASELINED
MISMATCHES: SAME_VIEW vs STABLE, VIEW_DRIFTED vs DRIFT_SUSPECTED, VIEW_MISMATCH does not exist, SUSPECTED_SWAP vs SWAP_SUSPECTED, REBASELINE_PENDING vs REBASELINED, UNCERTAIN does not exist, MOVED_CONFIRMED not in frontend

### AuditEvent type (frontend)
Fields: id, entity_type, entity_id, actor, action, ts, note

Backend AuditLog: id, actor, action, resource_type, resource_id, request_id, ip_hash, detail (JSONB), row_hash, prev_hash, occurred_at
MISMATCHES: entity_type vs resource_type, entity_id vs resource_id, ts vs occurred_at, note vs detail (JSONB), backend has no API endpoint

### EdgeDevice type (frontend)
Fields: id, centre_id, label, status (ONLINE/OFFLINE/DEGRADED), queue_depth, bytes_sent_today, last_heartbeat, model_version

Backend Device: status is PENDING/ACTIVE/OFFLINE/SUSPENDED/REVOKED (different vocab), has last_telemetry JSONB with queue_depth etc, last_heartbeat_at, model_version. No UI list endpoint.
MISMATCHES: status vocab, bytes_sent_today MISSING, label MISSING, DEGRADED does not exist, ONLINE does not exist (backend uses ACTIVE)

### ThresholdConfig type (frontend)
Fields: key, value, label, hypothesis_note, modified_by, modified_at

Backend ThresholdProfile: id, scheme_code, state_code, version, is_active, approved_by, approved_at, t_green, t_amber, repeat_n, min_feed_health_fraction, item_absent_min_windows, item_absent_min_days, phash_hamming_threshold, extra (JSONB)
No API endpoint. Frontend treats thresholds as flat key/value pairs; backend has structured columns.

## 3. Every API Call Made

NONE. The frontend makes zero API calls. All data comes from MOCK_DATA constants in src/api/mockData.ts.

## 4. WebSocket Subscriptions

NONE. No WebSocket or SSE connections.

## 5. Hardcoded / Fabricated Values

- TREND_DATA in Overview.tsx: hardcoded 7-day flag trend (lines 137-140)
- "~4 min" evidence latency in Overview.tsx: hardcoded estimate (line 312)
- "~99.97%" bandwidth saving in Overview.tsx: hardcoded estimate (line 319)
- All centre data: MOCK_CENTRES (6 centres with fictional names and coords)
- All flag data: MOCK_FLAGS (4 flags)
- All ghost batch data: MOCK_GHOST_EVALUATIONS, MOCK_BATCHES
- All camera data: MOCK_CAMERAS, MOCK_CAMERA_BASELINES, MOCK_VIEW_EVENTS
- All edge device data: MOCK_EDGE_DEVICES
- All threshold data: MOCK_THRESHOLDS
- All audit data: MOCK_AUDIT

## 6. Dead Code / Unused Components

- ComponentGallery (/gallery route) - design reference only, not production UI
- SimulatedBadge component - correct to have, shows SIMULATED DATA badge
- MOCK_GHOST_DATA export in mockData.ts - never imported (only MOCK_GHOST_EVALUATIONS is used)
- MOCK_VIEW_EVENTS and MOCK_CAMERA_VIEW_EVENTS both defined; only one may be used

## 7. any Casts on API Data

- MOCK_CENTRES[2].status: 'EVIDENCE_COMPROMISED' as any (mockData.ts line 41) - status not in SessionStatus type
- ViewEvent state: state as any (mockData.ts line 123) in genViewEvents()

## 8. Forms and Actions

| Screen | Form/Action | Backend mapping | Status |
|---|---|---|---|
| GhostBatches | TC response textarea | POST /v1/cases/{id}/respond | Not wired |
| GhostBatches | Add to watchlist button | No backend endpoint | BACKEND_GAP |
| GhostBatches | Request inspection button | No backend endpoint | BACKEND_GAP |
| GhostBatches | Request TC explanation button | No backend endpoint | BACKEND_GAP |
| GhostBatches | Escalate button | POST /v1/cases/{id}/events (to_status=ESCALATED) | Not wired |
| Flags/Cases | (unknown - need to read) | POST /v1/flags/{id}/resolve | Not wired |
| Settings | Threshold edit | No backend endpoint | BACKEND_GAP |

## 9. Navigation Structure (NavRail)

Overview, Centres, Flags & Cases, Camera Integrity, Ghost Batches, Edge Console, Settings, Audit Log, Accuracy & Limits

All routes are accessible, code-split with React.lazy().
