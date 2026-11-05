"""Application des fichiers de configuration : essai à blanc sans écriture, aller-retour export → application sans
écart, tout ou rien (une erreur dans un fichier refuse l'ensemble et les liste toutes), références par nom, planning
remplacé par canal et resynchronisé, `machine.json` seulement sur demande."""

import asyncio
import copy
import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import config_apply, config_files  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Playlist, RadioAnnouncement, Schedule, Setting  # noqa: E402
from test_config_files import library  # noqa: E402,F401


@pytest.fixture()
def single_names(library):  # noqa: F811
    with SessionLocal() as db:
        twins = db.query(Playlist).filter(Playlist.name == "Lundi soir").order_by(Playlist.id).all()
        db.delete(twins[-1])
        db.commit()


@pytest.fixture(autouse=True)
def _quiet_effects(monkeypatch):
    synced = []
    monkeypatch.setattr("app.scheduler_manager.sync_schedule_job", lambda schedule: synced.append(schedule.channel))
    monkeypatch.setattr("app.scheduler_manager.remove_schedule_job", lambda schedule_id: None)
    monkeypatch.setattr(config_files, "schedule_mirror", lambda: None)
    return synced


def _export():
    with SessionLocal() as db:
        files = config_files.export_all(db)
    files.pop("machine.json")
    return files


def _apply(files, dry_run=False, include_machine=False):
    with SessionLocal() as db:
        return asyncio.run(config_apply.apply(db, files, dry_run=dry_run, include_machine=include_machine))


def test_round_trip_has_no_difference(single_names):
    result = _apply(_export(), dry_run=True)
    assert result["changes"] == {}
    assert _apply(_export())["applied"] is True
    assert _export() == _export()


def test_dry_run_reports_the_difference_and_writes_nothing(single_names):
    files = _export()
    files["settings.json"]["settings"]["theme"] = "menthe"
    result = _apply({"settings.json": files["settings.json"]}, dry_run=True)
    assert result["applied"] is False
    assert any('"theme": "menthe"' in line for line in result["changes"]["settings.json"])
    with SessionLocal() as db:
        assert db.query(Setting).filter(Setting.key == "theme", Setting.value == "menthe").first() is None


def test_playlists_are_created_and_referenced_by_name(single_names, _quiet_effects):
    files = _export()
    files["playlists-video.json"]["playlists"].append({"name": "Mardi", "videos": [{"title": "RPM 110", "file": "rpm-110.mp4"}]})
    files["schedule-network.json"]["schedules"] = [{
        "target": {"type": "playlist", "name": "Mardi"}, "type": "recurring", "active": True,
        "recurrence": {"days_of_week": [1], "time": "19:00"},
    }]
    _apply({name: files[name] for name in ("playlists-video.json", "schedule-network.json")})
    with SessionLocal() as db:
        mardi = db.query(Playlist).filter(Playlist.name == "Mardi").one()
        assert [item.video.title for item in mardi.items] == ["RPM 110"]
        schedule = db.query(Schedule).filter(Schedule.channel == "network").one()
        assert schedule.target_id == mardi.id
    assert _quiet_effects == ["network"]


def test_all_or_nothing_with_every_error_listed(single_names):
    files = _export()
    files["playlists-video.json"]["playlists"].append({"name": "Nouvelle", "videos": []})
    files["settings.json"]["settings"]["theme"] = "pas-un-theme"
    files["announcements.json"]["announcements"] = [{"description": "Inconnue", "enabled": False}]
    files["schedule-cable.json"]["schedules"][0]["recurrence"]["time"] = "25:00"
    with pytest.raises(config_apply.ConfigErrors) as refused:
        _apply(files)
    joined = " | ".join(refused.value.errors)
    for expected in ("settings.json", "announcements.json", "schedule-cable.json"):
        assert expected in joined
    with SessionLocal() as db:
        assert db.query(Playlist).filter(Playlist.name == "Nouvelle").first() is None


def test_ambiguous_names_are_refused(library):  # noqa: F811
    with pytest.raises(config_apply.ConfigErrors) as refused:
        _apply({"schedule-cable.json": _export()["schedule-cable.json"]})
    assert "plusieurs playlists « Lundi soir »" in " ".join(refused.value.errors)


def test_announcements_toggle_and_machine_file_needs_consent(single_names):
    files = _export()
    files["announcements.json"]["announcements"][0]["enabled"] = False
    with SessionLocal() as db:
        machine = config_files.build_machine(db)
    result = _apply({"announcements.json": files["announcements.json"], "machine.json": machine})
    assert result["skipped"] == ["machine.json"]
    with SessionLocal() as db:
        assert db.query(RadioAnnouncement).one().enabled is False


def test_api_refusal_lists_errors(single_names):
    client = TestClient(app)
    bad = copy.deepcopy(_export()["settings.json"])
    bad["kind"] = "autre"
    answer = client.post("/api/config/apply", json={"files": {"settings.json": bad, "inconnu.json": {}}})
    assert answer.status_code == 422
    assert answer.json()["detail"]["errors"] == ["fichier inconnu : inconnu.json"]
    answer = client.post("/api/config/apply", json={"files": {"settings.json": bad}})
    assert answer.status_code == 422 and "« kind »" in answer.json()["detail"]["errors"][0]
    preview = client.post("/api/config/apply", json={"files": {"settings.json": _export()["settings.json"]}})
    assert preview.status_code == 200 and preview.json()["applied"] is False


def test_default_ambiance_can_name_a_playlist_created_in_the_same_batch(single_names):
    files = _export()
    files["playlists-radio.json"]["playlists"].append({"name": "Mardi", "default": False, "tracks": []})
    files["radio-outputs.json"]["outputs"]["radio_cable"]["default_playlist"] = "Mardi"
    assert _apply({name: files[name] for name in ("radio-outputs.json", "playlists-radio.json")})["applied"]


@pytest.mark.parametrize("name, mutate, message", [
    ("announcements.json", lambda d: d.update(announcements=["bouteille"]), "document invalide"),
    ("playlists-video.json", lambda d: d["playlists"][0].update(video=d["playlists"][0].pop("videos")), "« videos » doit être une liste"),
    ("settings.json", lambda d: d["settings"].update(volume_defaut=42), "réglage inconnu : volume_defaut"),
    ("announcements.json", lambda d: d["announcements"][0].update(enabled="false"), "doit être un booléen"),
])
def test_malformed_documents_are_refused_not_crashing(single_names, name, mutate, message):
    document = _export()[name]
    mutate(document)
    client = TestClient(app)
    answer = client.post("/api/config/apply?dry_run=false", json={"files": {name: document}})
    assert answer.status_code == 422
    assert message in " ".join(answer.json()["detail"]["errors"])
    with SessionLocal() as db:
        assert db.query(Playlist).filter(Playlist.name == "Lundi soir").one().items


def test_start_only_radio_settings_come_back_in_the_export(single_names):
    files = _export()
    wanted = files["settings.json"]["settings"]["radio"]["crossfade_seconds"] + 1
    files["settings.json"]["settings"]["radio"]["crossfade_seconds"] = wanted
    result = _apply({"settings.json": files["settings.json"]})
    assert result["restart_required"] == ["radio.crossfade_seconds"]
    assert _export()["settings.json"]["settings"]["radio"]["crossfade_seconds"] == wanted
    assert _apply({"settings.json": _export()["settings.json"]}, dry_run=True)["changes"] == {}
