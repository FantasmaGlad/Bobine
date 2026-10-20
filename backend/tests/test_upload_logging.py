"""Journal du cycle d'un upload par morceaux (technical.log) : création, morceaux
(taille, durée), complétion, reprise, abandon, purge — sans donnée sensible."""

import logging
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")
os.environ.setdefault("BOBINE_MEDIA_DIR", "data/test_videos")
os.environ.setdefault("BOBINE_WATCH_DIR", "data/test_watched")
os.environ.setdefault("BOBINE_THUMBNAILS_DIR", "data/test_thumbnails")

from app.utils import staged_uploads as staged  # noqa: E402

DATA = bytes(range(256)) * 100  # 25 600 octets
SECRET_NAME = "Cours-Secret-Dupont.mov"
SECRET_FINGERPRINT = "Cours-Secret-Dupont.mov|25600|1700000000000"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(staged, "staging_dir", lambda: tmp_path)
    from app.main import app

    return TestClient(app)


def _messages(caplog):
    return [r.getMessage() for r in caplog.records if r.name in ("app.routers.uploads", "app.utils.staged_uploads")]


# ---------------------------------------------------------------------------
# Journal du cycle d'un upload
# ---------------------------------------------------------------------------

def test_upload_lifecycle_is_logged_without_sensitive_data(client, caplog):
    caplog.set_level(logging.INFO)
    r = client.post("/api/uploads", json={"filename": SECRET_NAME, "size": len(DATA), "fingerprint": SECRET_FINGERPRINT})
    up = r.json()
    uid = up["upload_id"]
    half = len(DATA) // 2
    client.patch(f"/api/uploads/{uid}", content=DATA[:half], headers={"Upload-Offset": "0"})
    client.patch(f"/api/uploads/{uid}", content=DATA[half:], headers={"Upload-Offset": "999"})  # désynchronisé
    client.patch(f"/api/uploads/{uid}", content=DATA[half:], headers={"Upload-Offset": str(half)})
    client.post("/api/uploads", json={"filename": SECRET_NAME, "size": len(DATA), "fingerprint": SECRET_FINGERPRINT})  # reprise
    staged.take_staged_upload(uid)

    text = "\n".join(_messages(caplog))
    assert f"Upload {uid[:8]} créé : {len(DATA)} octets, extension .mov" in text
    assert "morceau reçu" in text and f"{half} octets en" in text
    assert "reprise désynchronisée (client à 999, serveur à" in text
    assert "transfert complet" in text
    assert f"Upload {uid[:8]} remis à l'import" in text
    # Ni le nom du fichier, ni l'empreinte, ni l'identifiant complet.
    assert "Secret" not in text and "Dupont" not in text and "1700000000000" not in text
    assert uid not in text


def test_resumed_session_and_abort_are_logged(client, caplog):
    caplog.set_level(logging.INFO)
    up = client.post("/api/uploads", json={"filename": "a.mp4", "size": len(DATA), "fingerprint": "fp"}).json()
    client.patch(f"/api/uploads/{up['upload_id']}", content=DATA[:1000], headers={"Upload-Offset": "0"})
    again = client.post("/api/uploads", json={"filename": "a.mp4", "size": len(DATA), "fingerprint": "fp"}).json()
    assert again["upload_id"] == up["upload_id"]
    client.delete(f"/api/uploads/{up['upload_id']}")
    text = "\n".join(_messages(caplog))
    assert "repris : 1000/25600 octets déjà reçus" in text
    assert "abandonné par le client (1000 octets reçus" in text


def test_unknown_session_and_incomplete_take_are_logged(client, caplog):
    caplog.set_level(logging.INFO)
    assert client.get("/api/uploads/" + "0" * 32).status_code == 404
    up = client.post("/api/uploads", json={"filename": "a.mp4", "size": 100, "fingerprint": None}).json()
    with pytest.raises(Exception):
        staged.take_staged_upload(up["upload_id"])
    text = "\n".join(_messages(caplog))
    assert "session introuvable ou expirée" in text
    assert "transfert est incomplet (0/100 octets)" in text


def test_invalid_id_is_never_echoed_in_logs(client, caplog):
    caplog.set_level(logging.INFO)
    client.get("/api/uploads/" + "x" * 32)
    assert "xxxx" not in "\n".join(_messages(caplog))


def test_disk_full_refusal_and_purge_are_logged(client, caplog, monkeypatch, tmp_path):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(staged, "_free_bytes", lambda: 10 * 1_048_576)
    r = client.post("/api/uploads", json={"filename": "gros.mov", "size": 50 * 1_048_576, "fingerprint": None})
    assert r.status_code == 507
    old = tmp_path / ("e" * 32 + ".part")
    old.write_bytes(b"x")
    os.utime(old, (1, 1))
    assert staged.purge_stale() == 1
    text = "\n".join(_messages(caplog))
    assert "espace disque insuffisant (10 Mo libres" in text and "50 Mo annoncés" in text
    assert "Uploads périmés purgés : 1 fichier(s)" in text
