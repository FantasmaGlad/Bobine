"""Identifiants stables dans la configuration : renommage, restauration, suppression opt-in, planning à `id` conservés,
métadonnées des médias, noms plats de la version 5.1."""

import asyncio
import copy
import os
from datetime import datetime, timezone

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest  # noqa: E402

from app import config_files  # noqa: E402
from app.config_apply.context import ConfigErrors  # noqa: E402
from app.config_apply.runner import apply as apply_configuration  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    AudioCourse, Playlist, RadioAnnouncement, RadioAnnouncementRule, RadioPlaylist, RadioTag, RadioTrack, Schedule,
    ScheduleOverride, ScheduleTargetType, ScheduleType, Video,
)
from test_config_apply import _apply, _export, _quiet_effects, single_names  # noqa: E402,F401
from test_config_files import library  # noqa: E402,F401


def _expect_errors(files, *needles):
    with pytest.raises(ConfigErrors) as refused:
        _apply(files)
    text = " ".join(refused.value.errors)
    for needle in needles:
        assert needle in text, text


def test_renaming_a_playlist_keeps_its_identity(single_names):
    with SessionLocal() as db:
        before = db.query(Playlist).one()
        before_id, before_uid = before.id, before.uid
    files = _export()
    files["playlists/video.json"]["playlists"][0]["name"] = "Lundi soir (nouveau nom)"
    result = _apply({"playlists/video.json": files["playlists/video.json"]})
    assert result["changes"]
    with SessionLocal() as db:
        playlist = db.query(Playlist).one()  # une seule : renommée, pas dupliquée
        assert (playlist.id, playlist.uid, playlist.name) == (before_id, before_uid, "Lundi soir (nouveau nom)")
    assert _apply(_export(), dry_run=True)["changes"] == {}


def test_without_prune_missing_playlists_stay_and_with_prune_they_go(single_names):
    files = _export()
    files["playlists/video.json"]["playlists"] = [{"name": "Autre", "videos": []}]
    _apply({"playlists/video.json": files["playlists/video.json"]})
    with SessionLocal() as db:
        assert sorted(p.name for p in db.query(Playlist).all()) == ["Autre", "Lundi soir"]
    files["playlists/video.json"]["prune"] = True
    assert _apply({"playlists/video.json": files["playlists/video.json"]}, dry_run=True)["changes"]
    with SessionLocal() as db:
        assert db.query(Playlist).count() == 2  # essai à blanc : rien supprimé
    _apply({"playlists/video.json": files["playlists/video.json"]})
    with SessionLocal() as db:
        assert [p.name for p in db.query(Playlist).all()] == ["Autre"]
        assert db.query(Schedule).count() == 0  # la programmation qui visait « Lundi soir » disparaît avec elle


def test_prune_must_be_a_boolean(single_names):
    files = _export()
    files["playlists/video.json"]["prune"] = "oui"
    _expect_errors({"playlists/video.json": files["playlists/video.json"]}, "« prune » doit être un booléen")


def test_unknown_uid_creates_the_object_with_that_uid(single_names):
    files = _export()
    files["playlists/video.json"]["playlists"].append({"uid": "pl_0123456789ab", "name": "Importée", "videos": []})
    _apply({"playlists/video.json": files["playlists/video.json"]})
    with SessionLocal() as db:
        assert db.query(Playlist).filter(Playlist.name == "Importée").one().uid == "pl_0123456789ab"


def test_uid_cannot_be_used_twice_in_one_document(single_names):
    files = _export()
    existing = files["playlists/video.json"]["playlists"][0]
    files["playlists/video.json"]["playlists"].append({"uid": existing["uid"], "name": "Copie", "videos": []})
    _expect_errors({"playlists/video.json": files["playlists/video.json"]}, "présent deux fois")


def test_renaming_onto_an_existing_name_is_refused(single_names):
    files = _export()
    files["playlists/video.json"]["playlists"] = [
        {"name": "Autre", "videos": []}, dict(files["playlists/video.json"]["playlists"][0]),
    ]
    _apply({"playlists/video.json": files["playlists/video.json"]})
    files = _export()
    uid_of_autre = next(p["uid"] for p in files["playlists/video.json"]["playlists"] if p["name"] == "Autre")
    files["playlists/video.json"]["playlists"] = [{"uid": uid_of_autre, "name": "Lundi soir", "videos": []}]
    _expect_errors({"playlists/video.json": files["playlists/video.json"]}, "renommage impossible")


