import json
import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest

from app.database import SessionLocal, init_db
from app.database.migrations import RADIO_OUTPUTS_MARK, migrate_radio_outputs
from app.devices.routing import ROUTES_SETTING
from app.models import (
    RadioAnnouncementRule,
    RadioAnnouncementRuleType,
    Schedule,
    ScheduleTargetType,
    ScheduleType,
    Setting,
)

KEYS = (
    RADIO_OUTPUTS_MARK, ROUTES_SETTING, "display_output_network_2",
    "radio_sound_radio_network", "radio_sound_radio_network_2", "radio_mix_radio_network", "radio_mix_radio_network_2",
)


def _clean():
    with SessionLocal() as db:
        db.query(Schedule).delete()
        db.query(RadioAnnouncementRule).delete()
        db.query(Setting).filter(Setting.key.in_(KEYS)).delete(synchronize_session=False)
        db.commit()


@pytest.fixture()
def legacy():
    init_db()
    _clean()
    with SessionLocal() as db:
        db.add(Schedule(target_type=ScheduleTargetType.radio_playlist, target_id=1, schedule_type=ScheduleType.recurring,
                        recurrence_rule="{}", channel="radio_network"))
        for target in ("radio_network", "radio", "both", "radio_cable"):
            db.add(RadioAnnouncementRule(rule_type=RadioAnnouncementRuleType.every_n_tracks, n_tracks=3, target=target))
        db.add(Setting(key="radio_sound_radio_network", value='{"limiter": true}'))
        db.add(Setting(key="radio_mix_radio_network", value='{"master": {"gain_db": -3}}'))
        db.add(Setting(key=ROUTES_SETTING, value=json.dumps({"radio_network": {"sink_id": "jbl", "key": "jbl"}})))
        db.commit()
    yield
    _clean()


def _state():
    with SessionLocal() as db:
        return {
            "schedules": sorted(s.channel for s in db.query(Schedule).all()),
            "rules": sorted(r.target for r in db.query(RadioAnnouncementRule).all()),
            "settings": {s.key: s.value for s in db.query(Setting).filter(Setting.key.in_(KEYS)).all()},
        }


def test_the_network_radio_moves_to_network_2_and_shared_rules_are_copied(legacy):
    migrate_radio_outputs()
    state = _state()
    assert state["schedules"] == ["radio_network_2"]
    assert state["rules"] == ["radio_cable", "radio_cable", "radio_network_2", "radio_network_2", "radio_network_2"]
    settings = state["settings"]
    assert settings["radio_sound_radio_network_2"] == '{"limiter": true}' and "radio_sound_radio_network" not in settings
    assert settings["radio_mix_radio_network_2"] == '{"master": {"gain_db": -3}}' and "radio_mix_radio_network" not in settings
    assert json.loads(settings[ROUTES_SETTING]) == {"radio_network_2": {"sink_id": "jbl", "key": "jbl"}}
    assert settings["display_output_network_2"] == "radio"


def test_a_second_pass_never_moves_the_new_network_1_radio(legacy):
    migrate_radio_outputs()
    with SessionLocal() as db:
        db.add(Schedule(target_type=ScheduleTargetType.radio_playlist, target_id=2, schedule_type=ScheduleType.recurring,
                        recurrence_rule="{}", channel="radio_network"))
        db.add(Setting(key="radio_sound_radio_network", value='{"limiter": false}'))
        db.commit()
    migrate_radio_outputs()
    state = _state()
    assert state["schedules"] == ["radio_network", "radio_network_2"]
    assert state["settings"]["radio_sound_radio_network"] == '{"limiter": false}'
    assert state["settings"]["radio_sound_radio_network_2"] == '{"limiter": true}'
