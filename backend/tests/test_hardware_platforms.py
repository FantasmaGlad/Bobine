import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.hardware import platforms


@pytest.mark.parametrize(("system", "android", "expected"), [
    ("linux", True, ["android", "linux"]), ("linux", False, ["linux"]), ("darwin", False, ["macos"]),
    ("win32", False, ["windows"]), ("freebsd", False, []),
])
def test_detected_platforms_go_from_most_to_least_precise(system, android, expected):
    with patch.object(sys, "platform", system), patch.object(platforms, "is_android_system", return_value=android):
        assert platforms.detected() == expected


def test_first_answer_falls_back_to_the_next_platform():
    implementations = {"android": SimpleNamespace(read=lambda: ""), "linux": SimpleNamespace(read=lambda: "cpuinfo")}
    with patch.object(sys, "platform", "linux"), patch.object(platforms, "is_android_system", return_value=True):
        assert platforms.first_answer(implementations, lambda implementation: implementation.read()) == "cpuinfo"
    with patch.object(sys, "platform", "freebsd"), patch.object(platforms, "is_android_system", return_value=False):
        assert platforms.first_answer(implementations, lambda implementation: implementation.read()) is None
