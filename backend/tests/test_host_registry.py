import os
import sys
from pathlib import Path

import pytest

from app import host
from app.utils import android_runtime


@pytest.fixture
def desktop(monkeypatch):
    monkeypatch.setattr(android_runtime, "is_android", lambda: False)
    monkeypatch.setattr("app.host.registry.is_android", lambda: False)


@pytest.mark.parametrize(("system", "key"), [("linux", "linux"), ("darwin", "macos"), ("win32", "windows"), ("cygwin", "linux"), ("freebsd14", "linux")])
def test_os_key_follows_sys_platform(desktop, monkeypatch, system, key):
    monkeypatch.setattr(sys, "platform", system)
    assert host.os_key() == key


@pytest.mark.parametrize(("system", "expected"), [("linux", [["xdg-open", "/d"]]), ("darwin", [["open", "/d"]]), ("freebsd14", [])])
def test_open_folder_uses_the_desktop_opener(monkeypatch, system, expected):
    opened = []
    monkeypatch.setattr(sys, "platform", system)
    monkeypatch.setattr("subprocess.Popen", lambda command, **kwargs: opened.append(command))
    host.open_folder("/d")
    assert opened == expected


@pytest.mark.parametrize(("system", "resources"), [("darwin", "/A.app/Contents/Resources"), ("linux", "/A.app/Contents/MacOS"), ("win32", "/A.app/Contents/MacOS")])
def test_bundle_resources_inside_a_macos_bundle(monkeypatch, system, resources):
    monkeypatch.setattr(sys, "platform", system)
    assert host.bundle_resources(Path("/A.app/Contents/MacOS/BobineBackend")) == Path(resources)


def test_windows_names_follow_os_name(monkeypatch):
    monkeypatch.setattr(os, "name", "nt")
    assert host.rejects_windows_names()
    monkeypatch.setattr(os, "name", "posix")
    assert not host.rejects_windows_names()
