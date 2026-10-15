"""Sur les profils où le navigateur partage la machine du
backend, ffmpeg tourne à priorité réduite pour ne pas affamer l'interface ;
l'appliance headless dédiée garde la pleine priorité (race to sleep)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")

from app.utils import video_utils  # noqa: E402

pytestmark = pytest.mark.skipif(os.name == "nt", reason="nice POSIX")


def _nice_of(pid: int) -> int:
    return os.getpriority(os.PRIO_PROCESS, pid)


@pytest.mark.parametrize("profile,expected_lower", [
    ("linux-desktop", True), ("macos", True), ("windows", True),
    ("linux-headless", False), ("android", False),
])
def test_shares_machine_profiles(monkeypatch, profile, expected_lower):
    monkeypatch.setattr("app.utils.deployment.get_deployment_profile", lambda: profile)
    assert video_utils._shares_machine_with_browser() is expected_lower


def test_desktop_profile_lowers_the_child_priority(monkeypatch):
    monkeypatch.setattr("app.utils.deployment.get_deployment_profile", lambda: "linux-desktop")
    child = subprocess.Popen(["sleep", "5"])
    try:
        before = _nice_of(child.pid)
        video_utils._lower_process_priority(child.pid)
        assert _nice_of(child.pid) == max(before, 10)
    finally:
        child.kill()


def test_headless_appliance_keeps_full_priority(monkeypatch):
    monkeypatch.setattr("app.utils.deployment.get_deployment_profile", lambda: "linux-headless")
    child = subprocess.Popen(["sleep", "5"])
    try:
        before = _nice_of(child.pid)
        video_utils._lower_process_priority(child.pid)
        assert _nice_of(child.pid) == before
    finally:
        child.kill()


def test_invalid_pid_never_raises(monkeypatch):
    monkeypatch.setattr("app.utils.deployment.get_deployment_profile", lambda: "linux-desktop")
    video_utils._lower_process_priority(2**22 + 12345)
