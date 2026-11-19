import platform
import types

import pytest

from app.desktop import system
from app.desktop.system import linux, macos, other, windows

PUBLIC = (
    "SOURCE_LABEL", "FIREWALL_HINT", "BACKEND_CREATIONFLAGS", "set_display_always_on", "keep_awake_while", "launch_kiosk",
    "list_monitors", "find_kiosk_browser", "find_native_projector", "ensure_launch_agent", "ensure_desktop_shortcut",
)


@pytest.mark.parametrize(("name", "module"), [("Linux", linux), ("Windows", windows), ("Darwin", macos), ("FreeBSD", other), ("", other)])
def test_registry_picks_the_desktop_implementation(monkeypatch, name, module):
    monkeypatch.setattr(platform, "system", lambda: name)
    assert system.current() is module


@pytest.mark.parametrize("module", [linux, windows, macos, other])
def test_every_implementation_offers_the_same_interface(module):
    assert all(hasattr(module, attribute) for attribute in PUBLIC)


def test_unknown_system_falls_back_to_the_browser(monkeypatch):
    opened = []
    monkeypatch.setattr(platform, "system", lambda: "FreeBSD")
    monkeypatch.setattr("webbrowser.open", opened.append)
    from app.desktop import tray_display

    tray_display.launch_kiosk_browser("http://k")
    tray_display._keep_awake_while_projecting(types.SimpleNamespace(pid=1))
    assert opened == ["http://k"]


def test_only_windows_skips_the_firewall_hint_and_hides_the_console():
    assert [m.FIREWALL_HINT for m in (linux, windows, macos, other)] == [True, False, True, True]
    assert windows.BACKEND_CREATIONFLAGS and not any(m.BACKEND_CREATIONFLAGS for m in (linux, macos, other))
