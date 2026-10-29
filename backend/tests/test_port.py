"""Résolution du port d'écoute (app/utils/port.py) : port préféré libre, port
occupé, plage de repli épuisée, mode strict, fichier d'exécution écrit puis
supprimé, et câblage (plus aucun 8000 littéral dans les lanceurs)."""

import json
import os
import re
import socket
from pathlib import Path

import pytest

from app.utils import port as port_mod

REPO_ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("0.0.0.0", 0))
        return sock.getsockname()[1]


@pytest.fixture
def held_port():
    """Un port réellement occupé (socket en écoute) pour la durée du test."""
    sock = socket.socket()
    sock.bind(("0.0.0.0", 0))
    sock.listen()
    yield sock.getsockname()[1], sock
    sock.close()


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.delenv(port_mod.STRICT_ENV, raising=False)
    monkeypatch.setattr(port_mod, "runtime_dir", lambda: tmp_path)
    monkeypatch.setattr(port_mod, "_active_port", None)
    # pas de gestionnaire SIGTERM ni d'atexit dans le processus de pytest
    monkeypatch.setattr(port_mod, "_cleanup_hooks_installed", True)


# --- résolution ----------------------------------------------------------------

def test_free_preferred_port_is_returned_unchanged():
    free = _free_port()
    assert port_mod.resolve_port(free) == free


def test_busy_preferred_port_falls_back_to_a_following_port(held_port):
    busy, _ = held_port
    resolved = port_mod.resolve_port(busy)
    assert busy < resolved <= busy + port_mod.FALLBACK_SPAN


def test_fallback_skips_busy_following_ports(monkeypatch):
    attempted = []

    def fake_bind_error(port, host="0.0.0.0"):
        attempted.append(port)
        return None if port == 9004 else OSError("occupé")

    monkeypatch.setattr(port_mod, "_bind_error", fake_bind_error)
    assert port_mod.resolve_port(9000) == 9004
    assert attempted == [9000, 9001, 9002, 9003, 9004]


def test_exhausted_range_uses_a_system_assigned_port(monkeypatch):
    attempted = []

    def all_busy(port, host="0.0.0.0"):
        attempted.append(port)
        return OSError("occupé")

    monkeypatch.setattr(port_mod, "_bind_error", all_busy)
    monkeypatch.setattr(port_mod, "_system_assigned_port", lambda host="0.0.0.0": 54321)
    assert port_mod.resolve_port(9000) == 54321
    # le préféré et exactement FALLBACK_SPAN ports suivants ont été essayés
    assert attempted == list(range(9000, 9000 + port_mod.FALLBACK_SPAN + 1))


def test_range_is_capped_at_the_last_valid_port(monkeypatch):
    attempted = []
    monkeypatch.setattr(port_mod, "_bind_error", lambda port, host="0.0.0.0": attempted.append(port) or OSError("x"))
    monkeypatch.setattr(port_mod, "_system_assigned_port", lambda host="0.0.0.0": 40000)
    assert port_mod.resolve_port(65534) == 40000
    assert attempted == [65534, 65535]


def test_system_assigned_port_is_really_bindable():
    assigned = port_mod._system_assigned_port()
    assert 0 < assigned < 65536
    assert port_mod._can_bind(assigned)


def test_system_failure_is_reported_clearly(monkeypatch):
    monkeypatch.setattr(port_mod, "_bind_error", lambda port, host="0.0.0.0": OSError("occupé"))

    class _Refusing:
        def bind(self, *_a):
            raise OSError("plus de ports")

        def close(self):
            pass

    monkeypatch.setattr(port_mod.socket, "socket", lambda *a, **k: _Refusing())
    with pytest.raises(port_mod.PortUnavailableError, match="attribuer"):
        port_mod.resolve_port(9000)


def test_strict_mode_fails_with_a_clear_message_when_busy(monkeypatch, held_port):
    busy, _ = held_port
    monkeypatch.setenv(port_mod.STRICT_ENV, "1")
    with pytest.raises(port_mod.PortUnavailableError) as excinfo:
        port_mod.resolve_port(busy)
    message = str(excinfo.value)
    assert str(busy) in message and port_mod.STRICT_ENV in message and "BOBINE_PORT" in message


def test_strict_mode_still_accepts_a_free_port(monkeypatch):
    monkeypatch.setenv(port_mod.STRICT_ENV, "1")
    free = _free_port()
    assert port_mod.resolve_port(free) == free


@pytest.mark.parametrize("value,expected", [("1", True), ("true", True), ("YES", True), ("0", False), ("", False), ("no", False)])
def test_strict_env_parsing(monkeypatch, value, expected):
    monkeypatch.setenv(port_mod.STRICT_ENV, value)
    assert port_mod.is_strict() is expected


def test_preferred_port_comes_from_settings(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "port", 8123, raising=False)
    assert port_mod.preferred_port() == 8123


def test_default_preferred_port_stays_8000():
    assert port_mod.DEFAULT_PORT == 8000
    from app.config import Settings
    fields = getattr(Settings, "model_fields", None) or Settings.__fields__
    assert fields["port"].default == port_mod.DEFAULT_PORT


