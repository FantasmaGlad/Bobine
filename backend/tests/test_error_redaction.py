import os

os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")
os.environ.setdefault("BOBINE_MEDIA_DIR", "data/test_videos")
os.environ.setdefault("BOBINE_WATCH_DIR", "data/test_watched")
os.environ.setdefault("BOBINE_THUMBNAILS_DIR", "data/test_thumbnails")

import pytest
from fastapi import FastAPI, HTTPException
from starlette.testclient import TestClient

from app.api.errors import install_error_handlers, redact_paths
from app.utils import import_jobs


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("[Errno 2] No such file or directory: '/home/user/Bobine/data/videos/a.mp4'", "[Errno 2] No such file or directory: 'a.mp4'"),
        ("ffmpeg a échoué sur /srv/media/cours/yoga.mkv : Invalid data", "ffmpeg a échoué sur yoga.mkv : Invalid data"),
        (r"Access denied: C:\ProgramData\Bobine\data\db.sqlite", "Access denied: db.sqlite"),
        ("Impossible de lire l'espace disque : /mnt/usb/", "Impossible de lire l'espace disque : "),
        ("Voir https://github.com/FantasmaGlad/Bobine/releases", "Voir https://github.com/FantasmaGlad/Bobine/releases"),
        ("Valeur invalide : 12/34", "Valeur invalide : 12/34"),
        ("Aucun chemin ici", "Aucun chemin ici"),
    ],
)
def test_redact_paths(message, expected):
    assert redact_paths(message) == expected


def test_http_errors_do_not_return_internal_paths():
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/text")
    def text():
        raise HTTPException(status_code=500, detail="Impossible de lire l'espace disque : [Errno 13] '/var/lib/bobine/data'")

    @app.get("/structured")
    def structured():
        raise HTTPException(status_code=409, detail={"code": "busy", "message": "Verrou tenu : /var/lib/bobine/lock"})

    client = TestClient(app)
    assert client.get("/text").json()["detail"]["message"] == "Impossible de lire l'espace disque : [Errno 13] 'data'"
    body = client.get("/structured").json()["detail"]
    assert body == {"code": "busy", "message": "Verrou tenu : lock"}


def test_failed_job_keeps_classification_and_hides_paths():
    job_id = import_jobs.create_job("video", "a.mp4")
    import_jobs.update_job(job_id, stage="error", error="[Errno 2] No such file or directory: '/home/user/data/videos/a.mp4'")
    job = import_jobs.get_job(job_id)
    assert job["error"] == "[Errno 2] No such file or directory: 'a.mp4'"
