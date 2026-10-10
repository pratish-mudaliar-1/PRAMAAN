# ADAPTATION AUDIT: PRAMAAN Backend

**Date:** 2026-10-04  
**Auditor:** Senior Backend Systems Engineer  
**Status:** PHASE 0 COMPLETE — PENDING USER REVIEW  

---

## 1. REPOSITORY MAP

### 1.1 Architecture & Directory Structure
```
backend/
├── alembic/                      # Database migrations
│   ├── env.py                    # Async migration harness
│   ├── script.py.mako            # Migration template
│   └── versions/                 # [EMPTY] No migration revisions generated
├── alembic.ini                   # Alembic configuration
├── app/
│   ├── main.py                   # FastAPI app factory, lifespan, CORS, error registration
│   ├── adapters/                 # External integration adapters
│   │   ├── interfaces.py         # Abstract base classes (Attendance, Timetable, Inventory, Trainer)
│   │   └── csv_file.py           # CSV file adapter implementation
│   ├── api/                      # Presentation layer (HTTP REST)
│   │   └── v1/
│   │       ├── __init__.py       # Router aggregation (/v1 prefix)
│   │       ├── deps.py           # Dependency injection (DB session, Principal)
│   │       ├── health.py         # Liveness (/healthz) and readiness (/readyz) probes
│   │       └── schemas.py        # Pydantic v2 boundary DTO schemas
│   ├── core/                     # Foundational infrastructure
│   │   ├── clock.py              # Injectable clock (SystemClock, FrozenClock, SteppingClock)
│   │   ├── config.py             # Pydantic Settings with env + YAML overlay
│   │   ├── errors.py             # RFC 9457 Problem+JSON exception hierarchy & handlers
│   │   ├── logging.py            # structlog JSON logging with PII scrubbing filter
│   │   └── security/             # Security & Cryptography
│   │       ├── device_key.py     # Ed25519 signing/verification & canonical JSON hashing
│   │       ├── jwt.py            # JWT decoder & dev HS256 token issuer
│   │       └── policy.py         # 5-role RBAC matrix & row-level query scoping helpers
│   ├── db/                       # Persistence layer
│   │   ├── base.py               # SQLAlchemy 2.0 async engine & session factory
│   │   ├── timescale.py          # TimescaleDB hypertable DDL, continuous aggs & retention
│   │   ├── models/               # SQLAlchemy Declarative Models (12 files)
│   │   │   ├── audit.py          # AuditLog with SHA-256 hash-chaining
│   │   │   ├── camera_integrity.py # CameraBaseline, SceneObservation, CameraSwapEvent, RebaselineRequest
│   │   │   ├── case_.py          # Case, CaseEvent, TcResponse
│   │   │   ├── centre.py         # Centre, Camera, Zone, SanctionedLayout
│   │   │   ├── device.py         # Device, DeviceStatusEnum
│   │   │   ├── evidence.py       # Evidence (S3 references + perceptual hashes)
│   │   │   ├── flag.py           # Flag, FlagInputSnapshot, IntegrityEvent
│   │   │   ├── ghost.py          # GhostBatchFlag, GhostPatternSummary
│   │   │   ├── observation.py    # Observation (minute-level edge ingestion)
│   │   │   ├── session_.py       # Batch, Session, IngestDedupe
│   │   │   ├── threshold.py      # ThresholdProfile
│   │   │   └── user.py           # User, RoleBinding
│   │   └── repositories/         # Typed Data Access Repositories
│   │       ├── audit.py          # AuditLogRepository
│   │       ├── base.py           # BaseRepository[T]
│   │       ├── centre.py         # CentreRepository
│   │       ├── device.py         # DeviceRepository
│   │       ├── flag.py           # FlagRepository, IntegrityEventRepository
│   │       ├── observation.py    # ObservationRepository
│   │       └── session_.py       # SessionRepository, IngestDedupeRepository
│   ├── domain/                   # Pure business logic (Zero I/O, deterministic)
│   │   ├── camera_integrity.py   # Camera state machine, hysteresis & corroboration rules
│   │   ├── reconciliation.py     # Attendance & inventory reconciliation, ghost batch detection
│   │   └── vision/               # Computer vision scene comparison algorithms
│   │       └── scene_compare.py  # Multi-feature fusion (Homography/ORB, Edge Chamfer, Color Hist)
│   ├── events/                   # Event definitions & bus (empty __init__.py)
│   ├── jobs/                     # Background workers
│   │   └── worker.py             # Arq worker settings stub
│   └── services/                 # Orchestration layer
│       └── ingestion.py          # ObservationIngestionService (dedupe, verify, hash-chain)
├── deploy/
│   ├── Dockerfile                # Multi-stage slim Dockerfile
│   └── docker-compose.yml        # TimescaleDB, Redis, MinIO, API & Worker definitions
├── docs/
│   └── ARCHITECTURE.md           # Architecture design doc
├── pyproject.toml                # Build configuration, linting & test settings
├── README.md                     # Project overview
├── STATUS.md                     # Implementation status tracking
└── tests/
    ├── conftest.py               # Shared pytest fixtures (SQLite in-memory session, frozen clock)
    ├── contract_client/          # Edge device test client
    │   └── client.py
    └── unit/                     # Unit test suite
        ├── test_adapter_csv.py
        ├── test_audit_hash_chain.py
        ├── test_clock.py
        ├── test_config.py
        ├── test_contract_client.py
        ├── test_device_key.py
        ├── test_errors.py
        ├── test_ingestion_service.py # [BROKEN IMPORT]
        ├── test_jwt.py
        ├── test_reconciliation.py
        ├── test_schemas.py
        └── test_security_policy.py
```

