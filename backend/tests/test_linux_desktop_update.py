"""Mise à jour d'un poste Linux installé par paquet : un .deb passe par apt-get, qui installe les dépendances que la
nouvelle version ajoute ; `dpkg -i` (seul repli sans apt-get) laissait Bobine « non configuré » dès qu'il en manquait une."""
from pathlib import Path

import pytest

from app.utils.deployment_profiles import linux_desktop
from app.utils.deployment_profiles.linux_desktop import LinuxDesktopHandler


@pytest.fixture()
def handler(monkeypatch):
    calls = []
    monkeypatch.setattr(LinuxDesktopHandler, "_is_git_clone", lambda self: False)
    monkeypatch.setattr(LinuxDesktopHandler, "restart_services", lambda self: None)
    monkeypatch.setattr(linux_desktop, "download_with_progress",
                        lambda url, path, digest, **kwargs: Path(path).write_bytes(b"paquet"))
    monkeypatch.setattr(linux_desktop, "run_checked", lambda command, **kwargs: calls.append(command))
    return LinuxDesktopHandler(), calls


def test_deb_is_installed_by_apt_get_with_its_dependencies(handler, monkeypatch):
    update, calls = handler
    monkeypatch.setattr(linux_desktop.shutil, "which", lambda name: f"/usr/bin/{name}" if name == "apt-get" else None)
    update.apply_update(download_url="https://example.org/bobine_5.1.1_amd64.deb")
    command = calls[0]
    assert command[:5] == ["pkexec", "sh", "-c", linux_desktop._SENTINEL_SCRIPT, "sh"]
    assert command[5:11] == ["env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "-y", "--allow-downgrades"]
    assert "--allow-downgrades" in command and command[-1].endswith("bobine_update.deb")


def test_dpkg_remains_only_without_apt_get(handler, monkeypatch):
    update, calls = handler
    monkeypatch.setattr(linux_desktop.shutil, "which", lambda name: None)
    update.apply_update(download_url="https://example.org/bobine_5.1.1_amd64.deb")
    assert calls[0][5:8] == ["dpkg", "-i", calls[0][-1]]


def test_sentinel_is_created_by_root_in_run_not_tmp():
    assert linux_desktop.SELF_UPDATE_SENTINEL.startswith("/run/")
    assert "/tmp/" not in linux_desktop._SENTINEL_SCRIPT
