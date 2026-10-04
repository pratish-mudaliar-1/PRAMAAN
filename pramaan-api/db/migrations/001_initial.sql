-- PRAMAAN Database Schema — Phase 1 (all tables defined)
-- PostgreSQL 16 · Phase 2 will wire engines to populate data

-- ─── Extensions ───────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- for text search

-- ─── Core tables ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS centre (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    state           TEXT NOT NULL,
    scheme          TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'PENDING',
    lat             DOUBLE PRECISION,
    lng             DOUBLE PRECISION,
    last_heartbeat  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS zone (
    id                  TEXT PRIMARY KEY,
    centre_id           TEXT NOT NULL REFERENCES centre(id) ON DELETE CASCADE,
    label               TEXT NOT NULL,
    polygon             JSONB,            -- [{x, y}] normalised 0-1
    coverage_factor_k   FLOAT NOT NULL DEFAULT 1.0,
    capacity            INT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS camera (
    id                      TEXT PRIMARY KEY,
    centre_id               TEXT NOT NULL REFERENCES centre(id) ON DELETE CASCADE,
    zone_id                 TEXT REFERENCES zone(id),
    label                   TEXT NOT NULL,
    model                   TEXT,
    mac                     TEXT UNIQUE,
    registered_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    current_baseline_ver    INT NOT NULL DEFAULT 0,
    view_state              TEXT NOT NULL DEFAULT 'UNCERTAIN'
);

CREATE TABLE IF NOT EXISTS sanctioned_layout (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    centre_id       TEXT NOT NULL REFERENCES centre(id) ON DELETE CASCADE,
    zone_id         TEXT REFERENCES zone(id),
    item_class      TEXT NOT NULL,
    sanctioned_count INT NOT NULL DEFAULT 1,
    critical        BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS batch (
    id              TEXT PRIMARY KEY,
    centre_id       TEXT NOT NULL REFERENCES centre(id) ON DELETE CASCADE,
    trade           TEXT NOT NULL,
    scheme          TEXT NOT NULL,
    start_date      DATE,
    end_date        DATE,
    ghost_status    TEXT NOT NULL DEFAULT 'CLEAR',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS session (
    id                  TEXT PRIMARY KEY,
    batch_id            TEXT NOT NULL REFERENCES batch(id) ON DELETE CASCADE,
    zone_id             TEXT REFERENCES zone(id),
    scheduled_start     TIMESTAMPTZ NOT NULL,
    scheduled_end       TIMESTAMPTZ NOT NULL,
    claimed_count       INT,
    trainer_count       INT,
    status              TEXT NOT NULL DEFAULT 'PENDING',
    observed_p90        FLOAT,
    ratio               FLOAT,
    rule_fired          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_session_batch ON session(batch_id);
CREATE INDEX IF NOT EXISTS idx_session_status ON session(status);
CREATE INDEX IF NOT EXISTS idx_session_time ON session(scheduled_start);

CREATE TABLE IF NOT EXISTS observation (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id       TEXT NOT NULL,
    zone_id         TEXT REFERENCES zone(id),
    ts              TIMESTAMPTZ NOT NULL,
    persons         INT NOT NULL DEFAULT 0,
    items           JSONB,
    feed_ok         BOOLEAN NOT NULL DEFAULT TRUE,
    model_version   TEXT,
    hash            TEXT,
    prev_hash       TEXT,
    signature       TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_observation_zone_ts ON observation(zone_id, ts);
CREATE INDEX IF NOT EXISTS idx_observation_device_ts ON observation(device_id, ts);

CREATE TABLE IF NOT EXISTS flag (
    id              TEXT PRIMARY KEY,
    type            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'OPEN',
    centre_id       TEXT REFERENCES centre(id),
    entity_id       TEXT,              -- session_id, batch_id, camera_id, etc.
    rule_fired      TEXT,
    evidence_link   TEXT,
    owner           TEXT,
    tc_response     TEXT,
    sla_deadline    TIMESTAMPTZ,
    severity        TEXT NOT NULL DEFAULT 'MEDIUM',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_flag_status ON flag(status);
CREATE INDEX IF NOT EXISTS idx_flag_centre ON flag(centre_id);
CREATE INDEX IF NOT EXISTS idx_flag_type ON flag(type);

CREATE TABLE IF NOT EXISTS audit_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type     TEXT NOT NULL,
    entity_id       TEXT NOT NULL,
    actor           TEXT NOT NULL,
    action          TEXT NOT NULL,
    old_val         JSONB,
    new_val         JSONB,
    note            TEXT,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts DESC);

-- ─── Camera Integrity tables (Feature A) ─────────────────────────────────────

CREATE TABLE IF NOT EXISTS camera_baseline (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id       TEXT NOT NULL REFERENCES camera(id) ON DELETE CASCADE,
    version         INT NOT NULL,
    captured_by     TEXT NOT NULL,
    captured_at     TIMESTAMPTZ NOT NULL,
    geo_lat         DOUBLE PRECISION,
    geo_lng         DOUBLE PRECISION,
    lighting_tag    TEXT NOT NULL DEFAULT 'DAY',  -- DAY | EVENING
    phash           TEXT,
    anchors         JSONB,   -- [{label, x, y, descriptor}]
    histogram       JSONB,
    status          TEXT NOT NULL DEFAULT 'ACTIVE',  -- ACTIVE | SUPERSEDED
    approved_by     TEXT,
    UNIQUE(camera_id, version)
);

CREATE TABLE IF NOT EXISTS camera_view_event (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id       TEXT NOT NULL REFERENCES camera(id) ON DELETE CASCADE,
    ts              TIMESTAMPTZ NOT NULL,
    similarity      FLOAT NOT NULL,
    anchors_found   INT NOT NULL DEFAULT 0,
    anchors_total   INT NOT NULL DEFAULT 0,
    baseline_ver    INT NOT NULL,
    state           TEXT NOT NULL,  -- SAME_VIEW | VIEW_DRIFTED | VIEW_MISMATCH | SUSPECTED_SWAP | SWAP_CONFIRMED | UNCERTAIN
    reason          JSONB
);
CREATE INDEX IF NOT EXISTS idx_view_event_camera_ts ON camera_view_event(camera_id, ts DESC);

CREATE TABLE IF NOT EXISTS camera_change_request (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id       TEXT NOT NULL REFERENCES camera(id),
    requested_by    TEXT NOT NULL,
    reason          TEXT,
    status          TEXT NOT NULL DEFAULT 'PENDING',  -- PENDING | APPROVED | REJECTED
    inspector_id    TEXT,
    approved_by     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ
);

-- ─── Ghost Batch tables (Feature B) ──────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ghost_evaluation (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    batch_id        TEXT NOT NULL REFERENCES batch(id) ON DELETE CASCADE,
    evaluated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    window_start    DATE NOT NULL,
    window_end      DATE NOT NULL,
    valid_sessions  INT NOT NULL DEFAULT 0,
    ghost_score     FLOAT NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'CLEAR',  -- CLEAR | WATCH | SUSPECTED_GHOST | ESCALATED
    indicators      JSONB,  -- {i1: float, i2: float, ...}
    excluded_sessions JSONB  -- [session_id, reason]
);
CREATE INDEX IF NOT EXISTS idx_ghost_eval_batch ON ghost_evaluation(batch_id, evaluated_at DESC);
CREATE INDEX IF NOT EXISTS idx_ghost_eval_status ON ghost_evaluation(status);

CREATE TABLE IF NOT EXISTS ghost_status_history (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    batch_id        TEXT NOT NULL REFERENCES batch(id) ON DELETE CASCADE,
    from_status     TEXT NOT NULL,
    to_status       TEXT NOT NULL,
    rule            TEXT,
    actor           TEXT NOT NULL,
    note            TEXT,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Config tables ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS threshold_config (
    key             TEXT PRIMARY KEY,
    value           FLOAT NOT NULL,
    label           TEXT NOT NULL,
    hypothesis_note TEXT,
    modified_by     TEXT NOT NULL DEFAULT 'system',
    modified_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS threshold_history (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key         TEXT NOT NULL REFERENCES threshold_config(key),
    old_value   FLOAT NOT NULL,
    new_value   FLOAT NOT NULL,
    actor       TEXT NOT NULL,
    ts          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Default thresholds (all hypothesis — calibrate on pilot) ─────────────────

INSERT INTO threshold_config (key, value, label, hypothesis_note) VALUES
('attendance.ratio_green', 0.80, 'GREEN threshold (ratio)', 'Sessions with observed ≥ 80% of claimed → GREEN.'),
('attendance.ratio_amber', 0.50, 'AMBER threshold (ratio)', 'Sessions below 50% (if persistent) → RED. 50–80% → AMBER.'),
('attendance.red_persistence_windows', 2, 'Persistence windows for RED', 'Must be below AMBER threshold in N consecutive windows before RED.'),
('camera.t_same', 0.75, 'SAME_VIEW similarity threshold', 'Similarity ≥ this → SAME_VIEW.'),
('camera.t_mismatch', 0.35, 'VIEW_MISMATCH similarity threshold', 'Similarity < this → VIEW_MISMATCH.'),
('camera.swap_persist_windows', 3, 'Windows to confirm SUSPECTED_SWAP', 'Mismatch must persist N × 5-min windows.'),
('camera.check_interval_minutes', 5, 'Check interval (minutes)', 'How often the scene similarity is computed.'),
('ghost.min_valid_sessions', 5, 'Min valid sessions for ghost verdict', 'Fewer → show insufficient evidence, never a verdict.'),
('ghost.min_evidence_days', 3, 'Min evidence days for ghost verdict', 'Evidence must span at least 3 distinct calendar days.'),
('ghost.window_sessions', 10, 'Rolling window (sessions)', 'Last N valid sessions considered for ghost evaluation.'),
('ghost.window_days', 14, 'Rolling window (days)', 'Last N calendar days considered.'),
('ghost.watch_score', 30, 'WATCH ghost score threshold', 'Score ≥ this → WATCH status.'),
('ghost.suspected_score', 60, 'SUSPECTED_GHOST score threshold', 'Score ≥ this → SUSPECTED_GHOST; human review needed.'),
('ghost.min_claim', 10, 'Min claimed count for ghost eval', 'Sessions with claim < this are excluded from ghost evaluation.'),
('ghost.i1_weight', 0.40, 'I1 weight (persistent shortfall)', 'Primary indicator weight.'),
('ghost.i2_weight', 0.20, 'I2 weight (near-zero occupancy)', ''),
('ghost.i3_weight', 0.15, 'I3 weight (claim uniformity)', ''),
('ghost.i4_weight', 0.10, 'I4 weight (out-of-schedule)', ''),
('ghost.i5_weight', 0.10, 'I5 weight (room overlap)', ''),
('ghost.i6_weight', 0.05, 'I6 weight (trend)', ''),
('item.absent_unoccluded_windows', 3, 'Windows for ABSENT (items)', 'Item must be unseen in N unoccluded windows.'),
('item.absent_min_days', 2, 'Min days for ABSENT (items)', 'Absence must span ≥ 2 distinct days.')
ON CONFLICT (key) DO NOTHING;
