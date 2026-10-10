"""app/api/v1/schemas.py — Shared Pydantic v2 request/response schemas.

ALL ingestion schemas use extra="forbid" to reject unexpected fields.
No personal identifiers, biometrics or names are accepted.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── Strict base (all ingestion payloads) ──────────────────────────────────────

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False)


# ── Device enrollment ─────────────────────────────────────────────────────────

class DeviceEnrollRequest(StrictModel):
    serial_number: str = Field(min_length=4, max_length=128)
    centre_id: uuid.UUID
    zone_id: uuid.UUID | None = None
    public_key_b64url: str = Field(
        min_length=43, max_length=43,
        description="Base64url-encoded (no padding) 32-byte Ed25519 public key"
    )
    enrollment_token: str = Field(description="One-time enrollment token issued by admin")
    firmware_version: str | None = None
    model_version: str | None = None


class DeviceEnrollResponse(BaseModel):
    device_id: uuid.UUID
    serial_number: str
    status: str


# ── Observation ingestion ─────────────────────────────────────────────────────

class ObservationRecord(StrictModel):
    """One minute-level aggregate record from an edge device.

    Privacy: no names, faces, biometrics, or person identifiers.
    Only aggregate counts computed by the edge privacy-preserving model.
    """
    minute_ts: datetime = Field(description="UTC minute bucket (truncated to minute)")
    zone_id: uuid.UUID
    session_id: uuid.UUID | None = None

    # Aggregate person counts — no individual identification
    persons_min: int | None = Field(None, ge=0)
    persons_median: float | None = Field(None, ge=0)
    persons_p90: float | None = Field(None, ge=0)
    persons_max: int | None = Field(None, ge=0)

    # Item counts — JSONB {"item_class": count}
    item_counts: dict[str, int] | None = None

    # Feed quality
    feed_health: float = Field(ge=0.0, le=1.0)
    frames_used: int = Field(ge=0)

    # Provenance
    model_version: str | None = Field(None, max_length=64)
    record_hash: str = Field(min_length=64, max_length=64, description="SHA-256 hex of canonical payload")
    prev_hash: str | None = Field(None, min_length=64, max_length=64)
    signature: str = Field(description="Base64url Ed25519 signature")

    @field_validator("minute_ts")
    @classmethod
    def _strip_seconds(cls, v: datetime) -> datetime:
        return v.replace(second=0, microsecond=0)


class ObservationBatchRequest(StrictModel):
    device_id: uuid.UUID
    records: list[ObservationRecord] = Field(min_length=1, max_length=500)


class RecordResult(BaseModel):
    record_hash: str
    accepted: bool
    reason: str | None = None


class ObservationBatchResponse(BaseModel):
    device_id: uuid.UUID
    accepted: int
    rejected: int
    results: list[RecordResult]


# ── Device heartbeat ──────────────────────────────────────────────────────────

class HeartbeatRequest(StrictModel):
    device_id: uuid.UUID
    model_version: str | None = None
    config_version: str | None = None
    firmware_version: str | None = None
    queue_depth: int | None = Field(None, ge=0)
    cpu_percent: float | None = Field(None, ge=0, le=100)
    temperature_celsius: float | None = None
    last_frame_ts: datetime | None = None
    free_disk_mb: int | None = Field(None, ge=0)


class HeartbeatResponse(BaseModel):
    acknowledged: bool
    server_ts: datetime
    config_update_available: bool = False


# ── Evidence ──────────────────────────────────────────────────────────────────

class EvidencePresignRequest(StrictModel):
    device_id: uuid.UUID
    zone_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    flag_id: uuid.UUID | None = None
    content_type: str = Field(default="image/jpeg", pattern=r"^image/(jpeg|png|webp)$")
    size_bytes: int = Field(gt=0, le=5 * 1024 * 1024)
    captured_at: datetime | None = None


class EvidencePresignResponse(BaseModel):
    evidence_id: uuid.UUID
    upload_url: str
    fields: dict[str, str]
    expires_in_seconds: int


class EvidenceCompleteRequest(StrictModel):
    evidence_id: uuid.UUID
    sha256_hex: str = Field(min_length=64, max_length=64)


class EvidenceCompleteResponse(BaseModel):
    evidence_id: uuid.UUID
    phash_hex: str | None
    is_near_duplicate: bool
    duplicate_of_id: uuid.UUID | None = None


# ── Pagination cursor ─────────────────────────────────────────────────────────

class CursorPage(BaseModel):
    items: list[Any]
    next_cursor: str | None = None
    total_hint: int | None = None


# ── Centre schemas ────────────────────────────────────────────────────────────

class ZoneResponse(BaseModel):
    id: uuid.UUID
    zone_code: str
    zone_type: str
    coverage_factor: float


class CentreResponse(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    state_code: str
    district: str
    scheme_code: str
    registration_no: str | None = None
    is_active: bool
    lat: float | None = None
    lng: float | None = None
    status: str | None = "GREEN"
    open_flags: int = 0
    suspected_swaps: int = 0
    suspected_ghosts: int = 0
    last_heartbeat: datetime | None = None
    risk_score: float | None = None
    risk_tier: str | None = None


class CentreDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    state_code: str
    district: str
    scheme_code: str
    registration_no: str | None = None
    is_active: bool
    lat: float | None = None
    lng: float | None = None
    status: str | None = "GREEN"
    open_flags: int = 0
    suspected_swaps: int = 0
    suspected_ghosts: int = 0
    last_heartbeat: datetime | None = None
    risk_score: float | None = None
    risk_tier: str | None = None
    zones: list[ZoneResponse] = []


# ── Camera schemas ────────────────────────────────────────────────────────────

class CameraResponse(BaseModel):
    id: uuid.UUID
    centre_id: uuid.UUID
    centre_name: str | None = None
    camera_code: str
    location_description: str | None = None
    is_active: bool
    zone_id: uuid.UUID | None = None
    zone_code: str | None = None
    current_state: str = "STABLE"
    since: datetime | None = None
    consecutive_suspicious: int = 0
    confidence: float | None = None
    last_transition_at: datetime | None = None



class CameraDetailResponse(CameraResponse):
    references_count: int = 0
    observations_count: int = 0
    explanation: dict[str, Any] | None = None


class CameraObservationResponse(BaseModel):
    id: uuid.UUID
    camera_id: uuid.UUID
    ts: datetime
    fused_similarity: float
    orb_inliers: int
    inlier_ratio: float
    classification: str
    source: str


class CameraReferenceResponse(BaseModel):
    id: uuid.UUID
    camera_id: uuid.UUID
    version: int
    s3_key: str
    phash_hex: str | None = None
    lighting_tag: str = "unknown"
    approved_by: str | None = None
    active: bool = True
    created_at: datetime


class UploadCameraReferenceRequest(StrictModel):
    lighting_tag: str = "unknown"
    reason: str = Field(default="Baseline update", max_length=500)
    image_base64: str | None = None


class RebaselineRequestListItemResponse(BaseModel):
    id: uuid.UUID
    camera_id: uuid.UUID
    camera_code: str | None = None
    requested_by: str
    reason: str
    status: str
    inspector_approved_by: str | None = None
    state_officer_approved_by: str | None = None
    new_reference_id: uuid.UUID | None = None
    created_at: datetime


class ApproveRebaselineRequestBody(StrictModel):
    role: str = "inspector"  # inspector | state_officer


class RejectRebaselineRequestBody(StrictModel):
    reason: str = Field(min_length=3, max_length=500)


class MaintenanceWindowRequest(StrictModel):
    starts_at: datetime
    ends_at: datetime
    reason: str = Field(min_length=3, max_length=500)


class MaintenanceWindowResponse(BaseModel):
    id: uuid.UUID
    camera_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    reason: str
    created_by: str
    created_at: datetime


class RebaselineRequestSchema(StrictModel):
    reason: str = Field(min_length=3, max_length=500)
    new_s3_key: str | None = None


class RebaselineResponse(BaseModel):
    camera_id: uuid.UUID
    previous_state: str
    new_state: str
    rebaselined: bool
    reason: str


# ── Ghost Batch schemas ───────────────────────────────────────────────────────

class GhostAssessmentResponse(BaseModel):
    id: uuid.UUID
    batch_id: uuid.UUID
    batch_trade: str | None = None
    batch_scheme: str | None = None
    centre_id: uuid.UUID
    centre_name: str | None = None
    window_start: str
    window_end: str
    state: str
    eligible_days: int
    ghost_days: int
    nodata_days: int = 0
    untrusted_days: int = 0
    pending_days: int = 0
    ghost_score: float
    per_day_detail: list[dict[str, Any]] = []
    explanation: dict[str, Any] = {}
    case_id: uuid.UUID | None = None
    algorithm_version: str = "v1"
    computed_at: datetime


class CentreGhostRollupResponse(BaseModel):
    centre_id: uuid.UUID
    centre_name: str
    total_batches: int
    normal_batches: int
    watch_batches: int
    suspected_ghost_batches: int
    escalated_batches: int
    resolved_batches: int
    centre_ghost_risk_score: float
    batch_assessments: list[dict[str, Any]] = []


class BatchResponse(BaseModel):
    id: uuid.UUID
    centre_id: uuid.UUID
    trade: str
    scheme: str
    start_date: str
    end_date: str
    ghost_state: str = "NORMAL"
    ghost_score: float | None = None
    total_sessions: int = 0


# ── Device schemas ────────────────────────────────────────────────────────────

class DeviceListItemResponse(BaseModel):
    id: uuid.UUID
    serial_number: str
    centre_id: uuid.UUID
    centre_name: str | None = None
    zone_id: uuid.UUID | None = None
    status: str
    is_active: bool
    last_seen_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    firmware_version: str | None = None
    model_version: str | None = None
    queue_depth: int | None = None
    cpu_percent: float | None = None
    temperature_celsius: float | None = None
    free_disk_mb: int | None = None
    health_status: str = "HEALTHY"


# ── Evidence schemas ──────────────────────────────────────────────────────────

class EvidenceItemResponse(BaseModel):
    id: uuid.UUID
    device_id: uuid.UUID
    zone_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    flag_id: uuid.UUID | None = None
    s3_key: str
    content_type: str
    size_bytes: int
    captured_at: datetime
    is_near_duplicate: bool
    duplicate_of_id: uuid.UUID | None = None
    legal_hold: bool = False


class EvidenceViewResponse(BaseModel):
    evidence_id: uuid.UUID
    view_url: str
    expires_in_seconds: int
    content_type: str
    captured_at: datetime | None = None


# ── Threshold schemas ─────────────────────────────────────────────────────────

class ThresholdProfileResponse(BaseModel):
    id: uuid.UUID
    scheme_code: str | None = None
    state_code: str | None = None
    version: int
    is_active: bool
    t_green: float
    t_amber: float
    repeat_n: int
    min_feed_health_fraction: float
    item_absent_min_windows: int
    item_absent_min_days: int
    phash_hamming_threshold: int
    extra: dict[str, Any] | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    approval_note: str | None = None


class ThresholdUpdateRequest(StrictModel):
    t_green: float = Field(ge=0.0, le=1.0)
    t_amber: float = Field(ge=0.0, le=1.0)
    repeat_n: int = Field(ge=1, le=10)
    min_feed_health_fraction: float = Field(ge=0.0, le=1.0)
    item_absent_min_windows: int = Field(ge=1, le=20)
    item_absent_min_days: int = Field(ge=1, le=14)
    phash_hamming_threshold: int = Field(ge=0, le=64)
    approval_note: str | None = Field(None, max_length=500)


# ── Audit schemas ─────────────────────────────────────────────────────────────

class AuditLogResponse(BaseModel):
    id: uuid.UUID
    actor: str
    action: str
    resource_type: str
    resource_id: str | None = None
    request_id: str | None = None
    detail: dict[str, Any] | None = None
    row_hash: str
    prev_hash: str
    occurred_at: datetime

