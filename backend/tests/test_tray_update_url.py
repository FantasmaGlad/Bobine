import sys
import webbrowser
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

tray_updates = pytest.importorskip("app.desktop.tray_updates")


@pytest.fixture
def opened(monkeypatch):
    urls = []
    monkeypatch.setattr(webbrowser, "open", urls.append)
    monkeypatch.setattr(tray_updates, "_check_for_update_once", lambda: None)
    monkeypatch.setitem(tray_updates._update_state, "has_update", True)
    return urls


@pytest.mark.parametrize("url", ["https://github.com/FantasmaGlad/Bobine/releases", "http://127.0.0.1:8000/x"])
def test_web_update_url_is_opened(opened, monkeypatch, url):
    monkeypatch.setitem(tray_updates._update_state, "download_url", url)
    tray_updates._on_check_update(None, None)
    assert opened == [url]


@pytest.mark.parametrize("url", ["file:///etc/passwd", "javascript:alert(1)", "smb://host/share"])
def test_non_web_update_url_is_refused(opened, monkeypatch, caplog, url):
    monkeypatch.setitem(tray_updates._update_state, "download_url", url)
    tray_updates._on_check_update(None, None)
    assert opened == []
    assert "refusée" in caplog.text
