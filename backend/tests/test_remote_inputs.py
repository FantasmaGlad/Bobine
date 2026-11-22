import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal, init_db
from app.inputs import overrides as rules
from app.inputs import store
from app.inputs.bindings import DEFAULT_BINDINGS
from app.main import app
from app.models import Setting


@pytest.fixture()
def sent(monkeypatch):
    messages = []

    async def capture(message):
        messages.append(message)

    monkeypatch.setattr("app.api.routes.settings.inputs.ws_manager.broadcast", capture)
    return messages


@pytest.fixture()
def client(sent):
    init_db()
    with SessionLocal() as db:
        db.query(Setting).filter(Setting.key == store.KEY).delete()
        db.commit()
    return TestClient(app)


def test_overrides_merge_with_defaults_and_can_disable_an_input():
    overrides = rules.with_override({}, "key:F1", ["chapter_next", "next"])
    overrides = rules.with_override(overrides, "key:ArrowLeft", [])
    bindings = rules.effective_bindings(overrides)
    assert bindings["key:F1"] == ["chapter_next", "next"]
    assert "key:ArrowLeft" not in bindings
    assert bindings["key:ArrowRight"] == list(DEFAULT_BINDINGS["key:ArrowRight"])
    assert "key:ArrowLeft" not in rules.with_override(overrides, "key:ArrowLeft", None)


@pytest.mark.parametrize("source, actions", [
    ("F1", ["next"]), ("code:1000", ["next"]), ("pad:20", ["next"]), ("key:" + "x" * 33, ["next"]),
    ("key:F1", ["voler"]), ("key:F1", ["next", "next"]), ("key:F1", ["up", "down", "left", "right"]), ("key:F1", "next"),
])
def test_out_of_bounds_inputs_and_actions_are_refused(source, actions):
    with pytest.raises(ValueError):
        rules.with_override({}, source, actions)


def test_at_most_64_custom_bindings():
    overrides = {f"code:{value}": ("next",) for value in range(rules.MAX_OVERRIDES)}
    with pytest.raises(ValueError):
        rules.with_override(overrides, "code:999", ["prev"])


def test_damaged_stored_value_falls_back_to_defaults():
    init_db()
    with SessionLocal() as db:
        db.query(Setting).filter(Setting.key == store.KEY).delete()
        db.add(Setting(key=store.KEY, value='{"key:F1": ["voler"]}'))
        db.commit()
        assert store.load(db) == {}
        db.query(Setting).filter(Setting.key == store.KEY).delete()
        db.commit()


def test_routes_set_disable_restore_and_reset_then_broadcast(client, sent):
    listed = client.get("/api/settings/inputs").json()
    assert listed["overrides"] == {} and listed["bindings"]["key:ArrowLeft"] == ["left"]

    changed = client.patch("/api/settings/inputs", json={"input": "key:F1", "actions": ["chapter_next"]}).json()
    assert changed["overrides"] == {"key:F1": ["chapter_next"]} and changed["bindings"]["key:F1"] == ["chapter_next"]
    assert sent[-1] == {"event": "inputs_change", "bindings": changed["bindings"]}

    off = client.patch("/api/settings/inputs", json={"input": "key:ArrowLeft", "actions": []}).json()
    assert "key:ArrowLeft" not in off["bindings"] and off["overrides"]["key:ArrowLeft"] == []

    restored = client.patch("/api/settings/inputs", json={"input": "key:ArrowLeft"}).json()
    assert restored["bindings"]["key:ArrowLeft"] == ["left"]

    reset = client.delete("/api/settings/inputs").json()
    assert reset["overrides"] == {} and len(sent) == 4
    assert client.get("/api/settings/inputs").json()["overrides"] == {}


def test_routes_refuse_unknown_actions_with_the_common_error_shape(client, sent):
    answer = client.patch("/api/settings/inputs", json={"input": "key:F1", "actions": ["voler"]})
    assert answer.status_code == 422
    assert answer.json()["detail"]["code"] == "invalid" and "voler" in answer.json()["detail"]["message"]
    assert sent == []
