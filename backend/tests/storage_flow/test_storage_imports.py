import hashlib
import os
import shutil
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.devices.base import DeviceError  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    AudioCourse,
    AudioTrack,
    ExternalVolume,
    ImportSource,
    RadioTrack,
    Setting,
    StorageImport,
    Video,
)
from app.storage import availability  # noqa: E402
from app.storage.service import StorageService  # noqa: E402
from storage_fakes import FakeStorageDriver  # noqa: E402
from storage_flow_support import needs_ffmpeg, _sha, _purge_local, vol_view, wait_job, codes, _register  # noqa: E402


@needs_ffmpeg
def test_import_copies_verifies_and_never_touches_the_source(env, media):
    vol = env.driver.plug("sda", "AAAA-0007", {"Cours/Rpm 101 test.mp4": media.video.read_bytes()})
    env.refresh()
    env.client.post(f"/api/storage/volumes/{vol.key}/mount", json={})
    source = env.driver.disk_dir(vol.key) / "Cours" / "Rpm 101 test.mp4"
    before = _sha(source), source.stat().st_mtime_ns
    response = env.client.post(f"/api/storage/volumes/{vol.key}/import", json={"entries": [{"path": "Cours"}], "kind": "video"})
    assert response.status_code == 202 and response.json()["files"] == 1
    job = wait_job(env.client, response.json()["job_id"])
    assert job["stage"] == "done" and job["result_id"] and job["source"] == "storage"
    assert job["bytes_total"] == job["bytes_done"] == media.video.stat().st_size and job["files_done"] == 1
    assert job["details"]["imported"] == 1 and job["details"]["failed"] == []
    assert source.exists() and (_sha(source), source.stat().st_mtime_ns) == before
    with SessionLocal() as db:
        video = db.query(Video).filter(Video.id == job["result_id"]).first()
        assert video.storage_id is None and video.rel_path is None and video.duration_seconds
        assert Path(video.file_path).exists() and str(env.tmp) not in video.file_path
        local = Path(video.file_path)
        assert local.stat().st_size > 0
    again = env.client.post(f"/api/storage/volumes/{vol.key}/import", json={"entries": [{"path": "Cours"}], "kind": "video"}).json()
    assert again["job_id"] is None and again["skipped"][0]["reason"] == "already_imported"
    forced = env.client.post(f"/api/storage/volumes/{vol.key}/import", json={"entries": [{"path": "Cours"}], "kind": "video", "force": True}).json()
    assert wait_job(env.client, forced["job_id"])["stage"] == "done"
    _purge_local(Video, Video.title.like("Rpm 101%"))
    with SessionLocal() as db:
        assert db.query(StorageImport).count() >= 1


@needs_ffmpeg
def test_import_audio_course_and_radio(env, media):
    files = {"Cours stk/01 - Intro.mp3": media.audio.read_bytes(), "Cours stk/02 - Suite.mp3": media.audio.read_bytes(), "Radio/Titre stk.mp3": media.audio.read_bytes()}
    vol = env.driver.plug("sda", "AAAA-0008", files)
    env.refresh()
    env.client.post(f"/api/storage/volumes/{vol.key}/mount", json={})
    course = env.client.post(f"/api/storage/volumes/{vol.key}/import", json={"entries": [{"path": "Cours stk"}], "kind": "audio_course"}).json()
    job = wait_job(env.client, course["job_id"])
    assert job["stage"] == "done" and job["kind"] == "audio"
    with SessionLocal() as db:
        found = db.query(AudioCourse).filter(AudioCourse.id == job["result_id"]).first()
        assert found.title == "Cours stk" and [t.number for t in found.tracks] == [1, 2] and all(t.storage_id is None for t in found.tracks)
    radio = env.client.post(f"/api/storage/volumes/{vol.key}/import", json={"entries": [{"path": "Radio"}], "kind": "radio"}).json()
    assert wait_job(env.client, radio["job_id"])["stage"] == "done"
    for path in (Path(p) for p in files):
        assert (env.driver.disk_dir(vol.key) / path).exists()
    _purge_local(RadioTrack, RadioTrack.title.like("%stk%"))
    with SessionLocal() as db:
        for track in db.query(AudioTrack).filter(AudioTrack.audio_course_id == job["result_id"]).all():
            Path(track.file_path).unlink(missing_ok=True)
        db.query(AudioCourse).filter(AudioCourse.id == job["result_id"]).delete()
        db.commit()


def test_import_refuses_when_local_disk_is_too_small(env, monkeypatch):
    vol = env.driver.plug("sda", "AAAA-0009", {"a.mp4": b"x" * 1000})
    env.refresh()
    env.client.post(f"/api/storage/volumes/{vol.key}/mount", json={})
    monkeypatch.setattr("app.storage.verified_copy.free_bytes", lambda directory=None: 10)
    response = env.client.post(f"/api/storage/volumes/{vol.key}/import", json={"entries": [{"path": "a.mp4"}], "kind": "video"})
    assert response.status_code == 409 and codes(response) == "insufficient_space"
    assert response.json()["detail"]["needed_bytes"] > response.json()["detail"]["free_bytes"]


def test_import_validates_selection_and_kind(env):
    vol = env.driver.plug("sda", "AAAA-0010", {"a.txt": b"x"})
    env.refresh()
    env.client.post(f"/api/storage/volumes/{vol.key}/mount", json={})
    path = f"/api/storage/volumes/{vol.key}/import"
    assert codes(env.client.post(path, json={"entries": [], "kind": "video"})) == "empty_selection"
    assert codes(env.client.post(path, json={"entries": [{"path": "a.txt"}], "kind": "bogus"})) == "bad_kind"
    assert env.client.post(path, json={"entries": [{"path": "../../etc/passwd"}], "kind": "video"}).status_code == 400
    nothing = env.client.post(path, json={"entries": [{"path": "a.txt"}], "kind": "video"}).json()
    assert nothing["job_id"] is None and nothing["skipped"][0]["reason"] == "no_media"


@needs_ffmpeg
def test_radio_indexing_skips_formats_that_need_transcoding(env, media):
    vol = env.driver.plug("sda", "BBBB-0003", {"Radio/Bon.mp3": media.audio.read_bytes(), "Radio/Ancien.wma": b"fake wma"})
    env.refresh()
    _register(env, vol.key)
    started = env.client.post(f"/api/storage/volumes/{vol.key}/index", json={"entries": [{"path": "Radio"}], "kind": "radio"}).json()
    job = wait_job(env.client, started["job_id"])
    assert job["details"]["indexed"] == 1 and {"path": "Radio/Ancien.wma", "reason": "format_requires_import"} in job["details"]["skipped"]
    with SessionLocal() as db:
        track = db.query(RadioTrack).filter(RadioTrack.storage_id.isnot(None)).one()
        assert track.rel_path == "Radio/Bon.mp3" and track.available
    tracks = env.client.get("/api/radio/tracks").json()
    assert any(t["external"] and t["available"] for t in tracks)
    env.driver.unplug(vol.key)
    env.refresh()
    assert any(t["external"] and not t["available"] for t in env.client.get("/api/radio/tracks").json())


def test_volume_without_uuid_imports_but_is_not_registrable(env):
    vol = env.driver.plug("sda", None, {"a.mp4": b"x"})
    env.refresh()
    view = vol_view(env, vol.key)
    assert view["can_register"] is False and view["register_block"] == "uuid_missing" and view["uuid_known"] is False
    assert codes(env.client.post(f"/api/storage/volumes/{vol.key}/library", json={})) == "uuid_missing"