# --- fichier d'exécution -------------------------------------------------------

def test_runtime_file_is_written_atomically_with_port_and_pid(tmp_path):
    written = port_mod.write_runtime_file(8003, 8000)
    assert written == tmp_path / port_mod.RUNTIME_FILE_NAME
    data = json.loads(written.read_text(encoding="utf-8"))
    assert data["port"] == 8003 and data["pid"] == os.getpid()
    assert data["preferred"] == 8000 and data["fallback"] is True
    # aucun fichier temporaire ne subsiste
    assert [p.name for p in tmp_path.iterdir()] == [port_mod.RUNTIME_FILE_NAME]


def test_runtime_file_is_replaced_not_appended(tmp_path):
    port_mod.write_runtime_file(8001, 8000)
    port_mod.write_runtime_file(8002, 8000)
    assert json.loads((tmp_path / port_mod.RUNTIME_FILE_NAME).read_text())["port"] == 8002


def test_read_runtime_port_returns_the_live_port():
    port_mod.write_runtime_file(8007, 8000)
    assert port_mod.read_runtime_port() == 8007


def test_stale_runtime_file_of_a_dead_process_is_ignored(tmp_path):
    (tmp_path / port_mod.RUNTIME_FILE_NAME).write_text(json.dumps({"port": 8005, "pid": 2**22 + 12345}))
    assert port_mod.read_runtime_port() is None
    assert port_mod.read_runtime(require_live=False)["port"] == 8005


@pytest.mark.parametrize("content", ["", "pas du json", "[]", '{"port": "8000", "pid": 1}', '{"port": 0, "pid": 1}', '{"port": 70000, "pid": 1}', '{"port": 8000}', '{"port": true, "pid": 1}'])
def test_corrupt_runtime_file_is_ignored(tmp_path, content):
    (tmp_path / port_mod.RUNTIME_FILE_NAME).write_text(content)
    assert port_mod.read_runtime(require_live=False) is None


def test_missing_runtime_file_gives_none():
    assert port_mod.read_runtime_port() is None


def test_clear_removes_the_file(tmp_path):
    port_mod.write_runtime_file(8001, 8000)
    port_mod.clear_runtime_file()
    assert not (tmp_path / port_mod.RUNTIME_FILE_NAME).exists()


def test_clear_keeps_the_file_of_another_process(tmp_path):
    target = tmp_path / port_mod.RUNTIME_FILE_NAME
    target.write_text(json.dumps({"port": 8001, "pid": os.getpid() + 1}))
    port_mod.clear_runtime_file()
    assert target.exists()


def test_clear_without_file_is_silent():
    port_mod.clear_runtime_file()


def test_unwritable_directory_is_not_fatal(tmp_path):
    blocker = tmp_path / "fichier"
    blocker.write_text("x")
    assert port_mod.write_runtime_file(8001, 8000, directory=blocker / "sous-dossier") is None


def test_current_port_prefers_the_runtime_file_then_the_preferred_port(monkeypatch):
    monkeypatch.setattr(port_mod, "preferred_port", lambda: 8000)
    assert port_mod.current_port() == 8000
    port_mod.write_runtime_file(8004, 8000)
    assert port_mod.current_port() == 8004


# --- cycle de vie des lanceurs -------------------------------------------------

def test_acquire_publishes_then_release_cleans_up(monkeypatch, tmp_path):
    free = _free_port()
    monkeypatch.setattr(port_mod, "preferred_port", lambda: free)
    assert port_mod.acquire_listen_port() == free
    assert port_mod.active_port() == free
    assert port_mod.read_runtime_port() == free
    assert port_mod.read_runtime()["fallback"] is False
    port_mod.release_port()
    assert not (tmp_path / port_mod.RUNTIME_FILE_NAME).exists()
    assert port_mod._active_port is None


def test_acquire_reports_the_fallback_in_logs_and_file(monkeypatch, caplog, held_port):
    busy, _ = held_port
    monkeypatch.setattr(port_mod, "preferred_port", lambda: busy)
    with caplog.at_level("WARNING", logger=port_mod.logger.name):
        chosen = port_mod.acquire_listen_port()
    assert chosen != busy
    assert port_mod.read_runtime() == {**port_mod.read_runtime(), "port": chosen, "preferred": busy, "fallback": True}
    assert str(busy) in caplog.text and str(chosen) in caplog.text and "pare-feu" in caplog.text


def test_acquire_in_strict_mode_does_not_publish_anything(monkeypatch, tmp_path, held_port):
    busy, _ = held_port
    monkeypatch.setattr(port_mod, "preferred_port", lambda: busy)
    monkeypatch.setenv(port_mod.STRICT_ENV, "1")
    with pytest.raises(port_mod.PortUnavailableError):
        port_mod.acquire_listen_port()
    assert not (tmp_path / port_mod.RUNTIME_FILE_NAME).exists()
    assert port_mod._active_port is None


def test_active_port_defaults_to_the_preferred_port(monkeypatch):
    monkeypatch.setattr(port_mod, "preferred_port", lambda: 8042)
    assert port_mod.active_port() == 8042


# --- câblage : plus de 8000 littéral dans les lanceurs --------------------------

