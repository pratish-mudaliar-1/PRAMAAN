"""scripts/reconcile_demo_session.py — Helper to evaluate reconciliation for the demo session."""
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, UTC

sys.path.insert(0, os.path.abspath("backend"))

from app.core.config import get_settings
from app.db.base import create_engine, create_session_factory
from app.db.models.session_ import Session
from app.services.reconciliation import ReconciliationService

async def main():
    with open(".webcam_state/agent_config.json") as f:
        cfg = json.load(f)
    sid = uuid.UUID(cfg["session_id"])

    s = get_settings()
    sqlite_path = os.path.abspath("backend/pramaan_dev.db").replace("\\", "/")
    db_url = f"sqlite+aiosqlite:///{sqlite_path}"
    engine = create_engine(db_url)
    factory = create_session_factory(engine)

    async with factory() as db:
        # Align scheduled_start to 08:00 so all 3 observations fall within window
        sess = await db.get(Session, sid)
        if sess:
            sess.scheduled_start = datetime(2026, 10, 5, 8, 0, 0, tzinfo=UTC)
            await db.flush()

        svc = ReconciliationService(db)
        res = await svc.reconcile_session(sid)
        await db.commit()

        print(f"Reconciliation Status: {res.status}")
        print(f"Attendance Ratio:      {res.ratio}")
        print(f"Observed Count:        {res.observed_hat}")
        print(f"Reason:                {res.reason}")

if __name__ == "__main__":
    asyncio.run(main())