def test_schedule_ids_survive_an_apply_with_or_without_uids(single_names):
    with SessionLocal() as db:
        original = db.query(Schedule).one()
        schedule_id, schedule_uid = original.id, original.uid
        override_id = db.query(ScheduleOverride).one().id
    files = _export()
    _apply({"schedule/cable.json": files["schedule/cable.json"]})
    legacy = copy.deepcopy(files["schedule/cable.json"])
    for entry in legacy["schedules"]:
        entry.pop("uid", None)
        entry["target"].pop("uid", None)
        for override in entry["overrides"]:
            override.pop("uid", None)
    legacy["schema"] = 1
    assert _apply({"schedule-cable.json": legacy}, dry_run=True)["changes"] == {}  # nom plat de la 5.1
    _apply({"schedule-cable.json": legacy})
    with SessionLocal() as db:
        kept = db.query(Schedule).one()
        assert (kept.id, kept.uid) == (schedule_id, schedule_uid)
        assert db.query(ScheduleOverride).one().id == override_id


def test_schedule_is_edited_in_place_and_dropped_when_absent(single_names):
    files = _export()
    cable = files["schedule/cable.json"]
    cable["schedules"][0]["recurrence"]["time"] = "07:00"
    cable["schedules"].append(copy.deepcopy({**cable["schedules"][0], "uid": "sch_aaaaaaaaaaaa", "overrides": []}))
    _apply({"schedule/cable.json": cable})
    with SessionLocal() as db:
        assert sorted(s.recurrence_rule for s in db.query(Schedule).all())[0].count("07:00") == 1
        assert db.query(Schedule).filter(Schedule.uid == "sch_aaaaaaaaaaaa").count() == 1
    cable["schedules"] = cable["schedules"][:1]
    _apply({"schedule/cable.json": cable})
    with SessionLocal() as db:
        assert db.query(Schedule).count() == 1


def test_tag_rename_and_prune(single_names):
    files = _export()
    tags = files["radio/tags.json"]
    tags["tags"][0]["name"] = "apaisant"
    tags["assignments"][0]["tags"] = ["apaisant"]
    _apply({"radio/tags.json": tags})
    with SessionLocal() as db:
        assert [t.name for t in db.query(RadioTag).all()] == ["apaisant"]
        assert [t.name for t in db.query(RadioTrack).one().tags] == ["apaisant"]
    tags["tags"] = [{"name": "énergie"}]
    tags["assignments"] = []
    tags["prune"] = True
    _apply({"radio/tags.json": tags})
    with SessionLocal() as db:
        assert [t.name for t in db.query(RadioTag).all()] == ["énergie"]


def test_announcement_description_and_rules_keep_their_uid(single_names):
    files = _export()
    files["library/announcements.json"]["announcements"][0]["description"] = "Hydratez-vous"
    rule_uid = files["radio/announcement-rules.json"]["rules"][0]["uid"]
    _apply({"library/announcements.json": files["library/announcements.json"], "radio/announcement-rules.json": files["radio/announcement-rules.json"]})
    with SessionLocal() as db:
        assert db.query(RadioAnnouncement).one().description == "Hydratez-vous"
        assert db.query(RadioAnnouncementRule).one().uid == rule_uid


def test_library_videos_are_edited_by_uid_even_after_a_title_change(single_names):
    files = _export()
    document = files["library/videos.json"]
    assert document["videos"][0]["file"] == "rpm-110.mp4"
    document["videos"][0].update({"title": "RPM 111", "program": None, "description": " Nouvelle séance "})
    _apply({"library/videos.json": document})
    with SessionLocal() as db:
        video = db.query(Video).one()
        assert (video.title, video.program, video.description) == ("RPM 111", None, "Nouvelle séance")
    # Retrouvé par son seul nom de fichier (document sans uid)
    document["videos"][0].pop("uid")
    document["videos"][0]["title"] = "RPM 112"
    _apply({"library/videos.json": document})
    with SessionLocal() as db:
        assert db.query(Video).one().title == "RPM 112"


