import os
import tempfile
from pathlib import Path

os.environ.setdefault("BOBINE_MDNS", "0")


def pytest_configure(config):
    if getattr(config.option, "basetemp", None) is None:
        config.option.basetemp = Path(tempfile.gettempdir()) / "pytest-bobine"
    config.addinivalue_line("markers", "recent_stack: banc qui exige le client de test de Starlette recent")


def pytest_collection_modifyitems(config, items):
    import fastapi

    if tuple(int(part) for part in fastapi.__version__.split(".")[:2]) >= (0, 100):
        return
    skip = pytest.mark.skip(reason="client de test de Starlette trop ancien (profil Android)")
    for item in items:
        if "recent_stack" in item.keywords:
            item.add_marker(skip)


import pytest


@pytest.fixture(autouse=True)
def _no_pending_config_mirror():

    def cancel() -> None:
        from app import config_files
        from app import config_mirror

        with config_mirror._mirror_lock:
            timer, config_mirror._mirror_timer = config_mirror._mirror_timer, None
        if timer is not None:
            timer.cancel()

    cancel()
    yield
    cancel()


@pytest.fixture()
def recorder(monkeypatch):
    from app import cli
    from cli_support import Recorder

    rec = Recorder({
        ("GET", "/api/health"): {"status": "ok"},
        ("GET", "/api/playback/state"): {"state": "waiting"},
        ("GET", "/api/diagnostics/system"): {"status": "warning", "checks": [], "problems": [
            {"code": "port_fallback", "severity": "warning", "message": "port", "remedy": "libérer"},
        ]},
        ("GET", "/api/logs"): {"entries": [], "truncated": False},
        ("POST", "/api/config/apply"): {"applied": False, "changes": {}, "skipped": [], "restart_required": []},
        ("GET", "/api/updates/check"): {"has_update": False, "current_version": "5.1.0"},
    })
    monkeypatch.setattr(cli.Client, "request", lambda self, method, path, **kw: rec(self, method, path, **kw))
    monkeypatch.setenv("BOBINE_PORT", "1903")
    return rec
