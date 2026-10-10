"""app/api/v1/__init__.py — API v1 master router."""
from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.audit import router as audit_router
from app.api.v1.cameras import router as cameras_router
from app.api.v1.cases import router as cases_router
from app.api.v1.centres import router as centres_router
from app.api.v1.device import router as device_router
from app.api.v1.evidence import router as evidence_router
from app.api.v1.events import router as events_router
from app.api.v1.flags import router as flags_router
from app.api.v1.ghost import router as ghost_router
from app.api.v1.health import router as health_router
from app.api.v1.ingest import router as ingest_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.thresholds import router as thresholds_router

api_router = APIRouter(prefix="/v1")
api_router.include_router(health_router)
api_router.include_router(device_router)
api_router.include_router(ingest_router)
api_router.include_router(evidence_router)
api_router.include_router(admin_router)
api_router.include_router(events_router)
api_router.include_router(centres_router)
api_router.include_router(sessions_router)
api_router.include_router(flags_router)
api_router.include_router(cases_router)
api_router.include_router(cameras_router)
api_router.include_router(ghost_router)
api_router.include_router(thresholds_router)
api_router.include_router(audit_router)

__all__ = ["api_router"]

