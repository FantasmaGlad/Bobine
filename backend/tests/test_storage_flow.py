"""Stockage externe : API protégée, montage/retrait, explorateur sûr, import vérifié, bibliothèque externe,
disponibilité (arrachage, rebranchement à un autre point de montage), garde-fous, longévité.

Aucun matériel ni root : un pilote factice simule les supports (voir storage_fakes.py). Le test réel sur image
disque (udisks2) est un script séparé (scripts/storage-real-test.sh)."""

import hashlib
import os
import shutil
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

# Base de test isolée AVANT tout import de l'application (comme les autres tests).
os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")
os.environ.setdefault("BOBINE_MEDIA_DIR", "data/test_videos")
os.environ.setdefault("BOBINE_WATCH_DIR", "data/test_watched")
os.environ.setdefault("BOBINE_THUMBNAILS_DIR", "data/test_thumbnails")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402
from app.devices import security  # noqa: E402
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

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
needs_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg indisponible")
KEYS = (security.SETTING_ENABLED, security.SETTING_PIN_HASH, "storage_defaults")


def _sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def media(tmp_path_factory):
    """Une vidéo H.264/AAC et un MP3 minuscules (générés une fois)."""
    folder = tmp_path_factory.mktemp("media")
    video, audio = folder / "Rpm 101 test.mp4", folder / "piste.mp3"
    if HAS_FFMPEG:
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=30", "-f", "lavfi", "-i", "sine=frequency=1000:duration=1",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(video)], capture_output=True, check=True)
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=800:duration=1", "-c:a", "libmp3lame", str(audio)], capture_output=True, check=True)
    return SimpleNamespace(video=video, audio=audio)


def _cleanup_db():
    with SessionLocal() as db:
        db.query(Setting).filter(Setting.key.in_(KEYS)).delete(synchronize_session=False)
        for model in (Video, AudioTrack, RadioTrack):
            for row in db.query(model).filter(model.storage_id.isnot(None)).all():
                db.delete(row)
        db.query(Video).filter(Video.title.like("__stk_%")).delete(synchronize_session=False)
        db.query(AudioCourse).filter(AudioCourse.title.like("%stk%")).delete(synchronize_session=False)
        db.query(StorageImport).delete()
        db.query(ExternalVolume).delete()
        db.commit()
    availability.set_online({})


def _purge_local(model, condition) -> None:
    """Supprime les lignes ET les fichiers locaux créés par un import de test (les tests ne laissent rien dans data/)."""
    with SessionLocal() as db:
        for row in db.query(model).filter(condition).all():
            for attr in ("file_path", "thumbnail_path", "cover_path"):
                path = getattr(row, attr, None)
                if path and getattr(row, "storage_id", None) is None:
                    Path(path).unlink(missing_ok=True)
            if hasattr(row, "tags"):
                row.tags = []
            db.delete(row)
        db.commit()


