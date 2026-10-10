# PRAMAAN Backend Gaps & Bugs Report
Phase 0 — items requiring your decision before Phase 3 begins.

---

## BACKEND_GAP Items

These are capabilities the frontend was designed for (or clearly needs), but the backend does not yet expose any API endpoints for them.

### BG-01: Camera Integrity — No Query API
The backend has a complete data model (CameraReference, SceneObservation, CameraIntegrityState, CameraStateEvent, RebaselineRequest, CameraMaintenanceWindow) and a service (app/services/camera_integrity.py) but ZERO API endpoints.

The frontend has a full CameraIntegrity page with: camera list, similarity timeline, baseline versions, state transitions, rebaseline request workflow.

Proposed backend additions needed:
- GET /v1/cameras — list cameras per centre
- GET /v1/cameras/{camera_id} — current state + latest reference
- GET /v1/cameras/{camera_id}/observations — similarity timeline (paginated)
- GET /v1/cameras/{camera_id}/references — baseline history
- POST /v1/cameras/{camera_id}/rebaseline — request new baseline
- GET /v1/cameras/{camera_id}/maintenance-windows — list windows
- POST /v1/cameras/{camera_id}/maintenance-windows — create window

Risk: HIGH — entire camera integrity feature unavailable without this.

### BG-02: Ghost Batch Assessments — No Query API
The backend has GhostAssessment and GhostStateEvent models and a service (app/services/ghost_batch.py) but ZERO API endpoints.

The frontend has a full GhostBatches page showing: batch list, ghost score, per-day detail, state history, indicator breakdown.

Proposed additions:
- GET /v1/ghost-assessments — list assessments (filter: centre_id, state, limit, offset)
- GET /v1/ghost-assessments/{id} — full assessment with per_day_detail and explanation
- GET /v1/batches — list batches per centre (needed for context)

Risk: HIGH — entire ghost batch feature unavailable.

### BG-03: Threshold Profile — No Read/Write API
The backend ThresholdProfile model is complete but has no API endpoints.

The frontend has a Settings page for viewing/editing thresholds. Currently using mock flat key/value; backend has structured columns (t_green, t_amber, repeat_n, etc.) plus JSONB extra.

Proposed additions:
- GET /v1/thresholds — list profiles (filter: scheme_code, state_code)
- GET /v1/thresholds/effective — get effective profile for caller's scope
- POST /v1/thresholds — create new version (national_admin/state_officer)
- POST /v1/thresholds/{id}/approve — approve a version

Risk: MEDIUM — settings page non-functional without this.

### BG-04: Audit Log — No Query API
The AuditLog model is complete but has no API endpoint.

The frontend has a full AuditLog page.

Proposed addition:
- GET /v1/audit-log — paginated, filtered by actor, action, resource_type, date range

Risk: MEDIUM — audit log page non-functional.

### BG-05: Integrity Events — No Query API
The IntegrityEvent model (CHAIN_BREAK, REPLAY, CLOCK_SKEW, etc.) has no query endpoint.

These events are relevant to display alongside flags in the frontend.

Proposed addition:
- GET /v1/integrity-events — list (filter: centre_id, device_id, event_type, limit, offset)

Risk: MEDIUM — integrity event screen would be non-functional.

### BG-06: Device Management — No UI List API
The frontend has an Edge Console page showing device status (ONLINE/OFFLINE/DEGRADED). The backend Device model exists but only has edge-facing endpoints (enroll, heartbeat). No API for the dashboard to query device list and status.

Proposed addition:
- GET /v1/devices — list devices (filter: centre_id, status, limit, offset)

Risk: LOW-MEDIUM — edge console page non-functional.

### BG-07: Evidence Read / Presigned View URL
The backend only has upload presign endpoints (device-facing). The frontend needs to display redacted keyframe evidence (images) from S3 with expiring presigned GET URLs.

Proposed addition:
- GET /v1/evidence/{evidence_id}/view — return short-lived presigned GET URL for the S3 object
- GET /v1/flags/{flag_id}/evidence — list evidence attached to a flag

Risk: MEDIUM — evidence viewer non-functional.

