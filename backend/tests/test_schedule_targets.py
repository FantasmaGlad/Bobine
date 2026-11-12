import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_schedule_database.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    OverrideAction,
    Playlist,
    Schedule,
    ScheduledLaunch,
    ScheduleOverride,
    ScheduleTargetType,
    ScheduleType,
)
from app.scheduling import launch_store  # noqa: E402


def test_deleting_a_playlist_cleans_the_schedule():
    init_db()
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        db.query(ScheduledLaunch).delete()
        doomed, other = Playlist(name="Supprimée"), Playlist(name="Gardée")
        db.add_all([doomed, other])
        db.flush()
        aimed = Schedule(target_type=ScheduleTargetType.playlist, target_id=doomed.id, schedule_type=ScheduleType.once,
                         run_at=now + timedelta(days=1), active=True, channel="cable")
        kept = Schedule(target_type=ScheduleTargetType.playlist, target_id=other.id, schedule_type=ScheduleType.once,
                        run_at=now + timedelta(days=2), active=True, channel="cable")
        db.add_all([aimed, kept])
        db.flush()
        replaced = ScheduleOverride(schedule_id=kept.id, occurrence_date=kept.run_at, action=OverrideAction.replaced,
                                    replacement_target_type=ScheduleTargetType.playlist, replacement_target_id=doomed.id)
        db.add(replaced)
        db.commit()
        launch_store.remember(db, "cable", "playlist", doomed.id, now)
        ids = (doomed.id, aimed.id, kept.id, replaced.id)

    with TestClient(app) as client:
        assert client.delete(f"/api/playlists/{ids[0]}").status_code == 200

    with SessionLocal() as db:
        assert db.get(Schedule, ids[1]) is None
        assert db.get(Schedule, ids[2]) is not None
        override = db.get(ScheduleOverride, ids[3])
        assert override.action == OverrideAction.cancelled
        assert override.replacement_target_id is None
        assert launch_store.get(db, "cable").active is False
        db.query(ScheduleOverride).delete()
        db.query(Schedule).filter(Schedule.id == ids[2]).delete()
        db.query(Playlist).filter(Playlist.name == "Gardée").delete()
        db.query(ScheduledLaunch).delete()
        db.commit()
