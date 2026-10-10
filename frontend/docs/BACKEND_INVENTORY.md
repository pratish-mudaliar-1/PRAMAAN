# PRAMAAN Backend Inventory
Phase 0 - read-only. Backend is the source of truth.

## 1. Auth & Security

### Auth Flow
- No /auth/login or /auth/token endpoint in this service. JWT verified but not issued here.
- REST: Authorization: Bearer <token> header.
- WebSocket (/v1/events/ws): ?token=<jwt> query param.

### JWT Claims Expected
| Claim | Type | Notes |
|---|---|---|
| sub | string | Opaque user ID |
| roles | string[] | See roles below |
| state_code | string or null | Required for state_officer |
| centre_ids | string[] | Required for inspector / training_centre |

### Roles
| Role | Read | Write | Admin | Threshold Mgmt |
|---|---|---|---|---|
| national_admin | all | all | yes | yes |
| state_officer | state-scoped | state-scoped | no | yes |
| inspector | centre-scoped | centre-scoped | no | no |
| training_centre | own centre | no | no | no |
| auditor | all | no | no | no |

## 2. Endpoints

### Health
| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | /v1/healthz | None | Liveness; always 200 |
| GET | /v1/readyz | None | Checks Postgres, Redis, S3; 200 or 503 |

### Centres (UI-facing)
| Method | Path | Auth | Roles | Notes |
|---|---|---|---|---|
| GET | /v1/centres | Bearer | All read | Offset pagination |
| GET | /v1/centres/{centre_id} | Bearer | All read | Includes zones |
| GET | /v1/centres/{centre_id}/risk | Bearer | All read | Risk breakdown |

Query params for list: state_code, limit (1-200 default 50), offset (default 0)

Centre item fields returned: id, name, code, state_code, district, scheme_code, registration_no, is_active
NOT returned by backend (frontend expects): lat, lng, last_heartbeat, open_flags, suspected_swaps, suspected_ghosts, status (session rollup), state, scheme

Risk response: { centre_id, risk_score: 0.72, risk_tier: HIGH|MEDIUM|LOW, explanation, red_sessions, amber_sessions, ghost_batch_flags, total_sessions }

### Sessions (UI-facing)
| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | /v1/sessions | Bearer | Offset pagination |
| GET | /v1/sessions/{session_id} | Bearer | Single session |

Query params: centre_id, batch_id, status, limit, offset

Session fields: id, batch_id, zone_id, scheduled_start, scheduled_end, claimed_count, trainer_count, attendance_status, attendance_ratio
Single session adds: last_evaluated_at

MISMATCH: Backend uses attendance_status (value NO_DATA with underscore); frontend uses status field and NO-DATA with hyphen.
MISMATCH: Backend does NOT return observed_p90, ratio, rule_fired.

### Flags (UI-facing)
| Method | Path | Auth | Roles | Notes |
|---|---|---|---|---|
| GET | /v1/flags | Bearer | All read | Offset pagination |
| GET | /v1/flags/{flag_id} | Bearer | All read | Includes snapshot |
| POST | /v1/flags/{flag_id}/resolve | Bearer | Write | Resolve/dismiss |

Query params for list: centre_id, severity, flag_type, status, limit, offset
Flag item fields: id, centre_id, session_id, zone_id, flag_type, severity, status, rule_name, description, created_at
Flag detail adds: rule_version, updated_at, snapshot (inputs, thresholds, model_version)
Resolve body: { resolution_reason: string, status: CLOSED_CONFIRMED|CLOSED_DISMISSED }

Backend flag_type values: ATTENDANCE_RED, ATTENDANCE_AMBER_REPEAT, GHOST_BATCH, ITEM_ABSENT, DEVICE_OFFLINE, INTEGRITY_CHAIN_BREAK, EVIDENCE_DUPLICATE
Frontend FlagType values (MISMATCH): OCCUPANCY, ITEM_ABSENT, FEED_HEALTH, DUPLICATE_EVIDENCE, CAMERA_SWAP, GHOST_BATCH

Backend flag status: OPEN, UNDER_REVIEW, CLOSED_CONFIRMED, CLOSED_DISMISSED
Frontend FlagStatus (MISMATCH): OPEN, TC_RESPONDED, UNDER_REVIEW, CLOSED

Backend does NOT return: centre_name, sla_deadline, tc_response, evidence_link

### Cases (UI-facing)
| Method | Path | Auth | Roles | Notes |
|---|---|---|---|---|
| GET | /v1/cases | Bearer | All read | Offset pagination |
| POST | /v1/cases | Bearer | Write | Create case |
| GET | /v1/cases/{case_id} | Bearer | All read | Full case + events + TC responses |
| POST | /v1/cases/{case_id}/events | Bearer | Write | Status transition |
| POST | /v1/cases/{case_id}/respond | Bearer | training_centre | Submit TC explanation |

Query params: centre_id, status, priority, limit, offset
Case item fields: id, case_number, centre_id, title, status, priority, assigned_to, sla_breached, created_at
Case detail adds: description, assigned_at, events[], tc_responses[]
Case statuses: OPEN, TC_RESPONDED, CLOSED

