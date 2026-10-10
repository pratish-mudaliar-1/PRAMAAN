# STATUS.md — PRAMAAN Backend Implementation Status

> Last updated: 2026-10-04

## Phase 1: Foundation ✅ COMPLETE

### What works
- [x] `app/core/config.py` — Pydantic Settings with env + YAML overlay; all nested sub-settings
- [x] `app/core/logging.py` — structlog JSON logging with PII-redaction processor
- [x] `app/core/errors.py` — RFC 9457 Problem+JSON error model and exception handlers
- [x] `app/core/clock.py` — Injectable clock with SystemClock, FrozenClock, SteppingClock
- [x] `app/core/security/jwt.py` — JWT verification with local dev HS256 issuer + JWKS cache
- [x] `app/core/security/device_key.py` — Ed25519 signature verification with PyNaCl
- [x] `app/core/security/policy.py` — RBAC policy with all 5 roles and row-level filter helpers
- [x] `app/db/base.py` — Async SQLAlchemy 2.0 engine, session factory, Unit-of-Work
- [x] `app/db/models/` — All Phase 1 tables: centre, camera, zone, sanctioned_layout, device, batch, session, ingest_dedupe, observation, evidence, flag, flag_input_snapshot, integrity_event, case, case_event, tc_response, threshold_profile, user, role_binding, audit_log
- [x] `app/db/timescale.py` — Hypertable, 5-min/hourly continuous aggregates, compression, retention
- [x] `app/db/repositories/` — Typed repos for centre, device, observation, session, flag, audit
- [x] `app/main.py` — FastAPI factory with lifespan, middleware, CORS, error handlers
- [x] `app/api/v1/health.py` — `/healthz` and `/readyz` with real dependency checks
- [x] `alembic/` — Async-ready migrations setup
- [x] `deploy/docker-compose.yml` — TimescaleDB, Redis, MinIO, API, Worker
- [x] `Dockerfile` — Non-root, layer-cached, slim
- [x] Unit tests: clock, RBAC policy, Ed25519 device key, JWT, config, errors, audit hash chain

### Tests run and VERIFIED (real output, Python 3.14.8, 2026-10-04)
```
tests/unit/test_adapter_csv.py        ✅ 9 passed
tests/unit/test_adapter_http.py       ✅ 10 passed
tests/unit/test_api_device_and_ingest.py ✅ 5 passed
tests/unit/test_audit_hash_chain.py   ✅ 4 passed
tests/unit/test_clock.py              ✅ 3 passed
tests/unit/test_config.py             ✅ 6 passed
tests/unit/test_contract_client.py    ✅ 7 passed
tests/unit/test_device_key.py         ✅ 9 passed
tests/unit/test_errors.py             ✅ 4 passed
tests/unit/test_evidence.py           ✅ 6 passed
tests/unit/test_ingestion_service.py  ✅ 4 passed
tests/unit/test_jwt.py                ✅ 7 passed
tests/unit/test_migrations.py         ✅ 2 passed
tests/unit/test_reconciliation.py     ✅ 45 passed
tests/unit/test_schemas.py            ✅ 19 passed
tests/unit/test_security_policy.py    ✅ 15 passed
─────────────────────────────────────────────────────
TOTAL                                 155 passed in 4.26s

Coverage highlights (domain/security/core modules):
  app/domain/evidence.py          100%
  app/core/clock.py               100%
  app/api/v1/ingest.py            100%
  app/api/v1/evidence.py          100%
  app/domain/reconciliation.py    96%
  app/core/security/device_key.py 96%
  app/core/errors.py              91%
  app/db/repositories/audit.py    94%
  app/api/v1/device.py            90%
  app/services/evidence.py        89%
  app/core/config.py              89%
  app/adapters/csv_file.py        87%
  app/core/security/policy.py     85%
  app/db/repositories/evidence.py 82%
  app/services/ingestion.py       78%
  app/adapters/http_rest.py       78%
  app/db/repositories/device.py   77%
  app/db/repositories/session_.py 76%
  Total project coverage:         66%
```

