import importlib
import sys
import webbrowser
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def tray_updates(monkeypatch):
    monkeypatch.setitem(sys.modules, "pystray", MagicMock())
    monkeypatch.delitem(sys.modules, "app.desktop.tray_updates", raising=False)
    yield importlib.import_module("app.desktop.tray_updates")
    sys.modules.pop("app.desktop.tray_updates", None)


@pytest.fixture
def opened(monkeypatch, tray_updates):
    urls = []
    monkeypatch.setattr(webbrowser, "open", urls.append)
    monkeypatch.setattr(tray_updates, "_check_for_update_once", lambda: None)
    monkeypatch.setitem(tray_updates._update_state, "has_update", True)
    return urls


@pytest.mark.parametrize("url", ["https://github.com/FantasmaGlad/Bobine/releases", "http://127.0.0.1:8000/x"])
def test_web_update_url_is_opened(tray_updates, opened, monkeypatch, url):
    monkeypatch.setitem(tray_updates._update_state, "download_url", url)
    tray_updates._on_check_update(None, None)
    assert opened == [url]


@pytest.mark.parametrize("url", ["file:///etc/passwd", "javascript:alert(1)", "smb://host/share"])
def test_non_web_update_url_is_refused(tray_updates, opened, monkeypatch, caplog, url):
    monkeypatch.setitem(tray_updates._update_state, "download_url", url)
    tray_updates._on_check_update(None, None)
    assert opened == []
    assert "refusée" in caplog.text
