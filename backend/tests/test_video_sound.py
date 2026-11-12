import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Setting  # noqa: E402
from app.playback.manager import get_playback_manager  # noqa: E402
from app.utils.radio_sound import default_sound  # noqa: E402
from app.utils.video_sound import load_all_video_sounds_into_managers, load_video_sound, video_sound_setting_key  # noqa: E402

KEYS = [video_sound_setting_key("cable"), video_sound_setting_key("network")]


def _clean():
    with SessionLocal() as db:
        db.query(Setting).filter(Setting.key.in_(KEYS)).delete(synchronize_session=False)
        db.commit()
    for channel in ("cable", "network"):
        get_playback_manager(channel).state["sound"] = default_sound()


@pytest.fixture()
def client(monkeypatch):
    from app import config_files
    monkeypatch.setattr(config_files, "schedule_mirror", lambda: None)
    with TestClient(app) as c:
        _clean()
        yield c
        _clean()


def test_every_channel_starts_flat(client):
    assert get_playback_manager("cable").snapshot()["sound"] == default_sound()


def test_sound_is_bounded_per_channel_and_persisted(client):
    answer = client.post("/api/playback/cable/set_sound", json={"sound": {"bands": [99, -99, 3, "x", 0], "bass_boost": 50, "loudness": True}})
    assert answer.status_code == 200
    sound = answer.json()["state"]["sound"]
    assert sound["bands"] == [12, -12, 3, 0, 0] and sound["bass_boost"] == 12 and sound["loudness"] is True
    with SessionLocal() as db:
        assert load_video_sound(db, "cable") == sound
        assert load_video_sound(db, "network") == default_sound()
    assert get_playback_manager("network").snapshot()["sound"] == default_sound()


def test_absent_fields_keep_their_value(client):
    client.post("/api/playback/network/set_sound", json={"sound": {"bands": [1, 2, 3, 4, 5], "limiter": False}})
    sound = client.post("/api/playback/network/set_sound", json={"sound": {"loudness": True}}).json()["state"]["sound"]
    assert sound["bands"] == [1, 2, 3, 4, 5] and sound["limiter"] is False and sound["loudness"] is True


def test_garbage_never_fails(client):
    for payload in ({"sound": None}, {"sound": "abc"}, {"sound": {"bands": "x", "enabled": 3}}, {}):
        assert client.post("/api/playback/cable/set_sound", json=payload).status_code == 200


def test_settings_are_reloaded_at_startup(client):
    client.post("/api/playback/cable/set_sound", json={"sound": {"bass_boost": 7}})
    get_playback_manager("cable").state["sound"] = default_sound()
    with SessionLocal() as db:
        load_all_video_sounds_into_managers(db)
    assert get_playback_manager("cable").state["sound"]["bass_boost"] == 7


def test_state_change_carries_the_sound(client):
    with client.websocket_connect("/ws/playback") as ws:
        ws.send_json({"command": "set_sound", "params": {"channel": "cable", "sound": {"bass_boost": 5}}})
        for _ in range(50):
            message = ws.receive_json()
            if message.get("event") == "state_change" and message.get("cause") == "sound_change":
                assert message["data"]["sound"]["bass_boost"] == 5
                break
        else:
            raise AssertionError("sound_change jamais reçu")


def test_sound_travels_in_the_display_config_file(client):
    from app import config_files
    client.post("/api/playback/cable/set_sound", json={"sound": {"bass_boost": 4}})
    with SessionLocal() as db:
        document = config_files.build_display_outputs(db)
    assert document["sound"]["cable"]["bass_boost"] == 4 and document["sound"]["network"] == default_sound()