_PORT_LITERAL = re.compile(r"(?<![\d.\-])8000(?![\d\-])")

_WIRED_FILES = [
    "backend/run_backend.py",
    "backend/app/desktop/tray.py",
    "android/app/src/main/python/bobine_bootstrap.py",
    *sorted(str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / "android/app/src/main/java").rglob("*.kt")),
]


@pytest.mark.parametrize("relative", _WIRED_FILES)
def test_no_hardcoded_8000_in_launchers(relative):
    source = (REPO_ROOT / relative).read_text(encoding="utf-8")
    offenders = [
        f"{relative}:{number}: {line.strip()}"
        for number, line in enumerate(source.splitlines(), 1)
        if _PORT_LITERAL.search(line)
    ]
    assert not offenders, "port 8000 codé en dur :\n" + "\n".join(offenders)


def test_launchers_use_the_shared_resolution():
    run_backend = (REPO_ROOT / "backend/run_backend.py").read_text(encoding="utf-8")
    bootstrap = (REPO_ROOT / "android/app/src/main/python/bobine_bootstrap.py").read_text(encoding="utf-8")
    assert "acquire_listen_port" in run_backend and "release_port" in run_backend
    assert "acquire_listen_port" in bootstrap and "release_port" in bootstrap


def test_kotlin_endpoint_reads_the_file_the_backend_writes():
    kotlin = (REPO_ROOT / "android/app/src/main/java/com/bobine/app/BackendEndpoint.kt").read_text(encoding="utf-8")
    assert f'"{port_mod.RUNTIME_FILE_NAME}"' in kotlin
    assert "filesDir" in kotlin and "myPid" in kotlin


# --- consommateurs du fichier d'exécution ----------------------------------------

def test_tray_urls_follow_the_published_port(monkeypatch):
    from app.desktop import tray
    monkeypatch.setattr(port_mod, "preferred_port", lambda: 8000)
    assert tray._admin_url() == "http://127.0.0.1:8000"
    port_mod.write_runtime_file(8003, 8000)
    assert tray._admin_url() == "http://127.0.0.1:8003"
    assert tray._health_url() == "http://127.0.0.1:8003/api/health"
    assert tray._kiosk_url() == "http://127.0.0.1:8003/kiosk"
    assert tray._projector_url() == "http://127.0.0.1:8003/cinema/?channel=cable"
    assert tray._display_state_url() == "http://127.0.0.1:8003/api/display/state"


def test_tray_dev_backend_command_goes_through_the_shared_launcher(monkeypatch, tmp_path):
    from app.desktop import tray
    monkeypatch.setattr(tray.sys, "executable", str(tmp_path / "python"))
    command = tray._backend_command()
    assert command[0] == str(tmp_path / "python")
    assert Path(command[1]).name == "run_backend.py" and Path(command[1]).is_file()
    assert "--port" not in command


def test_projector_window_resolves_a_callable_url_at_launch():
    from app.desktop.displays import Monitor, ProjectorWindow
    urls = iter(["http://127.0.0.1:8000/x", "http://127.0.0.1:8002/x"])
    launched = []

    class _Proc:
        def poll(self):
            return None

        def terminate(self):
            pass

        def wait(self, timeout=None):
            return 0

    window = ProjectorWindow(
        lambda: next(urls),
        browser_finder=lambda: "/usr/bin/chromium",
        native_finder=lambda: None,
        popen=lambda command, **kw: launched.append(command) or _Proc(),
        profile_factory=lambda: "/tmp/bobine-profile-test",
    )
    window.show_on(Monitor("HDMI-1", 0, 0, 1920, 1080, True))
    window.close()
    window.show_on(Monitor("HDMI-1", 0, 0, 1920, 1080, True))
    assert launched[0][-1].startswith("http://127.0.0.1:8000/x")
    assert launched[1][-1].startswith("http://127.0.0.1:8002/x")


def test_runtime_file_is_removed_when_the_process_receives_sigterm(tmp_path):
    """uvicorn re-lève SIGTERM après son arrêt propre : le fichier doit disparaître quand même."""
    import signal
    import subprocess
    import sys
    import time

    script = (
        "import time\n"
        "from app.utils import port\n"
        "port.acquire_listen_port()\n"
        "print('ready', flush=True)\n"
        "time.sleep(30)\n"
    )
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT / "backend"),
        "BOBINE_USE_XDG": "1",
        "XDG_DATA_HOME": str(tmp_path / "xdg"),
        "BOBINE_PORT": str(_free_port()),
        "HOME": str(tmp_path / "home"),
    }
    if os.name != "posix" or sys.platform == "darwin":
        pytest.skip("chemin de données XDG propre à Linux")
    runtime = tmp_path / "xdg" / "bobine" / port_mod.RUNTIME_FILE_NAME
    child = subprocess.Popen([sys.executable, "-c", script], env=env, stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "ready"
        assert runtime.is_file()
        child.send_signal(signal.SIGTERM)
        assert child.wait(timeout=10) == -signal.SIGTERM
        assert not runtime.exists()
    finally:
        if child.poll() is None:
            child.kill()
