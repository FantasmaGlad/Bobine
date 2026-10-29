"""`os_key()` choisit le message d'aide d'un ffmpeg introuvable : sur le
runtime Python 3.11 de l'APK Android TV (armeabi-v7a), ni
`sys.getandroidapilevel` ni `platform.system() == "Android"` n'existent,
seul `is_android()` (marqueur du bootstrap) le reconnaît."""

import sys

import pytest

from app.utils import android_runtime, ffmpeg_binaries


@pytest.fixture
def linux_sans_signal_android(monkeypatch):
    for var in ("BOBINE_PLATFORM", "ANDROID_ROOT", "ANDROID_DATA"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(android_runtime.platform, "system", lambda: "Linux")
    monkeypatch.delattr(sys, "getandroidapilevel", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")


def test_linux_de_bureau_reste_linux(linux_sans_signal_android):
    assert ffmpeg_binaries.os_key() == "linux"


def test_runtime_311_android_tv_est_android(linux_sans_signal_android, monkeypatch):
    monkeypatch.setenv("BOBINE_PLATFORM", "android")
    assert ffmpeg_binaries.os_key() == "android"


def test_runtime_recent_android_est_android(linux_sans_signal_android, monkeypatch):
    monkeypatch.setattr(sys, "getandroidapilevel", lambda: 34, raising=False)
    assert ffmpeg_binaries.os_key() == "android"


@pytest.mark.parametrize("plateforme,attendu", [("darwin", "macos"), ("win32", "windows")])
def test_bureau_macos_et_windows(linux_sans_signal_android, monkeypatch, plateforme, attendu):
    monkeypatch.setattr(sys, "platform", plateforme)
    assert ffmpeg_binaries.os_key() == attendu
