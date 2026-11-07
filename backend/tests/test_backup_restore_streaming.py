import concurrent.futures
import io
import sqlite3
import threading
import zipfile

import pytest
from fastapi import HTTPException

from app.routers import settings as settings_router
from app.utils import import_jobs


def _archive(path, db_path=None, bad_header=False):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        if db_path is not None:
            zf.write(db_path, "database.db")
        elif bad_header:
            zf.writestr("database.db", b"pas une base" * 10)
        zf.writestr("config.toml", b"[x]\n")


def _sqlite(path):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE settings (k TEXT)")
    con.commit()
    con.close()


def test_stage_reads_database_by_blocks_and_validates(tmp_path):
    db = tmp_path / "src.db"
    _sqlite(db)
    zip_path = tmp_path / "b.zip"
    _archive(zip_path, db_path=db)
    work = tmp_path / "work"
    work.mkdir()
    with open(zip_path, "rb") as f:
        staged, config = settings_router._stage_backup_archive(f, work)
    assert staged.read_bytes().startswith(b"SQLite format 3\x00")
    assert config == b"[x]\n"


def test_stage_refuses_invalid_inputs(tmp_path):
    work = tmp_path / "w"
    work.mkdir()
    with pytest.raises(HTTPException) as e:
        settings_router._stage_backup_archive(io.BytesIO(b""), work)
    assert e.value.status_code == 400
    with pytest.raises(HTTPException):
        settings_router._stage_backup_archive(io.BytesIO(b"pas un zip"), work)
    bad = tmp_path / "bad.zip"
    _archive(bad, bad_header=True)
    with open(bad, "rb") as f, pytest.raises(HTTPException):
        settings_router._stage_backup_archive(f, work)


def test_stage_refuses_when_disk_space_is_too_small(tmp_path, monkeypatch):
    db = tmp_path / "src.db"
    _sqlite(db)
    zip_path = tmp_path / "b.zip"
    _archive(zip_path, db_path=db)
    work = tmp_path / "w"
    work.mkdir()
    monkeypatch.setattr(settings_router.shutil, "disk_usage", lambda p: type("U", (), {"free": 10})())
    with open(zip_path, "rb") as f, pytest.raises(HTTPException) as e:
        settings_router._stage_backup_archive(f, work)
    assert e.value.status_code == 507


def test_cancel_queued_job_removes_its_temp_files(tmp_path):
    temp = tmp_path / "gros.mp4"
    temp.write_bytes(b"x")
    gate = threading.Event()
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    pool.submit(gate.wait)
    job_id = import_jobs.create_job("video", "gros.mp4", "gros")
    future = pool.submit(lambda: None)
    import_jobs.register_job_future(job_id, future, [str(temp)])
    assert import_jobs.cancel_job(job_id)
    gate.set()
    pool.shutdown()
    assert not temp.exists()
