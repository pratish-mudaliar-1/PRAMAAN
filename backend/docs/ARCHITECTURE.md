# PRAMAAN Backend Architecture

## System Overview

PRAMAAN (Platform for Real-time Attendance Monitoring and Analysis at National training centres)
is the backend service for SIH PS-26245 (MSDE). It receives signed minute-level aggregate
observations from edge video-analytics devices at government skill-development training centres,
reconciles them with attendance claims and sanctioned infrastructure, and serves real-time
flags and cases to monitoring officials.

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          PRAMAAN System Boundary                           │
│                                                                            │
│  Edge Devices         Ingestion API         Domain Engine                  │
│  ┌──────────┐         ┌──────────────┐      ┌──────────────────────┐       │
│  │ Camera + │──Sign──▶│POST /ingest/ │─────▶│ Reconciliation       │       │
│  │ Analytics│         │ observations │      │ Rules Engine         │       │
│  └──────────┘         └──────────────┘      │ Risk Scorer          │       │
│                              │               └──────────┬───────────┘       │
│  External Systems            │                          │                   │
│  ┌──────────────┐            │               ┌──────────▼───────────┐       │
│  │ Attendance   │──Adapter──▶│ Sync Jobs      │ Flag/Case Manager    │       │
│  │ Timetable    │            │               └──────────────────────┘       │
│  │ Inventory    │            │                          │                   │
│  └──────────────┘            │               ┌──────────▼───────────┐       │
│                              │               │ Event Bus (Redis      │       │
│                              ▼               │ Streams)             │       │
│                    ┌──────────────────┐      └──────────┬───────────┘       │
│                    │ PostgreSQL 16 +  │                 │                   │
│                    │ TimescaleDB      │      ┌──────────▼───────────┐       │
│                    └──────────────────┘      │ WebSocket/SSE Hub    │       │
│                                             └──────────┬───────────┘       │
│                    ┌──────────────────┐                │                   │
│                    │ MinIO/S3         │      ┌──────────▼───────────┐       │
│                    │ (Evidence frames)│      │ Monitoring Dashboard  │       │
│                    └──────────────────┘      │ (External client)    │       │
│                                             └──────────────────────┘       │
└────────────────────────────────────────────────────────────────────────────┘
```

## Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| API framework | FastAPI 0.115+ async | Native async; Pydantic v2 integration; auto OpenAPI |
| Data validation | Pydantic v2 strict | `extra="forbid"` on all ingestion schemas |
| Database | PostgreSQL 16 + TimescaleDB | Time-series native; continuous aggregates; compression |
| ORM | SQLAlchemy 2.0 async + asyncpg | Native async; best PG throughput |
| Migrations | Alembic | Async-compatible env.py |
| Cache / Streams | Redis 7 | Streams for event fan-out; pub/sub for rate limiting |
| Task queue | Arq | Async-native; Redis-backed; minimal ops overhead |
| Object storage | S3-compatible (MinIO dev) | Presigned URLs; server-side checks |
| Auth | OIDC JWT + Ed25519 device keys | Industry standard; PyNaCl for device key operations |
| Realtime | WebSocket primary + SSE fallback | Both through Redis Streams for persistence |
| Observability | structlog + Prometheus + OpenTelemetry | Structured logs; metrics; distributed tracing |

## Key Design Decisions

### 1. Privacy by Design
- No faces, no names, no biometrics, no Aadhaar numbers stored anywhere
- Attendance = aggregate count integers only
- Evidence frames are pre-processed by edge devices to remove faces before upload
- Perceptual hash (dHash) is stored, not the biometric

### 2. Observation Hash Chain
Each observation record from a device includes:
- `record_hash = SHA-256(canonical_json(payload))`
- `prev_hash = record_hash of the last accepted record from this device`
- `signature = Ed25519Sign(device_private_key, canonical_json_bytes)`

This creates a tamper-evident chain. Chain breaks, gaps, and replays are stored as
`integrity_event` records and may trigger cases. They are never silently dropped.

### 3. Honest State Vocabulary
- **Attendance**: `GREEN | AMBER | RED | NO_DATA | PENDING`
  - `NO_DATA` = feed was unhealthy for > threshold fraction of session window
  - `PENDING` = attendance claim not yet received; auto-re-evaluates when it arrives
- **Infrastructure items**: `PRESENT | ABSENT | UNCERTAIN`
  - `UNCERTAIN` = occluded, low visibility, or feed outage during observation windows
  - `ABSENT` = not seen across ≥ N unoccluded windows on ≥ 2 distinct days

### 4. Flags are Leads, Not Penalties
Every flag:
- Is a lead for human review
- Stores the complete `flag_input_snapshot` (inputs, thresholds, model_version, evidence_links)
- Can be reproduced from stored data without access to live observations
- Uses `flag_key` for idempotent upsert — reprocessing never duplicates flags

### 5. Thresholds in DB, Not Code
`ThresholdProfile` table with scoped fallback:
1. scheme + state (most specific)
2. scheme only
3. national default

All defaults labelled "initial hypothesis, calibrate in pilot".

### 6. RBAC Single Policy Layer
All access decisions go through `app/core/security/policy.py`.
Routers never do access checks. Five roles:
- `national_admin` — full access
- `state_officer` — own state only
- `inspector` — assigned centres only
- `training_centre` — own centre, read-only
- `auditor` — read-only, all centres

### 7. TimescaleDB for Observations
`observation` table is a hypertable on `minute_ts`:
- Chunk interval: 1 day
- Compression: after 7 days (segmented by device+zone)
- Retention: configurable (default 365 days)
- Continuous aggregates: 5-minute and hourly
- `P90(persons_p90)` computed via Postgres `percentile_cont` on the native data

### 8. Near-Duplicate Evidence Detection
Two approaches implemented and benchmarked (Phase 2):
- **BK-tree in Redis** — fast O(log n) for hot path queries
- **Postgres bit-slice** — exact Hamming via `bit_count(phash_int # other_int)` on indexed column

### 9. Event Bus via Redis Streams
- Each domain event is XADD to a stream
- Consumers XREADGROUP with consumer groups
- WebSocket hub reads from streams and fans out to authenticated subscribers
- Missed events during disconnect are replayed via stream offset (resume token)

## Data Flow: Observation Ingestion

```
Edge Device
    │ POST /v1/ingest/observations (gzip, signed batch)
    ▼
Rate Limiter (per-device Redis token bucket)
    │
    ▼
Schema Validation (Pydantic strict, extra=forbid)
    │
    ▼
Device Authentication (lookup device by id, status=ACTIVE)
    │
    ▼  For each record:
Idempotency Check (device_id, record_hash) → already accepted? return cached result
    │
    ▼
Ed25519 Signature Verify (canonical JSON → PyNaCl verify)
    │
    ▼
Timestamp Plausibility (±5 min clock skew window)
    │
    ▼
Hash Chain Check (prev_hash == device.last_accepted_hash?)
    │ NO → store IntegrityEvent(CHAIN_BREAK), continue with chain_ok=False
    ▼
Write Observation to TimescaleDB hypertable
    │
    ▼
Update device.last_accepted_hash, last_seen_at
    │
    ▼
Record IngestDedupe row
    │
    ▼
Publish observation.accepted domain event → Redis Stream
    │
    ▼
Return per-record accept/reject with reasons

    (Async, from event consumer)
    ▼
Session Assignment (find active session for zone at minute_ts)
    │
    ▼
Trigger Reconciliation Evaluation (if session window complete)
    │
    ▼
Fan-out via WebSocket/SSE to subscribed clients
```

## Directory Structure

```
backend/
├── app/
│   ├── api/v1/          # FastAPI routers
│   ├── core/            # Config, logging, errors, clock, security
│   ├── domain/          # Pure reconciliation/rules functions (no I/O)
│   ├── adapters/        # External system adapters (csv, http_rest)
│   ├── db/              # Models, repositories, timescale helpers
│   ├── events/          # Redis Streams publisher/consumer
│   ├── jobs/            # Arq background jobs
│   └── services/        # Orchestration layer
├── alembic/             # Migrations
├── tests/               # Unit, integration, e2e, property, load
├── docs/                # Architecture, contracts, security, privacy
├── deploy/              # Docker Compose, Helm skeleton
└── scripts/             # Backup, restore, import
```
