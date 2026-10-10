# PRAMAAN Reconciliation Matrix
Phase 0 / Phase 2 — awaiting your approval of the removal list before Phase 3 begins.

Classifications:
- MATCH: Frontend uses it correctly
- MISSING_IN_FRONTEND: Backend provides it; UI lacks it
- EXTRA_IN_FRONTEND: UI element with no backend support
- MISMATCH: Both sides have it but shapes/enums/naming differ
- BACKEND_ONLY_INTERNAL: Device-facing endpoints; no UI needed
- BACKEND_GAP: Product needs it; backend lacks it
- BACKEND_BUG_SUSPECT: Backend behavior inconsistent with schema

---

## Endpoints

| ID | Backend Ref | Frontend Ref | Class | Evidence | Action | Risk |
|---|---|---|---|---|---|---|
| EP-01 | GET /v1/healthz | None | MISSING_IN_FRONTEND | Backend: always 200. Frontend has no health indicator shown. | Add connection status indicator in TopBar. | LOW |
| EP-02 | GET /v1/readyz | None | MISSING_IN_FRONTEND | Backend: checks Postgres/Redis/S3. | Add to system health display in Settings or TopBar. | LOW |
| EP-03 | GET /v1/centres | Centres page uses MOCK_CENTRES | MISMATCH | Backend returns state_code/scheme_code; frontend expects state/scheme. Backend lacks lat/lng/status/open_flags. | Fix field names; add summary stats to backend response (BG-09). | HIGH |
| EP-04 | GET /v1/centres/{id} | CentreDetailPage uses MOCK_CENTRES | MISMATCH | Backend returns zones[]; frontend uses mock camera data instead. | Wire real endpoint; replace mock. | HIGH |
| EP-05 | GET /v1/centres/{id}/risk | Not called | MISSING_IN_FRONTEND | Risk endpoint exists but frontend never calls it. | Wire to CentreDetail and Overview risk score cards. | MEDIUM |
| EP-06 | GET /v1/sessions | CentreDetailPage / sessions table (mock) | MISMATCH | Field names differ; NO_DATA vs NO-DATA. | Fix types and wire API call. | HIGH |
| EP-07 | GET /v1/sessions/{id} | Not called | MISSING_IN_FRONTEND | Backend provides full session detail. | Wire to session drill-down. | MEDIUM |
| EP-08 | GET /v1/flags | FlagsCases page uses MOCK_FLAGS | MISMATCH | flag_type enum mismatch, flag_status mismatch, missing centre_name/sla_deadline/tc_response. | Fix types; wire real call; derive missing fields. | HIGH |
| EP-09 | GET /v1/flags/{id} | Not called | MISSING_IN_FRONTEND | Full flag detail + input snapshot available. | Wire to flag detail / explainability view. | MEDIUM |
| EP-10 | POST /v1/flags/{id}/resolve | Not wired | MISSING_IN_FRONTEND | Resolve endpoint exists. Frontend has no resolve button connected. | Add resolve action to flag detail. | MEDIUM |
| EP-11 | GET /v1/cases | FlagsCases page (partial mock) | MISMATCH | Frontend shows combined flags+cases but calls are mock only. | Separate flags list and cases list; wire both. | HIGH |
| EP-12 | POST /v1/cases | Not wired | MISSING_IN_FRONTEND | Create case endpoint exists. | Add "Open case" action to flag detail. | MEDIUM |
| EP-13 | GET /v1/cases/{id} | Not called | MISSING_IN_FRONTEND | Full case detail with timeline and TC responses. | Wire to case detail panel. | MEDIUM |
| EP-14 | POST /v1/cases/{id}/events | Not wired | MISSING_IN_FRONTEND | Status transition endpoint exists. | Add status transition buttons in case detail. | MEDIUM |
| EP-15 | POST /v1/cases/{id}/respond | GhostBatches TC response textarea (not wired) | MISSING_IN_FRONTEND | TC response textarea exists but submits to nothing. | Wire textarea to real endpoint. | MEDIUM |
| EP-16 | POST /v1/admin/reevaluate | Settings page (not wired) | MISSING_IN_FRONTEND | Admin reevaluate exists; no UI trigger. | Add "Trigger Re-evaluation" button for admin roles. | LOW |
| EP-17 | WS /v1/events/ws | Not connected | MISSING_IN_FRONTEND | No WebSocket connection anywhere in frontend. | Add ws hook + cache invalidation on events. | HIGH |
| EP-18 | GET /v1/events/stream | Not connected | MISSING_IN_FRONTEND | SSE fallback available. | Connect as fallback to WS. | LOW |
| EP-19 | POST /v1/device/enroll | Not applicable | BACKEND_ONLY_INTERNAL | Edge device only. | No UI needed. | — |
| EP-20 | POST /v1/device/heartbeat | Not applicable | BACKEND_ONLY_INTERNAL | Edge device only. | No UI needed. | — |
| EP-21 | POST /v1/ingest/observations | Not applicable | BACKEND_ONLY_INTERNAL | Edge device only. | No UI needed. | — |
| EP-22 | POST /v1/evidence/presign | Not applicable | BACKEND_ONLY_INTERNAL | Edge device only. | No UI needed. | — |
| EP-23 | POST /v1/evidence/complete | Not applicable | BACKEND_ONLY_INTERNAL | Edge device only. | No UI needed. | — |

