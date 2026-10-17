"""Détection d'Android indépendante de la version de CPython, et ses
conséquences : profil de déploiement, canal rolling d'un build packagé."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils import android_runtime, deployment
from app.utils.version import rolling_channel_of_version


@pytest.fixture
def desktop_env(monkeypatch):
    """Environnement de bureau neutre : aucun des signaux Android présent."""
    for var in ("BOBINE_PLATFORM", "ANDROID_ROOT", "ANDROID_DATA"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(android_runtime.platform, "system", lambda: "Linux")
    monkeypatch.delattr(sys, "getandroidapilevel", raising=False)


def test_desktop_linux_is_not_android(desktop_env):
    assert android_runtime.is_android() is False
    assert deployment.get_deployment_profile() in ("linux-desktop", "linux-headless")


def test_bootstrap_marker_is_enough(desktop_env, monkeypatch):
    # Runtime Python 3.11 de Chaquopy : platform.system() == "Linux" et pas de
    # sys.getandroidapilevel — seul le marqueur posé par le bootstrap reste.
    monkeypatch.setenv("BOBINE_PLATFORM", "android")
    assert android_runtime.is_android() is True
    assert deployment.get_deployment_profile() == "android"


def test_zygote_environment_is_enough(desktop_env, monkeypatch):
    monkeypatch.setenv("ANDROID_ROOT", "/system")
    monkeypatch.setenv("ANDROID_DATA", "/data")
    assert android_runtime.is_android() is True


def test_a_single_zygote_variable_is_not_enough(desktop_env, monkeypatch):
    monkeypatch.setenv("ANDROID_ROOT", "/system")
    assert android_runtime.is_android() is False


def test_cpython_android_signals_still_work(desktop_env, monkeypatch):
    monkeypatch.setattr(android_runtime.platform, "system", lambda: "Android")
    assert android_runtime.is_android() is True


@pytest.mark.parametrize("version,expected", [
    ("5.0.0", None),
    ("V5.0.0", None),
    ("5.0.0-canary", "canary"),
    ("5.0.0-beta", "beta"),
    ("5.0.0~canary", "canary"),
    ("5.0.0-rc1", None),
])
def test_rolling_channel_of_version(version, expected):
    assert rolling_channel_of_version(version) == expected