def _enable(pin: str | None = None) -> None:
    with SessionLocal() as db:
        db.add(Setting(key=security.SETTING_ENABLED, value="true"))
        if pin:
            db.add(Setting(key=security.SETTING_PIN_HASH, value=security.hash_pin(pin)))
        db.commit()


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Application complète (cycle de vie compris) avec un service de stockage neuf et un pilote factice ; écran local."""
    init_db()
    _cleanup_db()
    driver = FakeStorageDriver(tmp_path / "fake")
    service = StorageService(lambda: driver)
    monkeypatch.setattr("app.main.storage_service", service)
    monkeypatch.setattr("app.routers.storage.service", service)
    monkeypatch.setattr("app.routers.devices.is_local_request", lambda request: True)
    _enable()
    with TestClient(app) as client:
        ns = SimpleNamespace(client=client, driver=driver, service=service, tmp=tmp_path)
        ns.refresh = lambda: client.portal.call(service.refresh)
        yield ns
    _cleanup_db()


def get_volumes(env):
    return env.client.get("/api/storage/volumes").json()


def vol_view(env, key):
    return next(v for v in get_volumes(env)["volumes"] if v["key"] == key)


def wait_job(client, job_id, timeout=90):
    deadline = time.time() + timeout
    job = None
    while time.time() < deadline:
        jobs = client.get("/api/import-jobs").json()
        job = next((j for j in jobs if j["id"] == job_id), None)
        if job and job["stage"] in ("done", "error", "cancelled"):
            return job
        time.sleep(0.2)
    raise AssertionError(f"tâche {job_id} non terminée : {job}")


def codes(response):
    return response.json()["detail"]["code"]


# ---------------------------------------------------------------------------------------------------------
# Contrôle d'accès : identique aux périphériques
# ---------------------------------------------------------------------------------------------------------

@pytest.fixture()
def gate(tmp_path, monkeypatch):
    init_db()
    _cleanup_db()
    driver = FakeStorageDriver(tmp_path / "fake")
    service = StorageService(lambda: driver)
    monkeypatch.setattr("app.routers.storage.service", service)
    yield SimpleNamespace(service=service, driver=driver)
    _cleanup_db()


def remote(host="203.0.113.9"):
    return TestClient(app, client=(host, 50000))


def test_disabled_by_default_blocks_the_whole_api(gate):
    for method, path in (("get", "/api/storage/status"), ("get", "/api/storage/volumes"), ("get", "/api/storage/volumes/u-x/browse"),
                         ("post", "/api/storage/volumes/u-x/mount"), ("get", "/api/storage/advisor/format"), ("get", "/api/storage/portable")):
        response = getattr(remote(), method)(path, **({"json": {}} if method == "post" else {}))
        assert response.status_code == 403 and codes(response) == "devices_disabled", path


def test_remote_needs_pin_then_cookie_scoped_to_storage(gate):
    _enable("123456")
    client = remote()
    assert codes(client.get("/api/storage/volumes")) == "pin_required" and client.get("/api/storage/volumes").status_code == 401
    assert client.post("/api/devices/session", json={"pin": "000000"}).status_code == 401
    ok = client.post("/api/devices/session", json={"pin": "123456"})
    cookies = ok.headers.get_list("set-cookie")
    assert any("bobine_storage_session" in c and "Path=/api/storage" in c and "HttpOnly" in c and "SameSite=strict" in c for c in cookies)
    assert any("bobine_devices_session" in c and "Path=/api/devices" in c for c in cookies)
    assert client.get("/api/storage/volumes").status_code == 200
    # Une autre adresse ne peut pas réutiliser la session (liée à l'IP).
    stolen = remote("203.0.113.77")
    stolen.cookies.set("bobine_storage_session", client.cookies.get("bobine_storage_session", path="/api/storage"), path="/api/storage")
    assert stolen.get("/api/storage/volumes").status_code == 401
    client.delete("/api/devices/session")
    assert client.get("/api/storage/volumes").status_code == 401


def test_remote_without_pin_is_refused_with_explanation(gate):
    _enable()
    response = remote().get("/api/storage/volumes")
    assert response.status_code == 403 and codes(response) == "pin_not_set"


# ---------------------------------------------------------------------------------------------------------
# Détection, montage, retrait
# ---------------------------------------------------------------------------------------------------------

def test_hot_plug_listing_never_exposes_paths(env):
    assert get_volumes(env)["volumes"] == []
    vol = env.driver.plug("sda", "7FDB-F2EC", {"Cours/a.mp4": b"x"}, label="COURS")
    env.refresh()
    listing = get_volumes(env)
    assert [v["key"] for v in listing["volumes"]] == [vol.key]
    view = listing["volumes"][0]
    assert view["state"] == "present" and view["mounted"] is False and view["connected"] and view["fstype"] == "exfat"
    assert view["assessment"]["verdict"] in ("acceptable", "recommended") and view["library"]["registered"] is False
    assert view["can_register"] is True
    dumped = str(listing)
    assert "/dev/" not in dumped and str(env.tmp) not in dumped


def test_mount_defaults_to_read_only_with_wear_friendly_options(env):
    vol = env.driver.plug("sda", "AAAA-0001")
    env.refresh()
    response = env.client.post(f"/api/storage/volumes/{vol.key}/mount", json={})
    assert response.status_code == 200 and response.json()["mode"] == "ro"
    key, options = env.driver.mount_calls[-1]
    assert options == ["ro", "noatime", "nodiratime", "noexec"]
    assert not set(options) & {"sync", "discard", "dirsync"}
    view = vol_view(env, vol.key)
    assert view["mounted"] and view["mounted_read_only"] is True and view["state"] == "mounted"
    longevity = {i["id"]: i for i in view["longevity"]}
    assert longevity["read_only"]["status"] == "applied" and longevity["noatime"]["status"] == "applied"
    assert longevity["smart"]["status"] in ("applied", "unavailable")
    # Remonter dans le même mode ne fait rien.
    assert env.client.post(f"/api/storage/volumes/{vol.key}/mount", json={}).json()["changed"] is False


def test_rw_mount_is_explicit_and_refused_on_dirty_filesystem(env):
    vol = env.driver.plug("sda", "AAAA-0002", fstype="ntfs")
    env.refresh()
    env.driver.fail_mount = DeviceError("dirty", "Le système de fichiers semble endommagé", 409)
    refused = env.client.post(f"/api/storage/volumes/{vol.key}/mount", json={"mode": "ro"})
    assert refused.status_code == 409 and codes(refused) == "dirty"
    view = vol_view(env, vol.key)
    assert view["assessment"]["write_allowed"] is False and view["assessment"]["reason"] == "dirty"
    env.driver.fail_mount = None
    assert codes(env.client.post(f"/api/storage/volumes/{vol.key}/mount", json={"mode": "rw"})) == "write_refused"
    assert env.client.post(f"/api/storage/volumes/{vol.key}/mount", json={"mode": "bogus"}).status_code == 400


def test_unknown_and_malformed_keys(env):
    assert env.client.post("/api/storage/volumes/u-inconnu/mount", json={}).status_code == 404
    assert codes(env.client.get("/api/storage/volumes/u-inconnu/browse")) == "volume_not_found"
    # Un chemin de périphérique ou une injection n'est jamais une clé valable : 404, jamais une action.
    for hostile in ("%2Fdev%2Fsda1", "..%2Fetc", "sda1%3B%20rm%20-rf%20%2F", "x" * 200):
        response = env.client.post(f"/api/storage/volumes/{hostile}/eject")
        assert response.status_code == 404, hostile
    assert env.driver.unmount_calls == [] and env.driver.power_off_calls == []


def test_clean_eject_vs_abrupt_removal(env):
    clean = env.driver.plug("sda", "AAAA-0003")
    env.refresh()
    env.client.post(f"/api/storage/volumes/{clean.key}/mount", json={})
    response = env.client.post(f"/api/storage/volumes/{clean.key}/eject")
    assert response.status_code == 200 and response.json() == {"ejected": True, "powered_off": True}
    assert env.driver.power_off_calls == [clean.key] and env.driver.unmount_calls == [clean.key]
    assert get_volumes(env)["recent_removals"] == [] or all(not r["abrupt"] for r in get_volumes(env)["recent_removals"])

    brutal = env.driver.plug("sdb", "AAAA-0004", label="ARRACHEE")
    env.refresh()
    env.client.post(f"/api/storage/volumes/{brutal.key}/mount", json={})
    env.driver.unplug(brutal.key)
    env.refresh()
    removed = get_volumes(env)["recent_removals"]
    assert [r["name"] for r in removed if r["abrupt"]] == ["ARRACHEE"]


def test_busy_volume_refuses_unmount_and_eject(env):
    vol = env.driver.plug("sda", "AAAA-0005")
    env.refresh()
    env.client.post(f"/api/storage/volumes/{vol.key}/mount", json={})
    env.service._busy[vol.key] = {"job-x"}
    assert vol_view(env, vol.key)["state"] == "busy"
    assert codes(env.client.post(f"/api/storage/volumes/{vol.key}/unmount")) == "busy"
    assert codes(env.client.post(f"/api/storage/volumes/{vol.key}/eject")) == "busy"
    assert env.driver.unmount_calls == []
    env.service._busy.clear()
    assert env.client.post(f"/api/storage/volumes/{vol.key}/unmount").status_code == 200


# ---------------------------------------------------------------------------------------------------------
# Explorateur
# ---------------------------------------------------------------------------------------------------------

def test_browse_requires_mount_and_blocks_traversal(env):
    vol = env.driver.plug("sda", "AAAA-0006", {"Cours/RPM/101.mp4": b"v", "Cours/notes.txt": b"n", "Musique/a.mp3": b"a", ".cache/x": b"1"})
    secret = env.tmp / "secret"
    secret.mkdir()
    (secret / "pwd.mp4").write_bytes(b"s")
    os.symlink(secret, env.driver.disk_dir(vol.key) / "Cours" / "evasion")
    env.refresh()
    base = f"/api/storage/volumes/{vol.key}/browse"
    assert codes(env.client.get(base)) == "not_mounted"
    env.client.post(f"/api/storage/volumes/{vol.key}/mount", json={})
    root = env.client.get(base).json()
    assert [e["name"] for e in root["entries"]] == ["Cours", "Musique"] and root["total"] == 2 and root["path"] == ""
    cours = env.client.get(base, params={"path": "Cours"}).json()
    names = [e["name"] for e in cours["entries"]]
    assert names == ["RPM", "notes.txt"] and cours["skipped_links"] == 1 and cours["parent"] == ""  # lien hors volume ignoré
    for bad in ("../..", "../../etc", "/etc", "Cours/../../..", "C:/Windows", "Cours\\..\\x", "Cours/evasion/pwd.mp4"):
        response = env.client.get(base, params={"path": bad})
        assert response.status_code in (400, 403, 404) and "code" in response.json()["detail"], bad
    assert codes(env.client.get(base, params={"path": "Cours/evasion"})) == "outside_volume"
    assert codes(env.client.get(base, params={"path": "n/existe/pas"})) == "not_found"
    paged = env.client.get(base, params={"path": "Cours", "limit": 1, "offset": 1}).json()
    assert len(paged["entries"]) == 1 and paged["total"] == 2
    assert env.client.get(base, params={"limit": 5000}).status_code == 422
    assert env.client.get(base, params={"path": "Cours", "media_only": True}).json()["total"] == 1
    # Les évènements et réponses ne contiennent jamais le point de montage.
    assert str(env.tmp) not in str(root) + str(cours)


# ---------------------------------------------------------------------------------------------------------
# Import : copie vérifiée, source intacte, relance idempotente
# ---------------------------------------------------------------------------------------------------------

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
    assert source.exists() and (_sha(source), source.stat().st_mtime_ns) == before  # jamais modifiée ni supprimée
    with SessionLocal() as db:
        video = db.query(Video).filter(Video.id == job["result_id"]).first()
        assert video.storage_id is None and video.rel_path is None and video.duration_seconds
        assert Path(video.file_path).exists() and str(env.tmp) not in video.file_path
        local = Path(video.file_path)
        assert local.stat().st_size > 0  # (l'intégrité octet à octet de la copie est vérifiée dans test_storage_transfer.py)
    again = env.client.post(f"/api/storage/volumes/{vol.key}/import", json={"entries": [{"path": "Cours"}], "kind": "video"}).json()
    assert again["job_id"] is None and again["skipped"][0]["reason"] == "already_imported"  # relance idempotente
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
            db.delete(track)
        db.query(AudioCourse).filter(AudioCourse.id == job["result_id"]).delete()
        db.commit()


def test_import_refuses_when_local_disk_is_too_small(env, monkeypatch):
    vol = env.driver.plug("sda", "AAAA-0009", {"a.mp4": b"x" * 1000})
    env.refresh()
    env.client.post(f"/api/storage/volumes/{vol.key}/mount", json={})
    monkeypatch.setattr("app.storage.transfer.free_bytes", lambda directory=None: 10)
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


# ---------------------------------------------------------------------------------------------------------
# Bibliothèque externe : indexation, lecture directe, disponibilité, remappage
# ---------------------------------------------------------------------------------------------------------

def _register(env, key):
    response = env.client.post(f"/api/storage/volumes/{key}/library", json={"nickname": "Clé du club"})
    assert response.status_code == 200, response.text
    return response.json()


@needs_ffmpeg
def test_library_lifecycle_unplug_replug_other_mount_point(env, media):
    vol = env.driver.plug("sda", "BBBB-0001", {"Cours/Rpm 101 test.mp4": media.video.read_bytes()}, label="CLUB", mounted_rw=True)
    env.refresh()
    assert vol_view(env, vol.key)["mounted_read_only"] is False  # le bureau a monté en lecture-écriture
    assert codes(env.client.post(f"/api/storage/volumes/{vol.key}/index", json={"entries": [{"path": "Cours"}], "kind": "video"})) == "not_registered"
    _register(env, vol.key)
    # L'enregistrement a remonté le support en lecture seule (zéro écriture).
    assert env.driver.mount_calls[-1][1][0] == "ro" and vol_view(env, vol.key)["mounted_read_only"] is True
    first_mount = env.driver.volumes[vol.key].mountpoint

    started = env.client.post(f"/api/storage/volumes/{vol.key}/index", json={"entries": [{"path": "Cours"}], "kind": "video"}).json()
    job = wait_job(env.client, started["job_id"])
    assert job["stage"] == "done" and job["details"]["indexed"] == 1
    video_id = job["result_id"]
    with SessionLocal() as db:
        video = db.query(Video).filter(Video.id == video_id).first()
        lib = db.query(ExternalVolume).first()
        assert video.storage_id == lib.id and video.rel_path == "Cours/Rpm 101 test.mp4" and video.file_path == f"{first_mount}/Cours/Rpm 101 test.mp4"
        assert video.duration_seconds and video.thumbnail_path and str(env.tmp) not in video.thumbnail_path  # miniature INTERNE
        assert video.program == "RPM"
    # Réindexer ne duplique rien.
    again = env.client.post(f"/api/storage/volumes/{vol.key}/index", json={"entries": [{"path": "Cours"}], "kind": "video"}).json()
    assert wait_job(env.client, again["job_id"])["details"]["skipped"][0]["reason"] == "already_indexed"

    api = env.client.get(f"/api/videos/{video_id}").json()
    assert api["available"] is True and api["external"] is True
    stream = env.client.get(f"/api/videos/{video_id}/stream", headers={"Range": "bytes=0-9"})
    assert stream.status_code == 206 and len(stream.content) == 10
    head = env.client.head(f"/api/videos/{video_id}/stream")
    assert head.status_code == 200 and int(head.headers["content-length"]) == media.video.stat().st_size
    listing = env.client.get("/api/storage/volumes").json()["volumes"][0]
    assert listing["library"]["registered"] and listing["library"]["online"] and listing["library"]["stats"]["videos"] == 1

    # --- arrachage brutal : indisponible, jamais supprimé, plus de 500/404 à la lecture ---
    env.driver.unplug(vol.key)
    env.refresh()
    assert env.client.get(f"/api/videos/{video_id}").json()["available"] is False
    for method in (env.client.get, env.client.head):
        gone = method(f"/api/videos/{video_id}/stream")
        assert gone.status_code == 503 and gone.headers["retry-after"] == "5"
    assert codes(env.client.get(f"/api/videos/{video_id}/stream")) == "storage_unavailable"
    offline = env.client.get("/api/storage/volumes").json()["volumes"]
    assert offline[0]["connected"] is False and offline[0]["state"] == "offline" and offline[0]["library"]["online"] is False
    with SessionLocal() as db:
        row = db.query(Video).filter(Video.id == video_id).first()
        assert row is not None and row.file_path.startswith("external:") and row.rel_path == "Cours/Rpm 101 test.mp4"
    assert any(not v["available"] for v in env.client.get("/api/videos").json() if v["id"] == video_id)

    # --- rebranchement (même UUID, AUTRE point de montage) : chemins remappés, disponible de nouveau ---
    env.driver.plug("sdz", "BBBB-0001", None, label="CLUB")  # le contenu du disque est toujours là
    env.refresh()
    new_mount = env.driver.volumes[next(iter(env.driver.volumes))].mountpoint
    assert new_mount != first_mount
    with SessionLocal() as db:
        assert db.query(Video).filter(Video.id == video_id).first().file_path == f"{new_mount}/Cours/Rpm 101 test.mp4"
    assert env.client.get(f"/api/videos/{video_id}").json()["available"] is True
    assert env.client.get(f"/api/videos/{video_id}/stream", headers={"Range": "bytes=0-4"}).status_code == 206

    # --- garde-fous : ni suppression, ni renommage, ni normalisation sur le support ---
    on_disk = env.driver.disk_dir(next(iter(env.driver.volumes))) / "Cours" / "Rpm 101 test.mp4"
    assert env.client.put(f"/api/videos/{video_id}", json={"title": "Nouveau titre"}).status_code == 200
    assert on_disk.exists()
    normalize = env.client.post(f"/api/videos/{video_id}/normalize")
    assert normalize.status_code == 409 and normalize.json()["detail"]["code"] == "external_read_only"
    assert env.client.delete(f"/api/videos/{video_id}").status_code == 200
    assert on_disk.exists() and on_disk.read_bytes() == media.video.read_bytes()  # le fichier de l'utilisateur est intact


def test_disk_images_are_never_remounted_automatically(env):
    """udisks libère un périphérique loop dès son démontage : remonter une image « en lecture seule » la ferait disparaître."""
    image = env.driver.plug("loop5", "BBBB-0099", kind="image", dev_type="loop", mounted_rw=True)
    usb = env.driver.plug("sdq", "BBBB-0098", mounted_rw=True)
    env.refresh()
    _register(env, image.key)
    _register(env, usb.key)
    env.refresh()
    assert env.driver.unmount_calls == [usb.key]  # la clé USB est remontée en lecture seule, l'image est laissée telle quelle
    assert vol_view(env, usb.key)["mounted_read_only"] is True and vol_view(env, image.key)["mounted_read_only"] is False
    read_only = {i["id"]: i for i in vol_view(env, image.key)["longevity"]}["read_only"]
    assert read_only["status"] == "inactive"  # dit honnêtement qu'elle n'est pas en lecture seule


@needs_ffmpeg
def test_unregister_requires_confirmation_and_never_deletes_files(env, media):
    vol = env.driver.plug("sda", "BBBB-0002", {"Cours/Rpm 102.mp4": media.video.read_bytes(), "Album stk/01 - a.mp3": media.audio.read_bytes()})
    env.refresh()
    _register(env, vol.key)
    jobs = [
        env.client.post(f"/api/storage/volumes/{vol.key}/index", json={"entries": [{"path": "Cours"}], "kind": "video"}).json(),
        env.client.post(f"/api/storage/volumes/{vol.key}/index", json={"entries": [{"path": "Album stk"}], "kind": "audio_course"}).json(),
    ]
    for j in jobs:
        assert wait_job(env.client, j["job_id"])["stage"] == "done"
    with SessionLocal() as db:
        assert db.query(AudioTrack).filter(AudioTrack.storage_id.isnot(None)).count() == 1
    refused = env.client.delete(f"/api/storage/volumes/{vol.key}/library")
    assert refused.status_code == 409 and codes(refused) == "has_media"
    removed = env.client.delete(f"/api/storage/volumes/{vol.key}/library", params={"purge": True})
    assert removed.status_code == 200 and removed.json()["removed"]["videos"] == 1 and removed.json()["removed"]["audio_courses"] == 1
    with SessionLocal() as db:
        assert db.query(Video).filter(Video.storage_id.isnot(None)).count() == 0 and db.query(ExternalVolume).count() == 0
    assert (env.driver.disk_dir(vol.key) / "Cours" / "Rpm 102.mp4").exists()
    assert (env.driver.disk_dir(vol.key) / "Album stk" / "01 - a.mp3").exists()


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


def test_portable_device_cannot_be_used_as_extension_or_written(env):
    assert env.client.get("/api/storage/portable").json()["reason"] == "missing_tool"
    assert "gvfs-backends" in env.client.get("/api/storage/portable").json()["install"]
    for action in ("index", "export"):
        response = env.client.post(f"/api/storage/volumes/p-abc123/{action}", json={"entries": [{"path": "a"}], "kind": "video", "ids": [1]})
        assert response.status_code == 409 and codes(response) in ("portable_no_direct", "read_only_device")
    assert codes(env.client.post("/api/storage/volumes/p-abc123/import", json={"entries": [{"path": "a"}], "kind": "video"})) == "not_mounted"


def test_duplicate_uuid_cannot_be_registered(env):
    a = env.driver.plug("sda", "CCCC-0001", label="A")
    b = env.driver.plug("sdb", "CCCC-0001", label="B")
    env.driver.volumes[b.key + "x"] = b.__class__(**{**b.__dict__, "key": b.key + "x", "device": "/dev/sdb1x", "name": "sdb1x"})
    env.driver.volumes.pop(b.key, None)
    env.refresh()
    views = get_volumes(env)["volumes"]
    assert len(views) == 2 and all(v["can_register"] is False and v["register_block"] == "uuid_duplicate" for v in views)
    assert codes(env.client.post(f"/api/storage/volumes/{a.key}/library", json={})) == "uuid_duplicate"


def test_volume_without_uuid_imports_but_is_not_registrable(env):
    vol = env.driver.plug("sda", None, {"a.mp4": b"x"})
    env.refresh()
    view = vol_view(env, vol.key)
    assert view["can_register"] is False and view["register_block"] == "uuid_missing" and view["uuid_known"] is False
    assert codes(env.client.post(f"/api/storage/volumes/{vol.key}/library", json={})) == "uuid_missing"


# ---------------------------------------------------------------------------------------------------------
# Export (écriture temporaire et explicite) et compteur d'octets écrits
# ---------------------------------------------------------------------------------------------------------

def test_export_writes_temporarily_then_returns_to_read_only_and_counts_bytes(env, tmp_path):
    vol = env.driver.plug("sda", "DDDD-0001", {"deja.txt": b"1"}, kind="sd", label="CARTE")
    env.refresh()
    _register(env, vol.key)
    local = tmp_path / "local" / "cours.mp4"
    local.parent.mkdir()
    local.write_bytes(os.urandom(300_000))
    with SessionLocal() as db:
        video = Video(file_path=str(local), title="__stk_Export", source=ImportSource.upload)
        db.add(video)
        db.commit()
        video_id = video.id
    response = env.client.post(f"/api/storage/volumes/{vol.key}/export", json={"kind": "video", "ids": [video_id], "dest": "Sauvegarde/Bobine"})
    assert response.status_code == 202, response.text
    job = wait_job(env.client, response.json()["job_id"])
    assert job["stage"] == "done" and job["details"]["exported"] == 1
    exported = env.driver.disk_dir(vol.key) / "Sauvegarde" / "Bobine" / "__stk_Export.mp4"
    assert exported.exists() and _sha(exported) == _sha(local) and local.exists()
    assert not list((env.driver.disk_dir(vol.key) / "Sauvegarde" / "Bobine").glob(".bobine-*"))  # pas de temporaire oublié
    deadline = time.time() + 10
    while time.time() < deadline and vol_view(env, vol.key)["state"] == "busy":
        time.sleep(0.2)
    view = vol_view(env, vol.key)
    assert view["mounted_read_only"] is True  # retour automatique en lecture seule
    rw_calls = [options for _, options in env.driver.mount_calls if options[0] == "rw"]
    assert len(rw_calls) == 1
    assert view["library"]["bytes_written"] == 300_000 and view["library"]["wear_level"] == "ok"
    # Un second export ne remplace jamais le fichier existant.
    second = env.client.post(f"/api/storage/volumes/{vol.key}/export", json={"kind": "video", "ids": [video_id], "dest": "Sauvegarde/Bobine"}).json()
    assert wait_job(env.client, second["job_id"])["stage"] == "done"
    assert (env.driver.disk_dir(vol.key) / "Sauvegarde" / "Bobine" / "__stk_Export (2).mp4").exists() and exported.exists()
    with SessionLocal() as db:
        db.query(Video).filter(Video.id == video_id).delete()
        db.commit()


def test_export_refuses_unsafe_destination_and_unwritable_filesystems(env, tmp_path):
    vol = env.driver.plug("sda", "DDDD-0002", {"x.txt": b"1"})
    env.refresh()
    local = tmp_path / "l.mp4"
    local.write_bytes(b"data")
    with SessionLocal() as db:
        video = Video(file_path=str(local), title="__stk_Dest", source=ImportSource.upload)
        db.add(video)
        db.commit()
        video_id = video.id
    base = f"/api/storage/volumes/{vol.key}/export"
    body = {"kind": "video", "ids": [video_id]}
    assert codes(env.client.post(base, json=body)) == "not_mounted"
    env.client.post(f"/api/storage/volumes/{vol.key}/mount", json={})
    for hostile in ("../../etc", "/etc", "a/../../b"):
        refused = env.client.post(base, json={**body, "dest": hostile})
        assert refused.status_code == 400 and codes(refused) == "bad_path"  # refusé avant toute écriture ou remontage
    assert env.driver.mount_calls[-1][1][0] == "ro" and not (env.tmp / "etc").exists()
    assert codes(env.client.post(base, json={"kind": "video", "ids": [987654]})) == "nothing_to_export"
    assert codes(env.client.post(base, json={"kind": "video", "ids": []})) == "empty_selection"
    env.service._dirty.add(vol.key)
    assert codes(env.client.post(base, json=body)) == "write_refused"
    with SessionLocal() as db:
        db.query(Video).filter(Video.id == video_id).delete()
        db.commit()


# ---------------------------------------------------------------------------------------------------------
# Longévité : réglages, santé, TRIM, conseiller
# ---------------------------------------------------------------------------------------------------------

def test_settings_are_visible_validated_and_disableable(env):
    vol = env.driver.plug("sda", "EEEE-0001")
    env.refresh()
    assert codes(env.client.put(f"/api/storage/volumes/{vol.key}/settings", json={"noatime": False})) == "not_registered"
    _register(env, vol.key)
    updated = env.client.put(f"/api/storage/volumes/{vol.key}/settings", json={"noatime": False, "standby_minutes": 9999, "read_only": True}).json()
    assert updated["noatime"] is False and updated["standby_minutes"] == 240 and updated["read_only"] is True
    items = {i["id"]: i for i in vol_view(env, vol.key)["longevity"]}
    assert items["noatime"]["status"] == "disabled" and items["noatime"]["enabled"] is False
    env.client.post(f"/api/storage/volumes/{vol.key}/mount", json={})  # déjà monté ro par l'enregistrement
    defaults = env.client.put("/api/storage/settings", json={"noexec": False}).json()
    assert defaults["noexec"] is False
    other = env.driver.plug("sdb", "EEEE-0002")
    env.refresh()
    assert vol_view(env, other.key)["library"]["settings"]["noexec"] is False  # les défauts globaux s'appliquent aux autres supports
    assert env.client.put("/api/storage/settings", json={"standby_minutes": "beaucoup"}).status_code == 422


def test_health_is_honest_without_smart_and_counts_writes(env):
    vol = env.driver.plug("sda", "EEEE-0003")
    env.refresh()
    report = env.client.get(f"/api/storage/volumes/{vol.key}/health").json()
    assert report["available"] is False and report["reason"] == "permission" and report["overall"] == "ok" and report["bytes_written"] == 0
    env.driver.smart_report = {"available": True, "status": "warning", "warnings": ["reallocated_sectors"], "temperature_c": 40, "wear_percent_used": 12.0}
    refreshed = env.client.get(f"/api/storage/volumes/{vol.key}/health", params={"refresh": True}).json()
    assert refreshed["overall"] == "warning" and refreshed["warnings"] == ["reallocated_sectors"]
    cached = env.client.get(f"/api/storage/volumes/{vol.key}/health").json()
    assert cached["overall"] == "warning"


def test_trim_is_refused_without_privileges(env):
    vol = env.driver.plug("sda", "EEEE-0004")
    env.refresh()
    response = env.client.post(f"/api/storage/volumes/{vol.key}/trim")
    assert response.status_code == 501 and codes(response) == "needs_root"
    env.driver.root_user = True
    assert env.client.post(f"/api/storage/volumes/{vol.key}/trim").json() == {"result": "ok"}


def test_standby_applies_only_to_idle_rotational_disks(env):
    hdd = env.driver.plug("sda", "EEEE-0005", kind="hdd", rotational=True)
    ssd = env.driver.plug("sdb", "EEEE-0006", kind="usb", rotational=False)
    env.refresh()
    for key in (hdd.key, ssd.key):
        env.client.post(f"/api/storage/volumes/{key}/mount", json={})
    env.service._activity[hdd.key] = time.monotonic() - 3600
    env.service._activity[ssd.key] = time.monotonic() - 3600
    env.service._last_maintenance = 0
    env.client.portal.call(env.service._maintenance)
    assert env.driver.standby_calls == [hdd.key]
    assert vol_view(env, hdd.key)["standby"]["ok"] is True
    env.client.portal.call(env.service._maintenance)  # pas de répétition tant que le disque n'a pas été réveillé
    env.service._last_maintenance = 0
    env.client.portal.call(env.service._maintenance)
    assert env.driver.standby_calls == [hdd.key]


def test_format_advisor_endpoint(env):
    rec = env.client.get("/api/storage/advisor/format", params={"host": "linux", "others": "windows,macos"}).json()
    assert rec["fstype"] == "exfat" and rec["destructive"] is True and "windows" in rec["procedures"]
    assert env.client.get("/api/storage/advisor/format", params={"host": "windows"}).json()["fstype"] == "ntfs"
    assert env.client.get("/api/storage/advisor/format", params={"legacy": True}).json()["fstype"] == "vfat"


# ---------------------------------------------------------------------------------------------------------
# Dégradation propre : lecture, planning, radio
# ---------------------------------------------------------------------------------------------------------

def test_startup_puts_every_external_path_in_waiting_state(env):
    from app.storage import library

    with SessionLocal() as db:
        lib = ExternalVolume(fs_uuid="FFFF-0001", label="X", kind="usb")
        db.add(lib)
        db.commit()
        video = Video(file_path="/run/media/u/X/a.mp4", title="__stk_Startup", source=ImportSource.upload, storage_id=lib.id, rel_path="a.mp4")
        db.add(video)
        db.commit()
        library.mark_all_offline(db)
        db.refresh(video)
        assert video.file_path == "external://FFFF-0001/a.mp4" and video.available is False


def test_scheduler_and_playlists_skip_unavailable_media(env):
    from app.models import Playlist, PlaylistItem, ScheduleTargetType
    from app.routers.playback import _build_playlist_video_items
    from app.scheduler_manager import _scheduled_target_unavailable

    with SessionLocal() as db:
        lib = ExternalVolume(fs_uuid="FFFF-0002", label="Y", kind="usb")
        db.add(lib)
        db.commit()
        remote_video = Video(file_path="external://FFFF-0002/a.mp4", title="__stk_Ext", source=ImportSource.upload, storage_id=lib.id, rel_path="a.mp4")
        local_video = Video(file_path="/tmp/local.mp4", title="__stk_Loc", source=ImportSource.upload)
        playlist = Playlist(name="__stk_pl")
        db.add_all([remote_video, local_video, playlist])
        db.commit()
        db.add_all([PlaylistItem(playlist_id=playlist.id, video_id=remote_video.id, position=0), PlaylistItem(playlist_id=playlist.id, video_id=local_video.id, position=1)])
        db.commit()
        db.refresh(playlist)
        assert _scheduled_target_unavailable(db, ScheduleTargetType.video, remote_video.id) is True
        assert _scheduled_target_unavailable(db, ScheduleTargetType.video, local_video.id) is False
        assert _scheduled_target_unavailable(db, ScheduleTargetType.playlist, playlist.id) is False  # il reste un média local
        assert [i["title"] for i in _build_playlist_video_items(playlist)] == ["__stk_Loc"]
        availability.set_online({lib.id: "/mnt/y"})
        assert [i["title"] for i in _build_playlist_video_items(playlist)] == ["__stk_Ext", "__stk_Loc"]
        availability.set_online({})
        db.query(PlaylistItem).filter(PlaylistItem.playlist_id == playlist.id).delete()
        db.query(Playlist).filter(Playlist.id == playlist.id).delete()
        db.commit()


def test_radio_engine_skips_tracks_of_unplugged_storage():
    import asyncio

    from app.radio_manager import RadioPlaybackManager

    async def noop(message):
        return None

    availability.set_online({7: "/mnt/z"})
    tracks = [{"id": 1, "title": "a", "storage_id": None}, {"id": 2, "title": "b", "storage_id": 7}, {"id": 3, "title": "c", "storage_id": 7}, {"id": 4, "title": "d", "storage_id": None}]

    async def scenario():
        manager = RadioPlaybackManager(noop)
        await manager.load_playlist(1, "pl", tracks, shuffle=False, repeat="playlist")
        assert [t["id"] for t in manager.state["order"]] == [1, 2, 3, 4]
        availability.set_online({})  # le support est arraché pendant la lecture
        await manager._advance_or_stop()
        assert manager.state["current_track"]["id"] == 4  # 2 et 3 sautés
        await manager._advance_or_stop()
        assert manager.state["current_track"]["id"] == 1  # boucle sans s'arrêter
        reloaded = RadioPlaybackManager(noop)
        await reloaded.load_playlist(1, "pl", tracks, shuffle=False)
        assert [t["id"] for t in reloaded.state["order"]] == [1, 4]  # chargement : seuls les médias lisibles
        all_gone = RadioPlaybackManager(noop)
        await all_gone.load_playlist(1, "pl", [tracks[1], tracks[2]], repeat="playlist")
        assert all_gone.state["state"] == "idle" and all_gone.state["current_track"] is None

    try:
        asyncio.run(scenario())
    finally:
        availability.set_online({})