### BG-08: No Login / Token Endpoint
The frontend has no login screen and no auth flow at all. The backend consumes JWTs but does not issue them. An external identity provider is assumed.

Decision needed: Will you add a mock/dev login endpoint, or integrate an external IdP (Keycloak, etc.)? Until this is resolved, all authenticated endpoints cannot be called from the frontend.

Risk: CRITICAL — without auth, no authenticated API endpoint can be called.

### BG-09: Centre Missing Key Fields
The backend /v1/centres response does not include:
- lat/lng (no geolocation columns in Centre model)
- last_heartbeat (device-level, not centre-level)
- open_flags count (requires query join to Flag table)
- suspected_swaps / suspected_ghosts counts (require query joins)
- status (session-level rollup)

These are all derivable server-side but not currently exposed. The frontend Overview and Centres map view requires them.

Proposed: enrich /v1/centres response, or add a /v1/centres/summary endpoint with rollup stats.

Risk: HIGH — overview KPIs and map view show nothing without this.

---

## BACKEND_BUG_SUSPECT Items

### BS-01: Event Bus — Publish Never Called
The EventBus class is implemented (app/events/bus.py) and the WebSocket/SSE endpoints subscribe to it correctly. However, a search of ALL service and route code finds no calls to bus.publish(). 

Evidence: grep for bus.publish() across the entire backend returns zero results.

Result: Real-time events are structurally complete but functionally dead. Clients connect but never receive FLAG_RAISED, CASE_CREATED, etc.

Recommendation: Add bus.publish() calls in reconciliation.py (after flag creation) and cases.py (after case creation/transition).

Risk: HIGH — real-time feature is broken.

### BS-02: Flag Resolution — No Audit Trail
POST /v1/flags/{flag_id}/resolve updates flag.status but does not:
1. Write an AuditLog entry
2. Publish a FLAG_RESOLVED event to the bus

This means resolutions are not traceable in the audit log.

Risk: MEDIUM — compliance gap.

### BS-03: Case Creation — No Audit Trail
POST /v1/cases creates a case and a CaseEvent but does not write to AuditLog.

Risk: MEDIUM — compliance gap.

### BS-04: Session attendance_status Enum — Inconsistency
The Session model's attendance_status column is a plain String (no Enum type enforced at DB level). Values are set by the reconciliation service. The frontend uses NO-DATA (hyphen) but the backend uses NO_DATA (underscore). The frontend also has UNCERTAIN and EVIDENCE_COMPROMISED which have no backend equivalent.

Risk: LOW — type mismatch causes silent display errors in frontend.

### BS-05: GhostAssessment state = NORMAL vs frontend CLEAR
The backend GhostAssessment.state default is NORMAL. The frontend GhostStatus uses CLEAR. These are semantically equivalent but the names differ, which will cause missed status rendering.

Risk: LOW — cosmetic/functional mismatch.

---

## Correction to BS-01 (Updated After Code Verification)

bus.publish() IS called in production code:
- app/services/ghost_batch.py line 141: event_type="FLAG_CREATED"
- app/services/camera_integrity.py line 206: event_type="INTEGRITY_ALERT"

However, two new issues found:

### BS-01-A: Event Type Names Inconsistent
Services publish "FLAG_CREATED" and "INTEGRITY_ALERT" but the events.py docstring implies "FLAG_RAISED", "FLAG_RESOLVED", "CASE_CREATED", "CASE_STATUS_CHANGED". The frontend would need to handle exactly the event_types that are actually published. Current published types:
- FLAG_CREATED (from ghost_batch service when ghost detected)
- INTEGRITY_ALERT (from camera_integrity service on state transition)
- PING (from ws endpoint heartbeat)

NOT published (despite being logically expected):
- FLAG_CREATED from reconciliation service (needs verification)
- CASE_CREATED when a case is opened
- CASE_STATUS_CHANGED when status transitions

Risk: MEDIUM - frontend must subscribe to the ACTUAL event types, not the inferred ones.

### BS-01-B: Services Not Called From Any Route
Both ghost_batch.py and camera_integrity.py services are called from the background worker job (app/jobs/), not from any HTTP route. They run asynchronously. This is correct architecture - but it means the bus.publish calls in these services are only reachable when the worker is running.