def test_library_never_creates_or_deletes_media(single_names):
    files = _export()
    files["library/videos.json"]["videos"] = [{"uid": "vid_ffffffffffff", "title": "Fantôme", "file": "absent.mp4"}]
    files["library/videos.json"]["prune"] = True
    _expect_errors({"library/videos.json": files["library/videos.json"]}, "aucun média n'est créé")
    with SessionLocal() as db:
        assert db.query(Video).count() == 1


@pytest.mark.parametrize("field, value, message", [
    ("title", "  ", "ne peut pas être vide"), ("title", 3, "doit être un texte"), ("release", 5, "doit être un texte"),
])
def test_library_values_are_validated_like_the_interface(single_names, field, value, message):
    files = _export()
    files["library/videos.json"]["videos"][0][field] = value
    _expect_errors({"library/videos.json": files["library/videos.json"]}, message)


def test_library_audio_radio_and_backgrounds(single_names):
    files = _export()
    files["library/audio.json"]["courses"][0].update({"title": "Échauffement 2", "release": "121"})
    files["library/audio.json"]["courses"][0]["tracks"][0]["title"] = "Warm Up 2"
    files["library/radio.json"]["tracks"][0].update({"title": "Aube 2", "year": 2024, "genre": " Chill "})
    files["library/backgrounds.json"]["backgrounds"][0]["title"] = "Lagon 2"
    _apply({k: files[k] for k in ("library/audio.json", "library/radio.json", "library/backgrounds.json")})
    with SessionLocal() as db:
        course = db.query(AudioCourse).one()
        assert (course.title, course.release, course.tracks[0].title) == ("Échauffement 2", "121", "Warm Up 2")
        song = db.query(RadioTrack).one()
        assert (song.title, song.year, song.genre) == ("Aube 2", 2024, "Chill")
    files["library/radio.json"]["tracks"][0]["year"] = -1
    _expect_errors({"library/radio.json": files["library/radio.json"]}, "entier positif")


def test_flat_names_of_version_5_1_and_the_manifest(single_names):
    files = _export()
    manifest = files.pop("manifest.json")
    assert manifest["files"]["playlists/video.json"] == 1 and manifest["instance"]
    legacy = {"playlists-video.json": files["playlists/video.json"], "manifest.json": manifest}
    assert _apply(legacy, dry_run=True)["changes"] == {}
    _expect_errors({"playlists-video.json": files["playlists/video.json"], "playlists/video.json": files["playlists/video.json"]}, "fourni deux fois")
    _expect_errors({"playlists/unknown.json": {}}, "fichier inconnu")


def test_documents_of_schema_1_are_still_accepted(single_names):
    files = _export()
    document = copy.deepcopy(files["settings.json"])
    document["schema"] = 1
    assert _apply({"settings.json": document}, dry_run=True)["changes"] == {}
    document["schema"] = 3
    _expect_errors({"settings.json": document}, "« schema » doit valoir 1 ou 2")


def test_export_apply_export_is_identical_with_all_files(single_names):
    first = _export()
    _apply(first)
    assert _export() == first


# --- liens vers les fichiers de chapitres et de sous-titres ------------------------------------------------------------

@pytest.fixture(autouse=True)
def _no_leftover_links():
    from app.models import VideoChapter, VideoSubtitle

    def clean():
        with SessionLocal() as db:
            db.query(VideoSubtitle).delete()
            db.query(VideoChapter).delete()
            db.commit()

    clean()
    yield
    clean()


@pytest.fixture()
def data_dirs(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "subtitles_dir", str(tmp_path / "subtitles"))
    return tmp_path


def _video_entry():
    with SessionLocal() as db:
        return config_files.build_library_videos(db)["videos"][0]


def test_library_links_chapters_and_subtitles_when_none_exist(single_names):
    entry = _video_entry()
    assert entry["chapters"] is False and entry["chapters_file"] is None and entry["chapters_source"] is None
    assert entry["subtitles"] is False and entry["subtitle_files"] == []