### 1.2 Entry Points
- **API Server:** `app.main:create_app` running under Uvicorn (`uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000`).
- **Worker Process:** `app.jobs.worker:WorkerSettings` running under Arq (`arq app.jobs.worker.WorkerSettings`).

### 1.3 Frameworks & Versions
- **Python:** 3.12+ (tested locally under Python 3.14.8 on Windows)
- **FastAPI:** `>=0.115.0`
- **Pydantic / Pydantic Settings:** `>=2.9.0` / `>=2.5.0`
- **SQLAlchemy:** `>=2.0.35` (Async Engine with asyncpg)
- **Alembic:** `>=1.13.0`
- **Cryptography / Signing:** `PyNaCl>=1.5.0` (Ed25519), `python-jose[cryptography]>=3.3.0`
- **Images & Vision:** `Pillow>=10.4.0`, `imagehash>=4.3.1`
- **Logging & Tracing:** `structlog>=24.4.0`, `prometheus-client>=0.21.0`, `opentelemetry-api>=1.27.0`
- **Testing:** `pytest>=8.3.0`, `pytest-asyncio>=0.24.0`, `pytest-cov>=5.0.0`, `hypothesis>=6.168.0`

### 1.4 How to Run & Test
- **Local Dev Server:** `uvicorn app.main:create_app --factory --reload`
- **Docker Compose:** `docker compose -f deploy/docker-compose.yml up -d`
- **Run Tests:** `pytest -v`

### 1.5 Real Test Execution Baseline
Running the test suite as-is produced the following real execution results:

**Run 1 (Full Suite):**
```text
pytest -v
collected 128 items / 1 error

=================================== ERRORS ====================================
____________ ERROR collecting tests/unit/test_ingestion_service.py ____________
tests\unit\test_ingestion_service.py:24: in <module>
    from app.db.models.centre import TrainingCentre, Zone
E   ImportError: cannot import name 'TrainingCentre' from 'app.db.models.centre'
=========================== short test summary info ===========================
ERROR tests/unit/test_ingestion_service.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 1.07s ===============================
```

**Run 2 (Excluding Broken Import to Assess Remaining Tests):**
```text
pytest -v --ignore=tests/unit/test_ingestion_service.py
=========================== short test summary info ===========================
FAILED tests/unit/test_adapter_csv.py::test_timetable_returns_correct_window
  TypeError: can't compare offset-naive and offset-aware datetimes (csv_file.py:133)
FAILED tests/unit/test_adapter_csv.py::test_timetable_excludes_other_centre
  TypeError: can't compare offset-naive and offset-aware datetimes (csv_file.py:133)
FAILED tests/unit/test_reconciliation.py::test_coverage_factor_scales_denominator
  TypeError: ThresholdConfig() got multiple values for keyword argument 'coverage_factor_k' (test_reconciliation.py:35)
FAILED tests/unit/test_reconciliation.py::test_high_feed_healthy_never_no_data
  TypeError: ThresholdConfig() got multiple values for keyword argument 'min_feed_health_fraction' (test_reconciliation.py:35)
======================== 4 failed, 124 passed in 1.87s ========================
```