---

## Enums / Status Values

| ID | Backend Value | Frontend Value | Class | Action | Risk |
|---|---|---|---|---|---|
| EN-01 | NO_DATA (attendance_status) | NO-DATA (SessionStatus) | MISMATCH | Fix frontend type to use NO_DATA | LOW |
| EN-02 | PENDING (attendance_status) | PENDING (SessionStatus) | MATCH | Keep | — |
| EN-03 | UNCERTAIN (SessionStatus frontend) | Does not exist in backend | EXTRA_IN_FRONTEND | Remove UNCERTAIN from SessionStatus type | LOW |
| EN-04 | EVIDENCE_COMPROMISED (SessionStatus frontend) | Does not exist in backend | EXTRA_IN_FRONTEND | Remove EVIDENCE_COMPROMISED from SessionStatus; map to flag-derived state if needed | MEDIUM |
| EN-05 | ATTENDANCE_RED (flag_type) | OCCUPANCY (FlagType) | MISMATCH | Fix FlagType enum: rename OCCUPANCY to ATTENDANCE_RED | HIGH |
| EN-06 | ATTENDANCE_AMBER_REPEAT (flag_type) | Does not exist in frontend | MISSING_IN_FRONTEND | Add ATTENDANCE_AMBER_REPEAT to FlagType | MEDIUM |
| EN-07 | ITEM_ABSENT (flag_type) | ITEM_ABSENT (FlagType) | MATCH | Keep | — |
| EN-08 | GHOST_BATCH (flag_type) | GHOST_BATCH (FlagType) | MATCH | Keep | — |
| EN-09 | DEVICE_OFFLINE (flag_type) | Does not exist | MISSING_IN_FRONTEND | Add DEVICE_OFFLINE to FlagType | LOW |
| EN-10 | INTEGRITY_CHAIN_BREAK (flag_type) | CAMERA_SWAP (FlagType) | MISMATCH | Fix: rename CAMERA_SWAP to INTEGRITY_CHAIN_BREAK | MEDIUM |
| EN-11 | EVIDENCE_DUPLICATE (flag_type) | DUPLICATE_EVIDENCE (FlagType) | MISMATCH | Fix: rename DUPLICATE_EVIDENCE to EVIDENCE_DUPLICATE | LOW |
| EN-12 | FEED_HEALTH (FlagType frontend) | Does not exist in backend | EXTRA_IN_FRONTEND | Remove FEED_HEALTH from FlagType (backend has no such flag_type) | LOW |
| EN-13 | OPEN (flag_status) | OPEN (FlagStatus) | MATCH | Keep | — |
| EN-14 | UNDER_REVIEW (flag_status) | UNDER_REVIEW (FlagStatus) | MATCH | Keep | — |
| EN-15 | CLOSED_CONFIRMED (flag_status) | Does not exist in frontend | MISSING_IN_FRONTEND | Add CLOSED_CONFIRMED to FlagStatus | MEDIUM |
| EN-16 | CLOSED_DISMISSED (flag_status) | Does not exist in frontend | MISSING_IN_FRONTEND | Add CLOSED_DISMISSED to FlagStatus | MEDIUM |
| EN-17 | TC_RESPONDED (FlagStatus frontend) | Does not exist in backend flags | EXTRA_IN_FRONTEND | Remove TC_RESPONDED from FlagStatus (it's a Case status only) | MEDIUM |
| EN-18 | CLOSED (FlagStatus frontend) | Does not exist | EXTRA_IN_FRONTEND | Remove CLOSED; replace with CLOSED_CONFIRMED/CLOSED_DISMISSED | MEDIUM |
| EN-19 | NORMAL (ghost_state) | CLEAR (GhostStatus) | MISMATCH | Fix frontend: rename CLEAR to NORMAL | LOW |
| EN-20 | WATCH (ghost_state) | WATCH (GhostStatus) | MATCH | Keep | — |
| EN-21 | SUSPECTED_GHOST (ghost_state) | SUSPECTED_GHOST (GhostStatus) | MATCH | Keep | — |
| EN-22 | ESCALATED (ghost_state) | ESCALATED (GhostStatus) | MATCH | Keep | — |
| EN-23 | RESOLVED (ghost_state) | Does not exist | MISSING_IN_FRONTEND | Add RESOLVED to GhostStatus | LOW |
| EN-24 | STABLE (camera_integrity_state) | SAME_VIEW (CameraViewState) | MISMATCH | Fix: rename SAME_VIEW to STABLE | MEDIUM |
| EN-25 | DRIFT_SUSPECTED (camera_integrity_state) | VIEW_DRIFTED (CameraViewState) | MISMATCH | Fix: rename VIEW_DRIFTED to DRIFT_SUSPECTED | MEDIUM |
| EN-26 | SWAP_SUSPECTED (camera_integrity_state) | SUSPECTED_SWAP (CameraViewState) | MISMATCH | Fix: rename SUSPECTED_SWAP to SWAP_SUSPECTED | MEDIUM |
| EN-27 | SWAP_CONFIRMED (camera_integrity_state) | SWAP_CONFIRMED (CameraViewState) | MATCH | Keep | — |
| EN-28 | MOVED_CONFIRMED (camera_integrity_state) | Does not exist | MISSING_IN_FRONTEND | Add MOVED_CONFIRMED to CameraViewState | LOW |
| EN-29 | REBASELINED (camera_integrity_state) | REBASELINE_PENDING (CameraViewState) | MISMATCH | Fix: rename and rethink semantics (REBASELINED != REBASELINE_PENDING) | MEDIUM |
| EN-30 | RESOLVED (camera_integrity_state) | Does not exist | MISSING_IN_FRONTEND | Add RESOLVED to CameraViewState | LOW |
| EN-31 | VIEW_MISMATCH (CameraViewState frontend) | Does not exist in backend | EXTRA_IN_FRONTEND | Remove VIEW_MISMATCH (backend uses DRIFT_SUSPECTED progression to SWAP_SUSPECTED) | MEDIUM |
| EN-32 | UNCERTAIN (CameraViewState frontend) | Does not exist in backend | EXTRA_IN_FRONTEND | Remove UNCERTAIN from CameraViewState | LOW |

---

## Fields / Data Shape

| ID | Backend Field | Frontend Field | Class | Action | Risk |
|---|---|---|---|---|---|
| FD-01 | centre.state_code | centre.state | MISMATCH | Fix frontend type to use state_code | LOW |
| FD-02 | centre.scheme_code | centre.scheme | MISMATCH | Fix frontend type to use scheme_code | LOW |
| FD-03 | centre.lat/lng | N/A | BACKEND_GAP | Backend model has no geo coords; frontend needs for map | MEDIUM |
| FD-04 | centre.last_heartbeat | N/A | BACKEND_GAP | No heartbeat field at centre level; derive from devices | MEDIUM |
| FD-05 | centre.open_flags | N/A | BACKEND_GAP | Not returned; requires aggregation query | MEDIUM |
| FD-06 | centre.status (session rollup) | centre.status | BACKEND_GAP | Not returned; requires aggregation | HIGH |
| FD-07 | session.attendance_status | session.status | MISMATCH | Rename in frontend type | LOW |
| FD-08 | session.attendance_ratio | session.ratio | MISMATCH | Rename in frontend type | LOW |
| FD-09 | session.observed_p90 | N/A | BACKEND_GAP | Not stored in Session model directly | MEDIUM |
| FD-10 | session.rule_fired | N/A | BACKEND_GAP | Not in Session model; would need to join Flag | LOW |
| FD-11 | flag.flag_type | flag.type | MISMATCH | Rename in frontend type | LOW |
| FD-12 | flag.rule_name | flag.rule_fired | MISMATCH | Rename in frontend type | LOW |
| FD-13 | flag.centre_name | N/A | BACKEND_GAP | Backend never returns centre_name in flag response | MEDIUM |
| FD-14 | flag.sla_deadline | N/A | BACKEND_GAP | Backend has no SLA logic or deadline field | MEDIUM |
| FD-15 | flag.tc_response | N/A | BACKEND_GAP | TC responses are on Cases, not Flags | MEDIUM |
| FD-16 | flag.evidence_link | N/A | BACKEND_GAP | Backend FlagInputSnapshot has evidence_links (S3 keys) but no presigned GET URL returned | MEDIUM |
| FD-17 | ghost.valid_sessions | ghost.eligible_days | MISMATCH | Different semantics: eligible_days (days) vs valid_sessions (sessions) | MEDIUM |
| FD-18 | ghost.state | ghost.status | MISMATCH | Rename and fix enum mapping | LOW |
| FD-19 | ghost.explanation (JSONB) | ghost.indicators (i1-i6) | MISMATCH | Backend has persistence/magnitude/consistency/evidence_quality; frontend has i1-i6. Redesign ghost detail. | HIGH |
| FD-20 | ghost.per_day_detail (JSONB list) | ClaimedVsObservedPoint[] | MISMATCH | Backend per_day_detail contains date/claimed/o_hat/ratio/status/evidence_quality; frontend has different shape. Map carefully. | HIGH |
| FD-21 | device.status (ACTIVE) | device.status (ONLINE) | MISMATCH | Fix: ACTIVE -> ONLINE does not exist; keep backend enum | LOW |
| FD-22 | device.bytes_sent_today | N/A | BACKEND_GAP | Not in Device model | LOW |
| FD-23 | audit.resource_type | audit.entity_type | MISMATCH | Rename in frontend type | LOW |
| FD-24 | audit.occurred_at | audit.ts | MISMATCH | Rename in frontend type | LOW |
| FD-25 | audit.detail (JSONB) | audit.note (string) | MISMATCH | detail is JSONB; note is a plain string | LOW |

---

## Screens

| ID | Screen | Class | Notes | Action |
|---|---|---|---|---|
| SC-01 | Overview | MISMATCH | Uses MOCK_CENTRES and MOCK_FLAGS entirely; hardcoded TREND_DATA and metric estimates | Wire real APIs; remove mocks; replace hardcoded metrics with BACKEND_GAP markers |
| SC-02 | Centres | MISMATCH | Uses MOCK_CENTRES; map requires lat/lng (BACKEND_GAP) | Wire GET /v1/centres; show list view; defer map until BG-09 resolved |
| SC-03 | CentreDetail | MISMATCH | Uses mocks; should show sessions, flags, risk | Wire GET /v1/centres/{id}, /sessions, /flags, /centres/{id}/risk |
| SC-04 | FlagsCases | MISMATCH | Uses MOCK_FLAGS; wrong enum values; no case list | Wire GET /v1/flags and GET /v1/cases; fix enums |
| SC-05 | CameraIntegrity | BACKEND_GAP | Entire page depends on camera APIs that do not exist | Defer until BG-01 resolved |
| SC-06 | GhostBatches | BACKEND_GAP | Entire page depends on ghost batch API that does not exist; ghost score breakdown uses wrong indicator model | Defer until BG-02 resolved; redesign indicator display |
| SC-07 | EdgeConsole | BACKEND_GAP | Depends on device list API that does not exist | Defer until BG-06 resolved |
| SC-08 | Settings (Thresholds) | BACKEND_GAP | Depends on threshold API that does not exist | Defer until BG-03 resolved |
| SC-09 | AuditLog | BACKEND_GAP | Depends on audit log API that does not exist | Defer until BG-04 resolved |
| SC-10 | AccuracyLimits | MATCH | Static informational page; no API calls needed | Keep as-is |

---

## Removal Candidates (EXTRA_IN_FRONTEND)
**Awaiting your approval before removing any of these.**

| ID | Item | File | Reason |
|---|---|---|---|
| RM-01 | FlagType.OCCUPANCY | types.ts | Backend uses ATTENDANCE_RED |
| RM-02 | FlagType.FEED_HEALTH | types.ts | No such flag_type in backend |
| RM-03 | FlagType.CAMERA_SWAP | types.ts | Backend uses INTEGRITY_CHAIN_BREAK |
| RM-04 | FlagType.DUPLICATE_EVIDENCE | types.ts | Backend uses EVIDENCE_DUPLICATE (rename, not delete) |
| RM-05 | FlagStatus.TC_RESPONDED | types.ts | Not a flag status in backend (it is a case status) |
| RM-06 | FlagStatus.CLOSED | types.ts | Backend uses CLOSED_CONFIRMED/CLOSED_DISMISSED |
| RM-07 | SessionStatus.UNCERTAIN | types.ts | Not in backend attendance_status |
| RM-08 | SessionStatus.EVIDENCE_COMPROMISED | types.ts | Not in backend attendance_status |
| RM-09 | CameraViewState.VIEW_MISMATCH | types.ts | Not in backend camera_integrity_state |
| RM-10 | CameraViewState.UNCERTAIN | types.ts | Not in backend |
| RM-11 | CameraViewState.SAME_VIEW | types.ts | Rename to STABLE |
| RM-12 | CameraViewState.VIEW_DRIFTED | types.ts | Rename to DRIFT_SUSPECTED |
| RM-13 | CameraViewState.SUSPECTED_SWAP | types.ts | Rename to SWAP_SUSPECTED |
| RM-14 | CameraViewState.REBASELINE_PENDING | types.ts | Rename/rethink vs REBASELINED |
| RM-15 | GhostStatus.CLEAR | types.ts | Rename to NORMAL |
| RM-16 | GhostIndicators (i1-i6 structure) | types.ts | Backend uses persistence/magnitude/consistency/evidence_quality/cusum_score |
| RM-17 | MOCK_GHOST_DATA export | mockData.ts | Never imported; dead export |
| RM-18 | All MOCK_* usage in pages | all pages | Replace with real API calls after Phase 3 |
| RM-19 | Hardcoded TREND_DATA | Overview.tsx L137-140 | No backend endpoint for trend data |
| RM-20 | Hardcoded "~4 min" latency | Overview.tsx L312 | No backend endpoint |
| RM-21 | Hardcoded "~99.97%" bandwidth | Overview.tsx L319 | No backend endpoint |

---

## Summary Counts

| Class | Count |
|---|---|
| MATCH | 8 |
| MISSING_IN_FRONTEND | 14 |
| EXTRA_IN_FRONTEND | 21 |
| MISMATCH | 27 |
| BACKEND_ONLY_INTERNAL | 5 |
| BACKEND_GAP | 14 |
| BACKEND_BUG_SUSPECT | 5 |
