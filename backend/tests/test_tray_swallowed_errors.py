import sys
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pytest.importorskip("app.desktop.tray_display")

from app.desktop import tray_display, tray_urls  # noqa: E402
from app.utils import port  # noqa: E402


def _boom(*_args, **_kwargs):
    raise OSError("refused")


def test_unreadable_port_is_logged(monkeypatch, caplog):
    monkeypatch.setattr(port, "current_port", _boom)
    with caplog.at_level("DEBUG", logger=tray_urls.logger.name):
        assert tray_urls._admin_port() == port.DEFAULT_PORT
    assert "refused" in caplog.text


def test_unreadable_display_mode_is_logged(monkeypatch, caplog):
    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    with caplog.at_level("DEBUG", logger=tray_display.logger.name):
        assert tray_display._get_wired_display_mode() == "headless"
    assert "refused" in caplog.text