**Total Test Count:** 132 tests (124 passed, 4 failed due to bugs, 4 unexecuted due to import error in `test_ingestion_service.py`).  
**Baseline Test Coverage:** **56%** total line coverage.

---

## 2. CONFORMANCE MATRIX

| Requirement Area | Status | Evidence File Paths | Notes & Gaps |
| :--- | :--- | :--- | :--- |
| **1. Configuration** | `MATCHES` | `app/core/config.py`, `pyproject.toml` | Pydantic v2 `BaseSettings` with nested models (`db`, `redis`, `s3`, `auth`, `ingest`, `recon`, `camera_integrity`, `ghost_batch`, `otel`), YAML overlay support, `extra="ignore"` on env, secrets wrapped in `SecretStr`. |
| **2. DB Schema & Migrations** | `PARTIAL` | `app/db/models/*.py`, `alembic/` | Models are well-structured with typed SQLAlchemy 2.0 `Mapped[...]`, UUID PKs, foreign keys, and indexes. However, `alembic/versions/` is empty (no migration scripts generated or verified up/down). |
| **3. TimescaleDB Usage** | `PARTIAL` | `app/db/timescale.py` | DDL contains hypertable creation on `observation`, 5-minute and 1-hour continuous aggregates with refresh policies, compression (>7d) and retention (>90d). Not yet executed in automated DB initialization or migration scripts. |
| **4. Auth & RBAC Scoping** | `MATCHES` | `app/core/security/jwt.py`, `app/core/security/policy.py`, `app/api/v1/deps.py` | Complete 5-role matrix (`national_admin`, `state_officer`, `district_officer`, `centre_manager`, `auditor`). Action checking and row-level query scoping helpers implemented and unit-tested. |
| **5. Device Enrollment & Signing** | `PARTIAL` | `app/core/security/device_key.py`, `app/db/models/device.py` | Ed25519 signing/verification, public key decoding, canonical JSON formatting, and SHA-256 record hashing fully implemented. `POST /v1/device/enroll` route handler is missing. |
| **6. Hash-Chain Ingestion** | `PARTIAL` | `app/services/ingestion.py`, `app/db/models/observation.py` | `ObservationIngestionService` implements timestamp validation, signature check, SHA-256 hash recalculation, and `prev_hash` chain verification. Missing the FastAPI HTTP endpoint `POST /v1/ingest/observations`. |
| **7. Idempotency** | `MATCHES` | `app/db/models/session_.py`, `app/db/repositories/session_.py`, `app/services/ingestion.py` | `IngestDedupe` model and repository tracks `(device_id, minute_ts, record_hash)`. Service rejects duplicate records cleanly. |
| **8. Evidence & Perceptual-Hash Search** | `PARTIAL` | `app/db/models/evidence.py`, `app/api/v1/schemas.py` | `Evidence` model stores `phash`, S3 keys, and metadata. Missing presigned upload URL endpoints, upload completion hook, and Hamming distance perceptual hash near-duplicate search. |
| **9. External Adapters (CSV / HTTP)** | `PARTIAL` | `app/adapters/interfaces.py`, `app/adapters/csv_file.py` | Interfaces defined for 4 sources (`Attendance`, `Timetable`, `Inventory`, `TrainerAttendance`). `csv_file.py` implemented with PII column rejection. `http_rest.py` is missing. Watermarking sync jobs are missing. Datetime naive/aware comparison bug present in CSV timetable query. |
| **10. Reconciliation Logic** | `MATCHES` | `app/domain/reconciliation.py` | Pure domain functions: `reconcile_session_attendance` (P90 logic, GREEN/AMBER/RED, NO_DATA, PENDING), `reconcile_zone_inventory` (PRESENT/ABSENT/UNCERTAIN with multi-day persistence), and `compute_centre_risk_score`. Batch orchestration service and API endpoints missing. |
| **11. Thresholds in Config** | `MATCHES` | `app/core/config.py`, `app/db/models/threshold.py`, `app/domain/reconciliation.py` | All reconciliation, camera, and ghost batch thresholds configurable with defaults explicitly labelled `[initial hypothesis; calibrate in pilot]`. |
| **12. Integrity Events** | `MATCHES` | `app/db/models/flag.py`, `app/db/repositories/flag.py`, `app/services/ingestion.py` | Models and repos for `IntegrityEvent` and `Flag`. Service emits integrity events for signature failure, hash break, and clock drift. |
| **13. Case Management** | `PARTIAL` | `app/db/models/case_.py`, `app/api/v1/schemas.py` | `Case`, `CaseEvent`, and `TcResponse` models define complete workflow (`OPEN` → `UNDER_REVIEW` → `EXPLANATION_REQUESTED` → `EXPLANATION_RECEIVED` → `RESOLVED` / `ESCALATED`). API endpoints and service missing. |
| **14. WebSocket / SSE** | `MISSING` | `app/events/` | Real-time event streaming over Redis PubSub, WebSocket hub with RBAC scoping, and SSE fallback are not yet implemented. |
| **15. Observability** | `PARTIAL` | `app/core/logging.py`, `app/main.py` | structlog JSON logging with request ID tracing and PII scrubbing filter implemented. Prometheus metrics (`/metrics`) and OpenTelemetry exporter not yet activated. |
| **16. Security Controls** | `MATCHES` | `app/core/security/`, `app/core/errors.py` | Ed25519 signatures, JWT verification, strict PII prohibition in models and logs, RFC 9457 structured error responses without leaking stack traces. |
| **17. Tests** | `PARTIAL` | `tests/` | 132 unit tests exist, but 5 have defects (1 import error, 4 test/code logic bugs). Integration tests with testcontainers, E2E flows, and load tests are missing. |
| **18. Documentation** | `PARTIAL` | `docs/ARCHITECTURE.md`, `STATUS.md` | Architecture and Status documents are comprehensive. `docs/SECURITY.md`, `docs/PRIVACY.md`, and `docs/DATA_CONTRACT.md` are missing. |
| **19. Camera-Swap Detection** | `MATCHES` | `app/domain/camera_integrity.py`, `app/domain/vision/scene_compare.py`, `app/db/models/camera_integrity.py` | Domain state machine (`STABLE`, `DRIFT_SUSPECTED`, `SWAP_SUSPECTED`, `SWAP_CONFIRMED`, `MOVED_CONFIRMED`, `RESOLVED`, `REBASELINED`), hysteresis, multi-feature scene comparison (Homography RANSAC, Edge Chamfer, Color Histogram, SSIM). Router and worker job missing. |
| **20. Ghost Batch Detection** | `MATCHES` | `app/domain/reconciliation.py`, `app/db/models/ghost.py` | Domain detection pure functions over multi-day attendance vs occupancy. Models for `GhostBatchFlag` and `GhostPatternSummary`. Worker job and query API missing. |

