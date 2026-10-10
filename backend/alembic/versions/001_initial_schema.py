"""001_initial_schema — Complete database schema migration for PRAMAAN.

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-10-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Core TC & Hierarchy ──────────────────────────────────────────────────
    op.create_table(
        "centre",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("state_code", sa.String(8), nullable=False),
        sa.Column("district", sa.String(128), nullable=False),
        sa.Column("scheme_code", sa.String(64), nullable=False),
        sa.Column("registration_no", sa.String(128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_centre_code", "centre", ["code"])
    op.create_index("ix_centre_state_code", "centre", ["state_code"])
    op.create_index("ix_centre_scheme_code", "centre", ["scheme_code"])

    op.create_table(
        "camera",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("centre_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("centre.id", ondelete="CASCADE"), nullable=False),
        sa.Column("camera_code", sa.String(64), nullable=False),
        sa.Column("location_description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("installed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("centre_id", "camera_code", name="uq_camera_centre_code"),
    )
    op.create_index("ix_camera_centre_id", "camera", ["centre_id"])

    op.create_table(
        "zone",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("centre_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("centre.id", ondelete="CASCADE"), nullable=False),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("camera.id", ondelete="SET NULL"), nullable=True),
        sa.Column("zone_code", sa.String(64), nullable=False),
        sa.Column("zone_type", sa.String(64), nullable=False),
        sa.Column("polygon", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("coverage_factor", sa.Numeric(4, 3), nullable=False, server_default=sa.text("1.0")),
        sa.Column("multi_camera_strategy", sa.String(16), nullable=False, server_default=sa.text("'max'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("centre_id", "zone_code", name="uq_zone_centre_code"),
    )
    op.create_index("ix_zone_centre_id", "zone", ["centre_id"])

    op.create_table(
        "sanctioned_layout",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("centre_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("centre.id", ondelete="CASCADE"), nullable=False),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("zone.id", ondelete="SET NULL"), nullable=True),
        sa.Column("item_class", sa.String(64), nullable=False),
        sa.Column("sanctioned_count", sa.Integer(), nullable=False),
        sa.Column("critical", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sanctioned_layout_centre_id", "sanctioned_layout", ["centre_id"])

    # ── Devices & Auth ────────────────────────────────────────────────────────
    op.create_table(
        "device",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("centre_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("centre.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("zone.id", ondelete="SET NULL"), nullable=True),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("camera.id", ondelete="SET NULL"), nullable=True),
        sa.Column("serial_number", sa.String(128), nullable=False, unique=True),
        sa.Column("public_key", sa.LargeBinary(32), nullable=False),
        sa.Column("public_key_b64url", sa.String(64), nullable=False),
        sa.Column("enrollment_token_hash", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("model_version", sa.String(64), nullable=True),
        sa.Column("config_version", sa.String(64), nullable=True),
        sa.Column("firmware_version", sa.String(64), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_telemetry", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.Column("last_accepted_hash", sa.String(64), nullable=True),
        sa.Column("last_accepted_seq", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_device_serial_number", "device", ["serial_number"])
    op.create_index("ix_device_centre_id", "device", ["centre_id"])
    op.create_index("ix_device_zone_id", "device", ["zone_id"])

    # ── Sessions & Batches ───────────────────────────────────────────────────
    op.create_table(
        "batch",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("centre_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("centre.id", ondelete="CASCADE"), nullable=False),
        sa.Column("batch_code", sa.String(64), nullable=False),
        sa.Column("scheme_code", sa.String(64), nullable=False),
        sa.Column("trade_code", sa.String(64), nullable=True),
        sa.Column("enrolled_count", sa.Integer(), nullable=False),
        sa.Column("batch_start_date", sa.Date(), nullable=False),
        sa.Column("batch_end_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("source_ref", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("centre_id", "batch_code", name="uq_batch_centre_code"),
    )
    op.create_index("ix_batch_centre_id", "batch", ["centre_id"])

    op.create_table(
        "session",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batch.id", ondelete="CASCADE"), nullable=False),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("zone.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_count", sa.Integer(), nullable=True),
        sa.Column("trainer_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("attendance_status", sa.String(16), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("attendance_ratio", sa.Float(), nullable=True),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_ref", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_session_batch_id", "session", ["batch_id"])
    op.create_index("ix_session_scheduled_start", "session", ["scheduled_start"])

    # ── Ingestion & Observations ─────────────────────────────────────────────
    op.create_table(
        "ingest_dedupe",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("device.id", ondelete="CASCADE"), nullable=False),
        sa.Column("record_hash", sa.String(64), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("observation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.UniqueConstraint("device_id", "record_hash", name="uq_dedupe_device_hash"),
    )
    op.create_index("ix_dedupe_device_id", "ingest_dedupe", ["device_id"])

    op.create_table(
        "observation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("minute_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("device.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("zone.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("session.id", ondelete="SET NULL"), nullable=True),
        sa.Column("persons_min", sa.Integer(), nullable=True),
        sa.Column("persons_median", sa.Float(), nullable=True),
        sa.Column("persons_p90", sa.Float(), nullable=True),
        sa.Column("persons_max", sa.Integer(), nullable=True),
        sa.Column("item_counts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("feed_health", sa.Float(), nullable=False),
        sa.Column("frames_used", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=True),
        sa.Column("record_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("prev_hash", sa.String(64), nullable=True),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("chain_ok", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("clock_skew_ms", sa.Integer(), nullable=True),
        sa.Column("trust", sa.String(16), nullable=False, server_default=sa.text("'TRUSTED'")),
        sa.Column("scene_score_edge", sa.Float(), nullable=True),
        sa.Column("orb_inliers_edge", sa.Integer(), nullable=True),
        sa.Column("phash_dist_edge", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_observation_device_ts", "observation", ["device_id", "minute_ts"])
    op.create_index("ix_observation_zone_ts", "observation", ["zone_id", "minute_ts"])

    # ── Evidence & Perceptual Hash ───────────────────────────────────────────
    op.create_table(
        "evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("device.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("zone.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("flag_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("session.id", ondelete="SET NULL"), nullable=True),
        sa.Column("s3_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=False, server_default=sa.text("'image/jpeg'")),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("phash_hex", sa.String(16), nullable=True),
        sa.Column("phash_int", sa.BigInteger(), nullable=True),
        sa.Column("sha256_hex", sa.String(64), nullable=False),
        sa.Column("is_near_duplicate", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("duplicate_of_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evidence.id", ondelete="SET NULL"), nullable=True),
        sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evidence_device_id", "evidence", ["device_id"])
    op.create_index("ix_evidence_phash_hex", "evidence", ["phash_hex"])

    # ── Cases & Flags ────────────────────────────────────────────────────────
    op.create_table(
        "case",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("centre_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("centre.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_number", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'OPEN'")),
        sa.Column("priority", sa.String(16), nullable=False, server_default=sa.text("'MEDIUM'")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("assigned_to", sa.String(128), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_breached", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closure_reason", sa.Text(), nullable=True),
        sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_case_centre_id", "case", ["centre_id"])
    op.create_index("ix_case_status", "case", ["status"])

    op.create_table(
        "flag",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("centre_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("centre.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("session.id", ondelete="SET NULL"), nullable=True),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("zone.id", ondelete="SET NULL"), nullable=True),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("device.id", ondelete="SET NULL"), nullable=True),
        sa.Column("flag_key", sa.String(128), nullable=False, unique=True),
        sa.Column("flag_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False, server_default=sa.text("'AMBER'")),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column("rule_name", sa.String(128), nullable=False),
        sa.Column("rule_version", sa.String(32), nullable=False, server_default=sa.text("'v1'")),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("case.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_flag_centre_id", "flag", ["centre_id"])
    op.create_index("ix_flag_session_id", "flag", ["session_id"])
    op.create_index("ix_flag_case_id", "flag", ["case_id"])

    op.create_table(
        "flag_input_snapshot",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("flag_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("flag.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("inputs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("thresholds", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=True),
        sa.Column("evidence_links", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "integrity_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("device.id", ondelete="CASCADE"), nullable=False),
        sa.Column("centre_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("centre.id", ondelete="CASCADE"), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False, server_default=sa.text("'HIGH'")),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("record_hash", sa.String(64), nullable=True),
        sa.Column("flag_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("flag.id", ondelete="SET NULL"), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_integrity_event_device_id", "integrity_event", ["device_id"])

    op.create_table(
        "case_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("case.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(32), nullable=False),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_case_event_case_id", "case_event", ["case_id"])

    op.create_table(
        "tc_response",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("case.id", ondelete="CASCADE"), nullable=False),
        sa.Column("responder", sa.String(128), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=False),
        sa.Column("attachment_s3_keys", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tc_response_case_id", "tc_response", ["case_id"])

    # ── Threshold Profiles & Users ───────────────────────────────────────────
    op.create_table(
        "threshold_profile",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scheme_code", sa.String(64), nullable=False),
        sa.Column("state_code", sa.String(8), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("approved_by", sa.String(128), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_note", sa.Text(), nullable=True),
        sa.Column("t_green", sa.Float(), nullable=False, server_default=sa.text("0.80")),
        sa.Column("t_amber", sa.Float(), nullable=False, server_default=sa.text("0.50")),
        sa.Column("repeat_n", sa.Integer(), nullable=False, server_default=sa.text("2")),
        sa.Column("min_feed_health_fraction", sa.Float(), nullable=False, server_default=sa.text("0.50")),
        sa.Column("item_absent_min_windows", sa.Integer(), nullable=False, server_default=sa.text("2")),
        sa.Column("item_absent_min_days", sa.Integer(), nullable=False, server_default=sa.text("2")),
        sa.Column("phash_hamming_threshold", sa.Integer(), nullable=False, server_default=sa.text("5")),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "user",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("subject", sa.String(256), nullable=False, unique=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_user_subject", "user", ["subject"])

    op.create_table(
        "role_binding",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("centre_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("centre.id", ondelete="CASCADE"), nullable=True),
        sa.Column("state_code", sa.String(8), nullable=True),
        sa.Column("granted_by", sa.String(256), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_role_binding_user_id", "role_binding", ["user_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor", sa.String(256), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("ip_hash", sa.String(64), nullable=True),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("row_hash", sa.String(64), nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_log_occurred_at", "audit_log", ["occurred_at"])

    # ── Camera Integrity ─────────────────────────────────────────────────────
    op.create_table(
        "camera_reference",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("camera.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("s3_key", sa.Text(), nullable=False),
        sa.Column("features_blob", sa.LargeBinary(), nullable=True),
        sa.Column("phash_hex", sa.String(16), nullable=True),
        sa.Column("hsv_histogram_blob", sa.LargeBinary(), nullable=True),
        sa.Column("mask_polygons", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("redaction_mask", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("lighting_tag", sa.String(32), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("approved_by", sa.String(256), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("algorithm_version", sa.String(32), nullable=False, server_default=sa.text("'v1'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_camera_reference_camera_id", "camera_reference", ["camera_id"])

    op.create_table(
        "scene_observation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("camera.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(16), nullable=False, server_default=sa.text("'live'")),
        sa.Column("reference_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("camera_reference.id", ondelete="SET NULL"), nullable=True),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evidence.id", ondelete="SET NULL"), nullable=True),
        sa.Column("phash_dist", sa.Integer(), nullable=False),
        sa.Column("orb_inliers", sa.Integer(), nullable=False),
        sa.Column("inlier_ratio", sa.Float(), nullable=False),
        sa.Column("ssim_masked", sa.Float(), nullable=False),
        sa.Column("hist_distance", sa.Float(), nullable=False),
        sa.Column("fused_similarity", sa.Float(), nullable=False),
        sa.Column("transform_params", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("classification", sa.String(32), nullable=False),
        sa.Column("algorithm_version", sa.String(32), nullable=False, server_default=sa.text("'v1'")),
    )
    op.create_index("ix_scene_obs_camera_ts", "scene_observation", ["camera_id", "ts"])

    op.create_table(
        "camera_integrity_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("camera.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("state", sa.String(32), nullable=False, server_default=sa.text("'STABLE'")),
        sa.Column("since", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_suspected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_transition_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_suspicious", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("consecutive_stable", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("algorithm_version", sa.String(32), nullable=False, server_default=sa.text("'v1'")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "camera_state_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("camera.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_state", sa.String(32), nullable=False),
        sa.Column("to_state", sa.String(32), nullable=False),
        sa.Column("transitioned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("metrics_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("cause", sa.String(32), nullable=False, server_default=sa.text("'evaluation'")),
        sa.Column("triggered_by", sa.String(256), nullable=True),
    )
    op.create_index("ix_camera_state_event_camera_id", "camera_state_event", ["camera_id"])

    op.create_table(
        "rebaseline_request",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("camera.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by", sa.String(256), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'PENDING_INSPECTOR'")),
        sa.Column("inspector_approved_by", sa.String(256), nullable=True),
        sa.Column("inspector_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state_officer_approved_by", sa.String(256), nullable=True),
        sa.Column("state_officer_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_by", sa.String(256), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("new_reference_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("camera_reference.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "camera_maintenance_window",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("camera.id", ondelete="CASCADE"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_maint_window_camera_id", "camera_maintenance_window", ["camera_id"])

    # ── Ghost Batch ──────────────────────────────────────────────────────────
    op.create_table(
        "ghost_assessment",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batch.id", ondelete="CASCADE"), nullable=False),
        sa.Column("centre_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("centre.id", ondelete="CASCADE"), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("eligible_days", sa.Integer(), nullable=False),
        sa.Column("ghost_days", sa.Integer(), nullable=False),
        sa.Column("nodata_days", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("untrusted_days", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("pending_days", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("per_day_detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ghost_score", sa.Float(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column("hysteresis_ok_streak", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("algorithm_version", sa.String(32), nullable=False, server_default=sa.text("'v1'")),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("case.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_ghost_assessment_batch_id", "ghost_assessment", ["batch_id"])
    op.create_index("ix_ghost_assessment_centre_id", "ghost_assessment", ["centre_id"])

    op.create_table(
        "ghost_state_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batch.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ghost_assessment.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_state", sa.String(32), nullable=False),
        sa.Column("to_state", sa.String(32), nullable=False),
        sa.Column("transitioned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("metrics_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("cause", sa.String(32), nullable=False, server_default=sa.text("'evaluation'")),
    )
    op.create_index("ix_ghost_state_event_batch_id", "ghost_state_event", ["batch_id"])


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("ghost_state_event")
    op.drop_table("ghost_assessment")
    op.drop_table("camera_maintenance_window")
    op.drop_table("rebaseline_request")
    op.drop_table("camera_state_event")
    op.drop_table("camera_integrity_state")
    op.drop_table("scene_observation")
    op.drop_table("camera_reference")
    op.drop_table("audit_log")
    op.drop_table("role_binding")
    op.drop_table("user")
    op.drop_table("threshold_profile")
    op.drop_table("tc_response")
    op.drop_table("case_event")
    op.drop_table("integrity_event")
    op.drop_table("flag_input_snapshot")
    op.drop_table("flag")
    op.drop_table("case")
    op.drop_table("evidence")
    op.drop_table("observation")
    op.drop_table("ingest_dedupe")
    op.drop_table("session")
    op.drop_table("batch")
    op.drop_table("device")
    op.drop_table("sanctioned_layout")
    op.drop_table("zone")
    op.drop_table("camera")
    op.drop_table("centre")