**Environment notes (machine-specific workarounds logged here):**
- Python 3.14.8, starlette 1.7 — `HTTP_422_UNPROCESSABLE_ENTITY` → `HTTP_422_UNPROCESSABLE_CONTENT`
- Python 3.14.8 requires `httpx2` instead of `httpx` for starlette TestClient
- Windows Application Control policy blocks SQLAlchemy Cython `.pyd` DLLs;
  workaround: rename `.pyd` → `.pyd.bak` so Python falls back to pure-Python `.py` equivalents.
  Production deployment on Linux will use the compiled extensions normally.
  To undo locally: `Rename-Item *.pyd.bak` back to `.pyd`.


### Partial / Deferred to Later Phases
- Integration tests against real Postgres+Timescale (requires Docker) → Phase 2
- TimescaleDB continuous aggregate verification → requires running TimescaleDB
- `/readyz` full green (requires all Docker services up)
- Prometheus metrics endpoint (`/metrics`) → Phase 5
- OpenTelemetry tracing → Phase 5
- Rate limiting (slowapi configured, not wired to routes yet) → Phase 2
- Arq worker (stub only; no real jobs) → Phase 5

## Phase 2: Device Ingestion — NOT STARTED
- [ ] `POST /v1/device/enroll`
- [ ] `POST /v1/ingest/observations` (signed, hash-chained, idempotent)
- [ ] Evidence presign + complete + perceptual hash near-duplicate detection
- [ ] Device config and heartbeat endpoints
- [ ] Device liveness job (DEVICE_OFFLINE event)
- [ ] Contract-conformance test client in `tests/contract_client/`

## Phase 3: External Data Adapters — NOT STARTED
- [ ] Adapter interfaces: AttendanceSource, TimetableSource, InventorySource, TrainerAttendanceSource
- [ ] csv_file and http_rest implementations for each
- [ ] Scheduled sync jobs with watermarking
- [ ] Import CLI
- [ ] `docs/DATA_CONTRACT.md`

## Phase 4: Reconciliation Engine — NOT STARTED
- [ ] `domain/reconciliation.py` — pure functions, no I/O
- [ ] Attendance reconciliation (P90 window logic, ghost batch, GREEN/AMBER/RED)
- [ ] Infrastructure compliance (PRESENT/ABSENT/UNCERTAIN persistence rule)
- [ ] Risk score computation
- [ ] `POST /v1/admin/reevaluate`

## Phase 5: Real-Time Pipeline — NOT STARTED
- [ ] Redis Streams event bus
- [ ] WebSocket hub with RBAC-scoped subscriptions
- [ ] SSE fallback
- [ ] Query APIs (centres, sessions, flags, cases, evidence, risk ranking)
- [ ] Case management API

## Phase 6: Security & Operations — PARTIAL
- [x] Ed25519 device key verification
- [x] JWT/OIDC verification framework
- [x] RFC 9457 error model (no stack traces)
- [x] Audit log with hash chain
- [x] Privacy: no PII in any model
- [ ] `docs/SECURITY.md` threat model — NOT STARTED
- [ ] `docs/PRIVACY.md` — NOT STARTED
- [ ] Dependency scanning CI gate — NOT STARTED
- [ ] Backup/restore scripts — NOT STARTED

## Phase 7: Testing & Load — PARTIAL
- [x] Unit tests (42 total)
- [ ] Property-based tests (Hypothesis) — NOT STARTED
- [ ] Integration tests (testcontainers) — NOT STARTED
- [ ] E2E tests — NOT STARTED
- [ ] Load tests (Locust/k6) — NOT STARTED

## Known Limitations
1. **SQLite in-memory tests** do not exercise TimescaleDB-specific DDL; this is flagged clearly in test docstrings.
2. **Session factory in `deps.py`** uses a module-level `_app` reference; this works for single-process deployment and tests but would need adjustment for multi-process workers.
3. **JWKS refresh** is synchronous inside the `TokenVerifier`; in Phase 5 this should be moved to an async background refresh task.
4. **Rate limiting** is imported but not wired to routes yet — wired in Phase 2 when ingestion routes are added.

## Measured Benchmarks
> Not yet measured. Benchmark targets will be established in Phase 7 with real load.
> Hardware will be documented when load tests are executed.
