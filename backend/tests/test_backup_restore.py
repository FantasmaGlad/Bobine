import asyncio
import threading

from app.api.routes.settings import backup


def test_database_replacement_runs_off_the_event_loop(monkeypatch, tmp_path):
    current, incoming, config = tmp_path / "bobine.db", tmp_path / "incoming.db", tmp_path / "config.toml"
    current.write_bytes(b"ancienne")
    incoming.write_bytes(b"nouvelle")
    threads = []
    monkeypatch.setattr(backup, "release_sqlite_files", lambda path: None)
    monkeypatch.setattr(backup, "init_db", lambda: threads.append(threading.current_thread()))
    monkeypatch.setattr(backup, "_global_config_path", lambda: config)
    monkeypatch.setattr(backup, "log_activity", lambda *a, **k: None)

    class Tasks:
        def add_task(self, *a):
            pass

    asyncio.run(backup._restore_database_file(incoming, current, b"port = 1903\n", None, Tasks()))

    assert current.read_bytes() == b"nouvelle"
    assert current.with_suffix(".db.bak").read_bytes() == b"ancienne"
    assert config.read_bytes() == b"port = 1903\n"
    assert threads and threads[0] is not threading.main_thread()
