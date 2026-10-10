"""app/db/models/__init__.py — Import all models so Alembic autodiscovers them."""
from app.db.models.centre import Centre, Camera, Zone, SanctionedLayout
from app.db.models.device import Device, DeviceStatusEnum
from app.db.models.session_ import Batch, Session, IngestDedupe
from app.db.models.observation import Observation
from app.db.models.evidence import Evidence
from app.db.models.flag import Flag, FlagInputSnapshot, IntegrityEvent
from app.db.models.case_ import Case, CaseEvent, TCResponse
from app.db.models.threshold import ThresholdProfile
from app.db.models.user import User, RoleBinding
from app.db.models.audit import AuditLog
from app.db.models.camera_integrity import (
    CameraReference,
    SceneObservation,
    CameraIntegrityState,
    CameraStateEvent,
    RebaselineRequest,
    CameraMaintenanceWindow,
)
from app.db.models.ghost import GhostAssessment, GhostStateEvent

__all__ = [
    "Centre", "Camera", "Zone", "SanctionedLayout",
    "Device", "DeviceStatusEnum",
    "Batch", "Session", "IngestDedupe",
    "Observation",
    "Evidence",
    "Flag", "FlagInputSnapshot", "IntegrityEvent",
    "Case", "CaseEvent", "TCResponse",
    "ThresholdProfile",
    "User", "RoleBinding",
    "AuditLog",
    # Camera integrity
    "CameraReference", "SceneObservation", "CameraIntegrityState",
    "CameraStateEvent", "RebaselineRequest", "CameraMaintenanceWindow",
    # Ghost batch
    "GhostAssessment", "GhostStateEvent",
]