### Events / Real-time (UI-facing)
| Method | Path | Auth | Notes |
|---|---|---|---|
| WS | /v1/events/ws?token=<jwt> | JWT query | Role+tenant-scoped |
| GET | /v1/events/stream | Bearer | SSE fallback |

Event envelope: { event_id, event_type, timestamp, centre_id, state_code, payload: {...} }
Event types (structurally defined, not yet wired): PING, FLAG_RAISED, FLAG_RESOLVED, CASE_CREATED, CASE_STATUS_CHANGED

BUG SUSPECT: No service code calls bus.publish() - the bus exists but no events are actually published.

### Admin (UI-facing, restricted)
| Method | Path | Auth | Roles | Notes |
|---|---|---|---|---|
| POST | /v1/admin/reevaluate | Bearer | national_admin, state_officer | Trigger re-evaluation |

### Device / Edge (Device-facing - NO UI needed)
POST /v1/device/enroll, POST /v1/device/heartbeat, POST /v1/ingest/observations, POST /v1/evidence/presign, POST /v1/evidence/complete

## 3. Exact Enum Values

| Domain | Values |
|---|---|
| attendance_status | GREEN, AMBER, RED, NO_DATA, PENDING |
| flag_type | ATTENDANCE_RED, ATTENDANCE_AMBER_REPEAT, GHOST_BATCH, ITEM_ABSENT, DEVICE_OFFLINE, INTEGRITY_CHAIN_BREAK, EVIDENCE_DUPLICATE |
| flag_status | OPEN, UNDER_REVIEW, CLOSED_CONFIRMED, CLOSED_DISMISSED |
| device_status | PENDING, ACTIVE, OFFLINE, SUSPENDED, REVOKED |
| camera_integrity_state | STABLE, DRIFT_SUSPECTED, SWAP_SUSPECTED, SWAP_CONFIRMED, MOVED_CONFIRMED, RESOLVED, REBASELINED |
| ghost_assessment_state | NORMAL, WATCH, SUSPECTED_GHOST, ESCALATED, RESOLVED |
| per_day_status | GHOST, HEALTHY, NO_DATA, UNTRUSTED, PENDING |
| rebaseline_status | pending, inspector_approved, state_officer_approved, approved, rejected |
| case_status | OPEN, TC_RESPONDED, CLOSED |
| case_priority | HIGH, MEDIUM, LOW |
| risk_tier | HIGH, MEDIUM, LOW |
| integrity_event_type | CHAIN_BREAK, REPLAY, CLOCK_SKEW, EVIDENCE_DUPLICATE, DEVICE_OFFLINE, CAMERA_MOVED |
| severity | HIGH, MEDIUM, LOW |

## 4. Pagination

All list endpoints use offset pagination: ?limit=N&offset=N
Response: { "items": [...], "limit": N, "offset": N }
No cursor pagination (CursorPage schema exists but unused).

## 5. WebSocket / SSE

- WS: /v1/events/ws?token=<jwt> - single multiplexed stream, PING every 30s
- SSE: /v1/events/stream - Bearer auth, text/event-stream
- No topic subscription, no resume/replay, in-memory bus only

## 6. Models With No API Endpoints (Backend Gaps)

| Model | Table | Status |
|---|---|---|
| CameraReference | camera_reference | No endpoint |
| SceneObservation | scene_observation | No endpoint |
| CameraIntegrityState | camera_integrity_state | No endpoint |
| CameraStateEvent | camera_state_event | No endpoint |
| RebaselineRequest | rebaseline_request | No endpoint |
| CameraMaintenanceWindow | camera_maintenance_window | No endpoint |
| GhostAssessment | ghost_assessment | No endpoint |
| GhostStateEvent | ghost_state_event | No endpoint |
| ThresholdProfile | threshold_profile | No endpoint |
| AuditLog | audit_log | No endpoint |
| IntegrityEvent | integrity_event | No endpoint |
| Device (list/manage) | device | No UI list endpoint |

## 7. Feature Status

| Feature | Backend Status |
|---|---|
| Centre list + detail + risk | Implemented |
| Session list + detail | Implemented |
| Flag list + detail + resolve | Implemented |
| Case CRUD + workflow + TC respond | Implemented |
| Admin reevaluate | Implemented |
| Real-time WS/SSE | Structural only - bus not wired |
| Camera integrity queries | MISSING - no API endpoints |
| Ghost batch queries | MISSING - no API endpoints |
| Threshold profile read/write | MISSING - no API endpoints |
| Audit log query | MISSING - no API endpoint |
| Integrity events query | MISSING - no API endpoint |
| Device management (UI) | MISSING - only edge-facing |
| Evidence read / presigned view | MISSING - only upload endpoints |

## 8. Error Shapes
{ "detail": "string message" } with HTTP 400/401/403/404/409/422/503

## 9. OpenAPI
- Spec: GET /v1/openapi.json
- Docs: GET /v1/docs (dev only)
