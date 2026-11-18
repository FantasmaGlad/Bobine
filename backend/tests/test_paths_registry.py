import sys
from pathlib import Path
from unittest.mock import patch

from app.paths import registry


def test_windows_keeps_data_and_config_in_program_data(monkeypatch, tmp_path):
    monkeypatch.setenv("ProgramData", str(tmp_path))
    with patch("platform.system", return_value="Windows"), patch.object(registry, "is_android", lambda: False):
        assert registry.data_root(Path("/root")) == tmp_path / "Bobine"
        assert registry.global_config_path() == tmp_path / "Bobine" / "config.toml"


def test_frozen_macos_bundle_reads_its_resources(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "/Applications/Bobine.app/Contents/MacOS/Bobine")
    with patch("platform.system", return_value="Darwin"):
        assert registry.install_root(Path("/src")) == Path("/Applications/Bobine.app/Contents/Resources")


def test_linux_follows_xdg_when_asked(monkeypatch, tmp_path):
    monkeypatch.setenv("BOBINE_USE_XDG", "1")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    with patch("platform.system", return_value="Linux"), patch.object(registry, "is_android", lambda: False):
        assert registry.data_root(Path("/root")) == tmp_path / "bobine"


def test_android_uses_its_data_dir_and_the_default_config(monkeypatch, tmp_path):
    monkeypatch.setenv("BOBINE_ANDROID_DATA_DIR", str(tmp_path / "files"))
    with patch("platform.system", return_value="Linux"), patch.object(registry, "is_android", lambda: True):
        assert registry.data_root(Path("/root")) == tmp_path / "files"
        assert registry.global_config_path() == Path("/etc/bobine/config.toml")
