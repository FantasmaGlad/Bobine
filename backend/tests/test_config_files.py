"""Configuration en fichiers JSON : un fichier par type de réglage, objets désignés par leurs noms et métadonnées (jamais par identifiant interne), homonymes signalés, copie lisible tenue à jour après chaque modification."""

import json
import os
from datetime import datetime, timezone

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import config_files  # noqa: E402
from app.utils.uid import is_uid
from app.database import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    AudioCourse, AudioPlaylist, AudioPlaylistItem, AudioTrack, Background, ImportSource, OverrideAction, Playlist,
    PlaylistItem, RadioAnnouncement, RadioAnnouncementRule, RadioAnnouncementRuleType, RadioPlaylist,
    RadioPlaylistItem, RadioTag, RadioTrack, Schedule, ScheduleOverride, ScheduleTargetType, ScheduleType, Video,
)

MODELS = (
    ScheduleOverride, Schedule, AudioPlaylistItem, AudioPlaylist, AudioTrack, AudioCourse, PlaylistItem, Playlist,
    RadioPlaylistItem, RadioPlaylist, RadioAnnouncementRule, RadioAnnouncement, Video, Background,
)


def _clean():
    with SessionLocal() as db:
        for model in MODELS + (RadioTrack, RadioTag):
            db.query(model).delete()
        db.commit()


@pytest.fixture()
def library():
    init_db()
    _clean()
    with SessionLocal() as db:
        background = Background(file_path="/media/fonds/lagon.mp4", title="Lagon")
        video = Video(file_path="/media/videos/rpm-110.mp4", title="RPM 110", program="RPM", release="110",
                      source=ImportSource.upload)
        db.add_all([background, video])
        db.flush()
        playlist = Playlist(name="Lundi soir")
        playlist.items = [PlaylistItem(video_id=video.id, position=0)]
        twin = Playlist(name="Lundi soir")
        course = AudioCourse(title="Échauffement", program="BODYPUMP", release="120")
        db.add_all([playlist, twin, course])
        db.flush()
        track = AudioTrack(audio_course_id=course.id, number=1, title="Warm Up", file_path="/media/audio/bp120-01.mp3",
                           position=0)
        db.add(track)
        db.flush()
        mix = AudioPlaylist(name="Mix pump")
        mix.items = [AudioPlaylistItem(audio_track_id=track.id, position=0, background_id=background.id)]
        tag = RadioTag(name="calme")
        song = RadioTrack(file_path="/media/radio/aube.mp3", title="Aube", artist="Nils", album="Matin",
                          source=ImportSource.upload, tags=[tag])
        db.add_all([mix, song])
        db.flush()
        ambiance = RadioPlaylist(name="Ambiance", is_default=True)
        ambiance.items = [RadioPlaylistItem(radio_track_id=song.id, position=0)]
        db.add_all([
            ambiance,
            RadioAnnouncement(file_path="/media/rappels/bouteille.mp3", description="Pensez à votre bouteille"),
            RadioAnnouncementRule(rule_type=RadioAnnouncementRuleType.fixed_times, times_of_day='["09:00"]',
                                  target="both"),
        ])
        db.flush()
        schedule = Schedule(target_type=ScheduleTargetType.playlist, target_id=playlist.id,
                            schedule_type=ScheduleType.recurring, recurrence_rule='{"days_of_week": [0], "time": "18:30"}',
                            channel="cable")
        schedule.overrides = [ScheduleOverride(occurrence_date=datetime(2026, 12, 21, tzinfo=timezone.utc),
                                               action=OverrideAction.cancelled)]
        db.add(schedule)
        db.commit()
    yield
    _clean()


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
    assert list(config_files.BUILDERS) == [
        "settings.json", "machine.json", "outputs/display.json", "outputs/radio.json", "library/videos.json",
        "library/audio.json", "library/radio.json", "library/backgrounds.json", "library/announcements.json",
        "playlists/video.json", "playlists/audio.json", "playlists/radio.json", "schedule/cable.json",
        "schedule/network.json", "schedule/radio-cable.json", "schedule/radio-network.json", "radio/tags.json",
        "radio/announcement-rules.json",
    ]
    assert set(config_files.KINDS) == {"manifest.json", *config_files.BUILDERS}
    assert set(config_files.LEGACY_NAMES.values()) <= set(config_files.BUILDERS)


def test_objects_are_referenced_by_readable_keys(library):
    with SessionLocal() as db:
        files = config_files.export_all(db)
    assert set(files) == {"manifest.json", *config_files.BUILDERS}
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
        {"type": "fixed_times", "target": "both", "enabled": True, "times_of_day": ["09:00"]},
    ]
    cable = files["schedule/cable.json"]
    assert cable["channel"] == "cable" and files["schedule/network.json"]["schedules"] == []
    assert _no_uid(cable["schedules"][0]["target"]) == {"type": "playlist", "name": "Lundi soir"}
    assert cable["schedules"][0]["recurrence"] == {"days_of_week": [0], "time": "18:30"}
    assert _no_uid(cable["schedules"][0]["overrides"]) == [{"date": "2026-12-21", "action": "cancelled", "replacement": None}]
    assert set(files["machine.json"]["machine"]) >= {"display_mode", "update_tor", "audio_routes", "storage"}


def test_api_exports_all_files_or_one(library):
    client = TestClient(app)
    everything = client.get("/api/config/export").json()
    assert everything["schema"] == 2 and "schedule/radio-network.json" in everything["files"] and "manifest.json" in everything["files"]
    assert client.get("/api/config/export/library/announcements.json").json()["announcements"][0]["description"] == (
        "Pensez à votre bouteille"
    )
    assert client.get("/api/config/export/announcements.json").json()["kind"] == "announcements"
    assert client.get("/api/config/export/manifest.json").json()["kind"] == "manifest"
    unknown = client.get("/api/config/export/inconnu.json")
    assert unknown.status_code == 404 and unknown.json()["detail"]["code"] == "unknown_config_file"


def test_mirror_rewrites_only_changed_files(library, tmp_path, monkeypatch):
    monkeypatch.setattr(config_files, "mirror_dir", lambda: tmp_path / "config")
    assert config_files.write_mirror() == len(config_files.BUILDERS) + 1
    assert json.loads((tmp_path / "config" / "settings.json").read_text(encoding="utf-8"))["kind"] == "settings"
    assert (tmp_path / "config" / "playlists" / "video.json").exists()
    assert config_files.write_mirror() == 0
    with SessionLocal() as db:
        db.query(RadioAnnouncement).update({"enabled": False})
        db.commit()
    assert config_files.write_mirror() == 1


def test_a_successful_change_requests_a_mirror_update(monkeypatch):
    init_db()
    calls = []
    monkeypatch.setattr(config_files, "schedule_mirror", lambda: calls.append(True))
    client = TestClient(app)
    client.get("/api/settings")
    assert calls == []
    client.put("/api/settings", json={"language": "en"})
    client.put("/api/settings", json={"language": "xx"})
    client.put("/api/settings", json={"language": "fr"})
    assert len(calls) == 2
