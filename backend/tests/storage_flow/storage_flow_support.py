"""Appui des parcours de stockage : supports simulés, vues, attente des tâches."""

import hashlib
import shutil
import time
from pathlib import Path
import pytest  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    AudioCourse,
    AudioTrack,
    ExternalVolume,
    RadioTrack,
    Setting,
    StorageImport,
    Video,
)
from app.storage import availability  # noqa: E402


HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


needs_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg indisponible")


KEYS = ("storage_defaults",)


def _sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _cleanup_db():
    with SessionLocal() as db:
        db.query(Setting).filter(Setting.key.in_(KEYS)).delete(synchronize_session=False)
        for model in (Video, AudioTrack, RadioTrack):
            for row in db.query(model).filter(model.storage_id.isnot(None)).all():
                db.delete(row)
        db.flush()
        db.query(Video).filter(Video.title.like("__stk_%")).delete(synchronize_session=False)
        db.query(AudioCourse).filter(AudioCourse.title.like("%stk%")).delete(synchronize_session=False)
        db.query(StorageImport).delete()
        db.query(ExternalVolume).delete()
        db.commit()
    availability.set_online({})


def _purge_local(model, condition) -> None:
    with SessionLocal() as db:
        for row in db.query(model).filter(condition).all():
            for attr in ("file_path", "thumbnail_path", "cover_path"):
                path = getattr(row, attr, None)
                if path and getattr(row, "storage_id", None) is None:
                    Path(path).unlink(missing_ok=True)
            db.delete(row)
        db.commit()


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


def _register(env, key):
    response = env.client.post(f"/api/storage/volumes/{key}/library", json={"nickname": "Clé du club"})
    assert response.status_code == 200, response.text
    return response.json()