def test_imported_chapter_file_is_linked_with_its_path(single_names, data_dirs):
    from pathlib import Path

    from fastapi.testclient import TestClient

    from app.main import app

    with SessionLocal() as db:
        video_id = db.query(Video).one().id
    client = TestClient(app)
    answer = client.post(f"/api/videos/{video_id}/chapters/import", files={"file": ("chapitres cours.txt", "00:00 Intro\n05:00 Corps\n".encode())})
    assert answer.status_code == 200, answer.text
    entry = _video_entry()
    assert entry["chapters"] is True and entry["chapters_source"] == "file"
    linked = Path(entry["chapters_file"]["path"])
    assert linked.exists() and linked.read_text(encoding="utf-8").startswith("00:00 Intro")
    assert entry["chapters_file"]["file"] == linked.name and linked.name.endswith("chapitres_cours.txt")
    # Une modification à la main : les chapitres ne viennent plus du fichier, sa copie disparaît.
    client.put(f"/api/videos/{video_id}/chapters", json={"chapters": [{"start_seconds": 0, "title": "Seul"}]})
    entry = _video_entry()
    assert entry["chapters"] is True and entry["chapters_source"] == "manual" and entry["chapters_file"] is None
    assert not linked.exists()
    # Tout retirer : `chapters` redevient faux.
    client.put(f"/api/videos/{video_id}/chapters", json={"chapters": []})
    assert _video_entry()["chapters"] is False


def test_deleting_a_video_removes_the_chapter_copy(single_names, data_dirs):
    from pathlib import Path

    from fastapi.testclient import TestClient

    from app.main import app

    with SessionLocal() as db:
        video_id = db.query(Video).one().id
    client = TestClient(app)
    client.post(f"/api/videos/{video_id}/chapters/import", files={"file": ("c.txt", b"00:00 A\n01:00 B\n")})
    path = Path(_video_entry()["chapters_file"]["path"])
    assert path.exists()
    assert client.delete(f"/api/videos/{video_id}").status_code == 200
    assert not path.exists()


def test_subtitle_files_are_linked(single_names, data_dirs):
    from pathlib import Path

    from fastapi.testclient import TestClient

    from app.main import app

    with SessionLocal() as db:
        video_id = db.query(Video).one().id
    client = TestClient(app)
    vtt = b"WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nBonjour\n"
    answer = client.post(f"/api/videos/{video_id}/subtitles", files={"file": ("cours.fr.vtt", vtt)}, data={"language_code": "fr", "language_label": "Français"})
    assert answer.status_code == 200, answer.text
    entry = _video_entry()
    assert entry["subtitles"] is True and len(entry["subtitle_files"]) == 1
    sub = entry["subtitle_files"][0]
    assert sub["language"] == "fr" and sub["format"] and Path(sub["path"]).exists() and sub["file"] == Path(sub["path"]).name


def test_links_are_informational_and_never_applied_nor_in_the_diff(single_names, data_dirs):
    files = _export()
    document = files["library/videos.json"]
    document["videos"][0]["chapters"] = True
    document["videos"][0]["chapters_file"] = {"file": "x.txt", "path": "/etc/passwd"}
    document["videos"][0]["subtitle_files"] = [{"language": "fr", "file": "y.vtt", "path": "/etc/shadow"}]
    result = _apply({"library/videos.json": document})
    assert result["changes"] == {}
    entry = _video_entry()
    assert entry["chapters"] is False and entry["chapters_file"] is None and entry["subtitle_files"] == []


def test_deleting_a_video_used_by_a_playlist_and_a_schedule_works(data_dirs, tmp_path, single_names):
    """Régression : la ligne de playlist orpheline faisait échouer la suppression, après l'effacement des fichiers."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.models import PlaylistItem

    media = tmp_path / "rpm.mp4"
    media.write_bytes(b"x")
    with SessionLocal() as db:
        video = db.query(Video).one()
        video.file_path = str(media)
        video_id = video.id
        db.add(Schedule(target_type=ScheduleTargetType.video, target_id=video_id, schedule_type=ScheduleType.once,
                        run_at=datetime(2031, 1, 1, tzinfo=timezone.utc), channel="cable"))
        db.commit()
        assert db.query(PlaylistItem).count() == 1
    assert TestClient(app).delete(f"/api/videos/{video_id}").status_code == 200
    assert not media.exists()
    with SessionLocal() as db:
        assert db.query(Video).count() == 0 and db.query(PlaylistItem).count() == 0
        assert db.query(Schedule).filter(Schedule.target_type == ScheduleTargetType.video).count() == 0
        assert db.query(Playlist).count() == 1  # la playlist reste, seulement sans cette vidéo
