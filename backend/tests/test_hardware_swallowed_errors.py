import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.hardware.power import watts
from app.hardware.disk import usage


def _boom(*_args, **_kwargs):
    raise OSError("unreadable")


def test_unreadable_disk_usage_is_logged(monkeypatch, caplog):
    monkeypatch.setattr(shutil, "disk_usage", _boom)
    with caplog.at_level("WARNING", logger=usage.logger.name):
        assert usage.get_storage_usage()["total_bytes"] == 0
    assert "unreadable" in caplog.text


def test_failing_power_probe_is_logged(monkeypatch, caplog):
    def fallback():
        return 7.0

    monkeypatch.setattr(watts, "_power_probes", lambda: [_boom, fallback])
    with caplog.at_level("DEBUG", logger=watts.logger.name):
        assert watts.get_power_watts() == 7.0
    assert "_boom" in caplog.text and "unreadable" in caplog.text
