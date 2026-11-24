import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest

from app.config_apply.context import ConfigErrors
from app.config_apply.runner import _canonical_files
from app.database import SessionLocal, init_db
from app.database.migrations import migrate_schedule_lanes_to_outputs
from app.models import Schedule, ScheduleTargetType, ScheduleType


def _doc(channel, *uids):
    return {"schema": 2, "kind": f"schedule-{channel.replace('_', '-')}", "channel": channel, "schedules": [{"uid": uid} for uid in uids]}


def test_legacy_radio_schedule_files_are_refused():
    files = {"schedule/cable.json": _doc("cable", "a"), "schedule/radio-cable.json": _doc("radio_cable", "c"),
             "schedule/radio-network.json": _doc("radio_network", "d")}
    with pytest.raises(ConfigErrors) as refused:
        _canonical_files(files)
    joined = " ".join(refused.value.errors)
    assert "schedule/radio-cable.json" in joined and "schedule/radio-network.json" in joined


def test_output_schedule_files_are_accepted():
    files = {"schedule/cable.json": _doc("cable", "a"), "settings.json": {"schema": 2}}
    assert sorted(_canonical_files(files)) == ["schedule/cable.json", "settings.json"]


def test_radio_windows_join_the_lane_of_their_output():
    init_db()
    with SessionLocal() as db:
        db.query(Schedule).delete()
        for channel in ("radio_cable", "radio_network", "radio_network_2", "cable"):
            db.add(Schedule(target_type=ScheduleTargetType.radio_playlist, target_id=1, schedule_type=ScheduleType.recurring,
                            recurrence_rule="{}", channel=channel))
        db.commit()
    migrate_schedule_lanes_to_outputs()
    migrate_schedule_lanes_to_outputs()
    with SessionLocal() as db:
        channels = sorted(s.channel for s in db.query(Schedule).all())
        db.query(Schedule).delete()
        db.commit()
    assert channels == ["cable", "cable", "network", "network_2"]