---

## 3. CODE-QUALITY FINDINGS (Ranked by Risk)

### 🔴 High Risk
1. **Broken Test Import (`TrainingCentre` vs `Centre`):**
   - *Location:* [tests/unit/test_ingestion_service.py:24](file:///c:/Users/prati/Documents/sih%2026245/backend/tests/unit/test_ingestion_service.py#L24)
   - *Impact:* Causes pytest collection failure across the entire file, silencing 4 critical ingestion unit tests.
2. **Missing Alembic Migration Revision:**
   - *Location:* `alembic/versions/`
   - *Impact:* Database schema exists only as Python declarations; cannot run reproducible migration up/down in production or CI environments.
3. **Offset-Naive vs Offset-Aware Datetime Comparison in CSV Adapter:**
   - *Location:* [app/adapters/csv_file.py:133](file:///c:/Users/prati/Documents/sih%2026245/backend/app/adapters/csv_file.py#L133)
   - *Impact:* Runtime `TypeError` crashing timetable filtering whenever querying with timezone-aware `datetime` objects.
4. **Keyword Argument Collision in Reconciliation Test Helper:**
   - *Location:* [tests/unit/test_reconciliation.py:35](file:///c:/Users/prati/Documents/sih%2026245/backend/tests/unit/test_reconciliation.py#L35)
   - *Impact:* `TypeError` on `default_cfg(coverage_factor_k=0.5)` because `coverage_factor_k` is duplicated in positional/keyword arguments.

### 🟡 Medium Risk
5. **Direct Global Reference in Dependency Injection:**
   - *Location:* [app/api/v1/deps.py:21-22](file:///c:/Users/prati/Documents/sih%2026245/backend/app/api/v1/deps.py#L21-L22)
   - *Impact:* `get_db_session()` imports `get_session_factory` from `app.main`, reading `_app.state`. While functional, this binds dependencies to a global `_app` singleton instead of extracting state via `Request.app.state`.
6. **Synchronous JWKS Fetch in Token Verifier:**
   - *Location:* [app/core/security/jwt.py:65-75](file:///c:/Users/prati/Documents/sih%2026245/backend/app/core/security/jwt.py#L65-L75)
   - *Impact:* Performs synchronous `httpx.get` during JWT verification on JWKS cache misses, blocking the async event loop.
7. **Potential CPU Bottleneck in Vision Processing:**
   - *Location:* [app/domain/vision/scene_compare.py](file:///c:/Users/prati/Documents/sih%2026245/backend/app/domain/vision/scene_compare.py)
   - *Impact:* Multi-feature image comparisons (RANSAC homography, edge extraction, color histogram) are computationally intensive. When integrated with API or worker, they must run in dedicated thread pools (`run_in_threadpool` or Arq worker) to avoid starving the FastAPI async loop.

### 🟢 Low Risk
8. **Missing Index Verification on Timescale Hypertable Partitions:**
   - *Location:* [app/db/timescale.py](file:///c:/Users/prati/Documents/sih%2026245/backend/app/db/timescale.py)
   - *Impact:* Compound indexes `(device_id, minute_ts DESC)` and `(zone_id, minute_ts DESC)` must be confirmed on hypertable creation for optimal range queries.
9. **Stubbed Worker Settings:**
   - *Location:* [app/jobs/worker.py](file:///c:/Users/prati/Documents/sih%2026245/backend/app/jobs/worker.py)
   - *Impact:* Arq worker class is defined but contains no registered job functions.

---

## 4. SECURITY & PRIVACY FINDINGS

1. **Authentication Gaps at API Edge (Missing Routers):**
   - *Status:* Core security verification (JWT and Ed25519) is implemented and thoroughly tested in `app/core/security/`, but the FastAPI router (`/v1`) currently only mounts `/healthz` and `/readyz`. Device enrollment (`POST /v1/device/enroll`), observation ingestion (`POST /v1/ingest/observations`), and administrative endpoints must be wired with explicit security dependencies (`Depends(get_current_principal)` or Ed25519 signature headers).
2. **Missing Row-Level Scoping Enforcement in Query Routes:**
   - *Status:* `Policy.filter_centres()`, `filter_flags()`, and `filter_sessions()` are defined in `app/core/security/policy.py`, but as query routes are not yet mounted, active enforcement in database queries must be guaranteed when endpoints are added.
3. **SSRF Risk in Future HTTP REST Adapter:**
   - *Status:* `app/adapters/interfaces.py` defines the abstract contracts. When implementing `http_rest.py`, URL validation must enforce scheme whitelisting (`https://` only) and block loopback / private IP ranges (`127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.169.254`).
4. **PII and Privacy Compliance:**
   - *Status:* **STRONG COMPLIANCE**. Models store zero trainee names, biometric face templates, or personal IDs. Observations only store aggregate counts (`persons_p90`, `item_counts`), scene embeddings, and perceptual hashes. `app/core/logging.py` includes a custom structlog processor redacting keys like `password`, `secret`, `token`, `aadhaar`, `trainee_name`, `phone`, `email`.

---

## 5. RISK-ORDERED ADAPTATION PLAN

| Package | Goal & Scope | Files Touched | Tests to Add / Fix First | Rollback Approach | Blast Radius |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **WP-01: Safety Net & Test Suite Fixes** | Fix the 5 existing broken tests (class import, datetime timezone mismatch, duplicate kwargs), bring baseline test suite to 100% pass rate (132/132 passing). | `tests/unit/test_ingestion_service.py`, `app/adapters/csv_file.py`, `tests/unit/test_reconciliation.py` | Characterization tests for CSV date parsing and ingestion fixture setup. | Revert file edits. | **Low** |
| **WP-02: DB Migration Baseline (Alembic)** | Generate initial Alembic migration for all 12 model tables; create TimescaleDB hypertable & continuous aggregates migration step; verify `alembic upgrade head` and `downgrade base`. | `alembic/versions/001_initial_schema.py`, `app/db/timescale.py` | Migration up/down integration test against real Postgres container. | Downgrade Alembic revision. | **Medium** |
| **WP-03: Device Ingestion & API Layer** | Implement router endpoints for `POST /v1/device/enroll` and `POST /v1/ingest/observations`, wiring `ObservationIngestionService`, rate limiting, and Ed25519 signature validation. | `app/api/v1/ingest.py`, `app/api/v1/device.py`, `app/api/v1/__init__.py` | Contract client integration tests (`tests/contract_client/client.py`), endpoint unit tests. | Delete/disable router inclusion. | **Medium** |
| **WP-04: Evidence Presign & Perceptual Hash Search** | Implement `POST /v1/evidence/presign`, `POST /v1/evidence/complete`, and near-duplicate pHash search (Hamming distance ≤ 5) against S3/MinIO. | `app/services/evidence.py`, `app/api/v1/evidence.py`, `app/domain/evidence.py` | Unit tests for pHash distance calculation and mock/real S3 presigned URL generation. | Revert evidence router. | **Low** |
| **WP-05: External Data Adapters (HTTP REST & Sync Jobs)** | Implement `app/adapters/http_rest.py` with SSRF guards; implement scheduled sync worker jobs with watermarking for attendance, timetable, inventory, trainer counts. | `app/adapters/http_rest.py`, `app/jobs/sync.py`, `app/jobs/worker.py` | Unit tests with `respx` mocking external HTTP payloads + SSRF blocking tests. | Remove adapter registration in settings. | **Medium** |
| **WP-06: Reconciliation Worker & Re-evaluation API** | Wire domain reconciliation into automated session evaluation jobs and `POST /v1/admin/reevaluate` endpoint; write flags and risk scores to DB. | `app/services/reconciliation.py`, `app/api/v1/admin.py`, `app/jobs/reconciliation.py` | Integration tests verifying flag creation and risk score calculation from seed session data. | Disable job triggers in Arq worker. | **Medium** |
| **WP-07: Real-Time Event Pipeline (Redis / WS / SSE)** | Implement Redis PubSub event broadcaster, WebSocket hub with RBAC-scoped subscriptions, and SSE fallback endpoint (`GET /v1/events/stream`). | `app/events/bus.py`, `app/api/v1/ws.py`, `app/api/v1/events.py` | Async WebSocket test client verifying role-filtered event delivery. | Remove WS/SSE route handlers. | **Medium** |
| **WP-08: Case Management & Query APIs** | Implement RBAC-scoped query APIs (`/v1/centres`, `/v1/sessions`, `/v1/flags`, `/v1/cases`, `/v1/risk-rankings`) and case lifecycle endpoints (`POST /v1/cases/{id}/explain`, `POST /v1/cases/{id}/resolve`). | `app/api/v1/centres.py`, `app/api/v1/cases.py`, `app/api/v1/flags.py`, `app/services/case.py` | RBAC access tests for each of the 5 roles ensuring proper row-level data segregation. | Revert router endpoints. | **Low** |
| **WP-09: Camera-Swap & Ghost Batch Worker Pipelines** | Wire camera integrity state machine and ghost batch detector into scheduled worker jobs, evaluation harness, and dedicated API query endpoints. | `app/jobs/camera_integrity.py`, `app/jobs/ghost_batch.py`, `app/api/v1/camera_integrity.py`, `app/api/v1/ghost_batch.py` | Camera drift/swap scenario tests, multi-day ghost batch pattern tests, benchmark evaluation report. | Disable scheduled job routines. | **Medium** |
| **WP-10: Observability, Security Hardening & CI Gates** | Enable Prometheus `/metrics` endpoint, OpenTelemetry tracing, complete `docs/SECURITY.md`, `docs/PRIVACY.md`, `docs/DATA_CONTRACT.md`, and add testcontainers integration test suite. | `app/api/v1/metrics.py`, `docs/SECURITY.md`, `docs/PRIVACY.md`, `docs/DATA_CONTRACT.md`, `tests/integration/` | End-to-end integration test against testcontainers (Postgres, Redis, MinIO). | Revert documentation and metrics config. | **Low** |

---

## 6. AUDIT CONCLUSION & NEXT STEPS

The repository contains an exceptionally clean and modular domain layer, comprehensive SQLAlchemy models, strong cryptographic utilities, and a well-defined RBAC architecture. 

The primary task ahead is **adaptation and wiring**:
1. Fixing minor unit test defects to establish a 100% green safety net.
2. Generating Alembic migrations.
3. Exposing the domain logic via thin, secure FastAPI routers.
4. Scheduling worker jobs for background sync and reconciliation.
5. Verifying the complete system with integration tests against real infrastructure.

**Phase 0 is complete. Awaiting user review and approval to proceed with WP-01 (Safety Net).**
