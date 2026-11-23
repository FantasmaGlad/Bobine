import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

from app.config_apply.legacy_schedules import merge_radio_schedules
from app.database import SessionLocal, init_db
from app.database.migrations import migrate_schedule_lanes_to_outputs
from app.models import Schedule, ScheduleTargetType, ScheduleType


def _doc(channel, *uids):
    return {"schema": 2, "kind": f"schedule-{channel.replace('_', '-')}", "channel": channel, "schedules": [{"uid": uid} for uid in uids]}


def test_a_5x_export_sends_the_network_radio_to_network_2():
    files = {"schedule/cable.json": _doc("cable", "a"), "schedule/network.json": _doc("network", "b"),
             "schedule/radio-cable.json": _doc("radio_cable", "c"), "schedule/radio-network.json": _doc("radio_network", "d")}
    merged = merge_radio_schedules(files)
    assert sorted(merged) == ["schedule/cable.json", "schedule/network-2.json", "schedule/network.json"]
    assert [e["uid"] for e in merged["schedule/cable.json"]["schedules"]] == ["a", "c"]
    assert [e["uid"] for e in merged["schedule/network.json"]["schedules"]] == ["b"]
    assert merged["schedule/network-2.json"]["channel"] == "network_2"
    assert [e["uid"] for e in merged["schedule/network-2.json"]["schedules"]] == ["d"]


def test_a_recent_export_keeps_each_radio_on_its_own_output():
    files = {"schedule/radio-network.json": _doc("radio_network", "e"), "schedule/radio-network-2.json": _doc("radio_network_2", "f"),
             "schedule-radio-cable.json": _doc("radio_cable", "g")}
    merged = merge_radio_schedules(files)
    assert {name: [e["uid"] for e in doc["schedules"]] for name, doc in merged.items()} == {
        "schedule/network.json": ["e"], "schedule/network-2.json": ["f"], "schedule/cable.json": ["g"]}


def test_files_without_radio_lanes_are_untouched():
    files = {"schedule/cable.json": _doc("cable", "a"), "settings.json": {"schema": 2}}
    assert merge_radio_schedules(files) is files


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
