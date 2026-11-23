import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal, init_db
from app.main import app
from app.models import Background, Setting
from app.signage import playlist, store

PREFIX = "data/test_signage_"


@pytest.fixture()
def sent(monkeypatch):
    messages = []

    async def capture(message):
        messages.append(message)

    monkeypatch.setattr("app.api.routes.signage.ws_manager.broadcast", capture)
    return messages


@pytest.fixture()
def media():
    init_db()
    with SessionLocal() as db:
        db.query(Setting).filter(Setting.key.in_(["signage_cable", "signage_network"])).delete(synchronize_session=False)
        db.query(Background).filter(Background.file_path.like(f"{PREFIX}%")).delete(synchronize_session=False)
        image = Background(file_path=f"{PREFIX}affiche.png", title="Affiche")
        video = Background(file_path=f"{PREFIX}clip.mp4", title="Clip", duration_seconds=42.0)
        db.add_all([image, video])
        db.commit()
        return {"image": image.id, "video": video.id}


@pytest.fixture()
def client(sent, media):
    return TestClient(app)


def test_items_are_bounded_and_refused_whole():
    assert playlist.parse_items([{"background_id": 3, "seconds": None}, {"background_id": 4, "seconds": 30}]) == (
        playlist.SignageItem(3, None), playlist.SignageItem(4, 30))
    for bad in ({"background_id": 0}, {"background_id": True}, {"background_id": 2, "seconds": 1},
                {"background_id": 2, "seconds": 3601}, "2"):
        with pytest.raises(ValueError):
            playlist.parse_items([{"background_id": 1}, bad])
    with pytest.raises(ValueError):
        playlist.parse_items([{"background_id": 1}] * (playlist.MAX_ITEMS + 1))


def test_an_image_without_duration_shows_ten_seconds_and_a_video_plays_whole():
    assert playlist.resolved_seconds(playlist.SignageItem(1, None), is_image=True) == playlist.DEFAULT_IMAGE_SECONDS
    assert playlist.resolved_seconds(playlist.SignageItem(1, None), is_image=False) is None
    assert playlist.resolved_seconds(playlist.SignageItem(1, 25), is_image=False) == 25


def test_damaged_stored_loop_reads_as_empty(media):
    with SessionLocal() as db:
        db.add(Setting(key="signage_cable", value="{abîmé"))
        db.commit()
        assert store.load(db, "cable") == ()


def test_loop_is_set_per_channel_then_broadcast(client, sent, media):
    assert client.get("/api/signage").json() == {"channel": "cable", "items": []}
    items = [{"background_id": media["video"], "seconds": None}, {"background_id": media["image"], "seconds": 20}]
    answer = client.put("/api/signage", json={"channel": "network", "items": items}).json()
    assert [(e["title"], e["is_image"], e["play_seconds"]) for e in answer["items"]] == [("Clip", False, None), ("Affiche", True, 20)]
    assert sent == [{"event": "signage_change", "channel": "network"}]
    assert client.get("/api/signage", params={"channel": "network"}).json() == answer
    assert client.get("/api/signage", params={"channel": "cable"}).json()["items"] == []


def test_a_deleted_background_leaves_the_loop(client, media):
    client.put("/api/signage", json={"items": [{"background_id": media["image"]}, {"background_id": media["video"]}]})
    with SessionLocal() as db:
        db.query(Background).filter(Background.id == media["image"]).delete()
        db.commit()
    assert [e["background_id"] for e in client.get("/api/signage").json()["items"]] == [media["video"]]


def test_unknown_background_or_bad_item_is_refused_without_change(client, sent, media):
    missing = client.put("/api/signage", json={"items": [{"background_id": 999999}]})
    assert missing.status_code == 404 and missing.json()["detail"]["code"] == "not_found"
    bad = client.put("/api/signage", json={"items": [{"background_id": media["image"], "seconds": 1}]})
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "invalid"
    wrong_channel = client.put("/api/signage", json={"channel": "radio", "items": []})
    assert wrong_channel.status_code == 422
    assert sent == [] and client.get("/api/signage").json()["items"] == []
