import pytest

from app.hardware import platforms
from app.hardware.uptime import android, linux, system


@pytest.fixture
def platforms_detected(monkeypatch):
    def use(names):
        monkeypatch.setattr(platforms, "detected", lambda: list(names))
    return use


def test_android_clock_comes_before_proc_uptime(monkeypatch, platforms_detected):
    platforms_detected(["android", "linux"])
    monkeypatch.setattr(android, "system_uptime", lambda: 120)
    monkeypatch.setattr(linux, "system_uptime", lambda: 999)
    assert system.system_uptime_seconds(5) == 120


def test_proc_uptime_answers_when_the_android_clock_is_missing(monkeypatch, platforms_detected):
    platforms_detected(["android", "linux"])
    monkeypatch.setattr(android, "system_uptime", lambda: 0)
    monkeypatch.setattr(linux, "system_uptime", lambda: 999)
    assert system.system_uptime_seconds(5) == 999


def test_boot_time_then_service_uptime_close_the_chain(monkeypatch, platforms_detected):
    platforms_detected(["macos"])
    monkeypatch.setattr(system.time, "time", lambda: 1000.0)
    monkeypatch.setattr(system.psutil, "boot_time", lambda: 400.0)
    assert system.system_uptime_seconds(5) == 600

    def broken():
        raise OSError("no boot time")
    monkeypatch.setattr(system.psutil, "boot_time", broken)
    assert system.system_uptime_seconds(5) == 5


def test_negative_answers_count_as_missing(monkeypatch, platforms_detected):
    platforms_detected(["linux"])
    monkeypatch.setattr(linux, "system_uptime", lambda: -3)
    monkeypatch.setattr(system.psutil, "boot_time", lambda: 0.0)
    monkeypatch.setattr(system.time, "time", lambda: 50.0)
    assert system.system_uptime_seconds(5) == 50
