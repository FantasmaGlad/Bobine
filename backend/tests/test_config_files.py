import json
import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

from fastapi.testclient import TestClient

from app import config_files
from app import config_builders
from app import config_mirror
from app.utils.uid import is_uid
from app.database import SessionLocal, init_db
from app.main import app
from app.models import RadioAnnouncement


def _no_uid(value):
    if isinstance(value, dict):
        return {k: _no_uid(v) for k, v in value.items() if k != "uid"}
    if isinstance(value, list):
        return [_no_uid(v) for v in value]
    return value


def _uids(value):
    if isinstance(value, dict):
        return ([value["uid"]] if "uid" in value else []) + [u for v in value.values() for u in _uids(v)]
    if isinstance(value, list):
        return [u for v in value for u in _uids(v)]
    return []


def test_one_file_per_kind_of_setting():
    assert list(config_builders.BUILDERS) == [
        "settings.json", "machine.json", "outputs/display.json", "outputs/radio.json", "library/videos.json",
        "library/audio.json", "library/radio.json", "library/backgrounds.json", "library/announcements.json",
        "playlists/video.json", "playlists/audio.json", "playlists/radio.json", "schedule/cable.json",
        "schedule/network.json", "schedule/network-2.json", "radio/tags.json",
        "radio/announcement-rules.json",
    ]
    assert set(config_files.KINDS) == {"manifest.json", *config_builders.BUILDERS}
    assert set(config_files.LEGACY_NAMES.values()) <= set(config_builders.BUILDERS)


def test_objects_are_referenced_by_readable_keys(library):
    with SessionLocal() as db:
        files = config_builders.export_all(db)
    assert set(files) == {"manifest.json", *config_builders.BUILDERS}
    for name, document in files.items():
        assert document["schema"] == 2 and document["kind"] == config_files.KINDS[name]
        assert '"id"' not in json.dumps(document), name
    videos = files["playlists/video.json"]
    uids = _uids(videos)
    assert all(is_uid(u) for u in uids) and len(set(uids)) == len(uids)
    assert _no_uid(videos["playlists"][0]) == {
        "name": "Lundi soir",
        "videos": [{"title": "RPM 110", "program": "RPM", "release": "110", "file": "rpm-110.mp4"}],
    }
    assert videos["warnings"] == ["playlist en double : Lundi soir"]
    audio = files["playlists/audio.json"]["playlists"][0]["tracks"][0]
    assert audio["track"]["course"]["title"] == "Échauffement" and _no_uid(audio["background"]) == {"title": "Lagon", "file": "lagon.mp4"}
    assert files["playlists/radio.json"]["playlists"][0]["default"] is True
    assert files["radio/tags.json"]["assignments"][0]["tags"] == ["calme"]
    assert [t["name"] for t in files["radio/tags.json"]["tags"]] == ["calme"]
    assert _no_uid(files["radio/announcement-rules.json"]["rules"]) == [
        {"type": "fixed_times", "target": "radio_cable", "enabled": True, "times_of_day": ["09:00"]},
    ]
    cable = files["schedule/cable.json"]
    assert cable["channel"] == "cable" and files["schedule/network.json"]["schedules"] == []
    assert _no_uid(cable["schedules"][0]["target"]) == {"type": "playlist", "name": "Lundi soir"}
    assert cable["schedules"][0]["recurrence"] == {"days_of_week": [0], "time": "18:30"}
    assert _no_uid(cable["schedules"][0]["overrides"]) == [{"date": "2026-12-21", "action": "cancelled", "replacement": None}]
    assert set(files["machine.json"]["machine"]) >= {"display_mode", "audio_routes", "storage"}


def test_api_exports_all_files_or_one(library):
    client = TestClient(app)
    everything = client.get("/api/config/export").json()
    assert everything["schema"] == 2 and "schedule/network-2.json" in everything["files"] and "manifest.json" in everything["files"]
    assert client.get("/api/config/export/library/announcements.json").json()["announcements"][0]["description"] == (
        "Pensez à votre bouteille"
    )
    assert client.get("/api/config/export/announcements.json").json()["kind"] == "announcements"
    assert client.get("/api/config/export/manifest.json").json()["kind"] == "manifest"
    unknown = client.get("/api/config/export/inconnu.json")
    assert unknown.status_code == 404 and unknown.json()["detail"]["code"] == "unknown_config_file"


def test_mirror_rewrites_only_changed_files(library, tmp_path, monkeypatch):
    monkeypatch.setattr(config_mirror, "mirror_dir", lambda: tmp_path / "config")
    assert config_mirror.write_mirror() == len(config_builders.BUILDERS) + 1
    assert json.loads((tmp_path / "config" / "settings.json").read_text(encoding="utf-8"))["kind"] == "settings"
    assert (tmp_path / "config" / "playlists" / "video.json").exists()
    assert config_mirror.write_mirror() == 0
    with SessionLocal() as db:
        db.query(RadioAnnouncement).update({"enabled": False})
        db.commit()
    assert config_mirror.write_mirror() == 1


def test_a_successful_change_requests_a_mirror_update(monkeypatch):
    init_db()
    calls = []
    monkeypatch.setattr(config_mirror, "schedule_mirror", lambda: calls.append(True))
    client = TestClient(app)
    client.get("/api/settings")
    assert calls == []
    client.put("/api/settings", json={"language": "en"})
    client.put("/api/settings", json={"language": "xx"})
    client.put("/api/settings", json={"language": "fr"})
    assert len(calls) == 2
