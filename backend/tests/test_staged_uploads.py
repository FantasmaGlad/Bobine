"""Téléversement par morceaux reprenable (lot F2 du plan Firefox) : création,
ajout par offset, reprise après désynchronisation, réutilisation par
empreinte, protections (dépassement, espace disque, session incomplète) et
reprise du fichier par un point d'entrée d'import sans recopie."""

import os
import sys
import time
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")
os.environ.setdefault("BOBINE_MEDIA_DIR", "data/test_videos")
os.environ.setdefault("BOBINE_WATCH_DIR", "data/test_watched")
os.environ.setdefault("BOBINE_THUMBNAILS_DIR", "data/test_thumbnails")

from app.utils import staged_uploads as staged  # noqa: E402

DATA = bytes(range(256)) * 100  # 25 600 octets


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(staged, "staging_dir", lambda: tmp_path)
    from app.main import app

    return TestClient(app)


def _create(client, size=len(DATA), name="cours.mp4", fingerprint=None):
    r = client.post("/api/uploads", json={"filename": name, "size": size, "fingerprint": fingerprint})
    assert r.status_code == 201, r.text
    return r.json()


def _patch(client, upload_id, offset, body):
    return client.patch(f"/api/uploads/{upload_id}", content=body, headers={"Upload-Offset": str(offset)})


def test_full_transfer_in_chunks_then_take(client, tmp_path):
    up = _create(client)
    assert up["offset"] == 0 and up["complete"] is False
    third = len(DATA) // 3
    r = _patch(client, up["upload_id"], 0, DATA[:third])
    assert r.status_code == 200 and r.json()["offset"] == third
    r = _patch(client, up["upload_id"], third, DATA[third:])
    assert r.json()["complete"] is True

    path, original = staged.take_staged_upload(up["upload_id"])
    assert original == "cours.mp4" and path.endswith(".mp4")
    assert Path(path).read_bytes() == DATA
    assert not (tmp_path / f"{up['upload_id']}.json").exists()


def test_resume_after_desync_reports_real_offset(client):
    up = _create(client)
    _patch(client, up["upload_id"], 0, DATA[:1000])
    # le client croit être à 0 (réponse perdue) : le serveur indique l'offset réel
    r = _patch(client, up["upload_id"], 0, DATA[:500])
    assert r.status_code == 409
    assert r.json()["offset"] == 1000 and r.headers["Upload-Offset"] == "1000"
    assert client.get(f"/api/uploads/{up['upload_id']}").json()["offset"] == 1000


def test_same_fingerprint_resumes_the_existing_session(client):
    first = _create(client, fingerprint="cours.mp4|25600|1700000000")
    _patch(client, first["upload_id"], 0, DATA[:2000])
    again = _create(client, fingerprint="cours.mp4|25600|1700000000")
    assert again["upload_id"] == first["upload_id"] and again["offset"] == 2000


def test_chunk_larger_than_announced_size_is_rejected(client):
    up = _create(client, size=100)
    r = _patch(client, up["upload_id"], 0, b"x" * 150)
    assert r.status_code == 413
    assert client.get(f"/api/uploads/{up['upload_id']}").json()["offset"] == 100


def test_missing_or_invalid_offset_header(client):
    up = _create(client)
    assert client.patch(f"/api/uploads/{up['upload_id']}", content=b"abc").status_code == 400


def test_insufficient_disk_space_is_507(client, monkeypatch):
    monkeypatch.setattr(staged, "_free_bytes", lambda: 10)
    r = client.post("/api/uploads", json={"filename": "gros.mp4", "size": 10_000})
    assert r.status_code == 507 and "Espace disque" in r.json()["detail"]


def test_incomplete_session_cannot_be_taken(client):
    up = _create(client)
    _patch(client, up["upload_id"], 0, DATA[:10])
    with pytest.raises(HTTPException) as e:
        staged.take_staged_upload(up["upload_id"])
    assert e.value.status_code == 409


def test_unknown_and_malformed_ids_are_404(client):
    assert client.get("/api/uploads/" + "0" * 32).status_code == 404
    assert client.get("/api/uploads/../../etc/passwd").status_code in (404, 405)
    assert client.get("/api/uploads/not-a-hex-id").status_code == 404


def test_cancel_removes_the_files(client, tmp_path):
    up = _create(client)
    assert client.delete(f"/api/uploads/{up['upload_id']}").status_code == 204
    assert not list(tmp_path.glob(f"{up['upload_id']}*"))


def test_stale_sessions_are_purged(client, tmp_path):
    up = _create(client)
    old = time.time() - staged.STALE_AFTER_SECONDS - 10
    for suffix in (".part", ".json"):
        os.utime(tmp_path / f"{up['upload_id']}{suffix}", (old, old))
    assert staged.purge_stale() == 2


def test_receive_single_upload_prefers_staged_file_without_copy(client):
    up = _create(client, name="archive.zip")
    _patch(client, up["upload_id"], 0, DATA)
    path, name = staged.receive_single_upload(None, up["upload_id"], forced_suffix=".zip")
    assert name == "archive.zip" and path.endswith(".zip") and Path(path).stat().st_size == len(DATA)


def test_receive_single_upload_without_anything_is_400():
    with pytest.raises(HTTPException) as e:
        staged.receive_single_upload(None, None)
    assert e.value.status_code == 400
