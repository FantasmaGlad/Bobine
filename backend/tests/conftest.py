import os
import tempfile
from pathlib import Path

os.environ.setdefault("BOBINE_MDNS", "0")


def pytest_configure(config):
    if getattr(config.option, "basetemp", None) is None:
        config.option.basetemp = Path(tempfile.gettempdir()) / "pytest-bobine"


import pytest


@pytest.fixture(autouse=True)
def _no_pending_config_mirror():

    def cancel() -> None:
        from app import config_files

        with config_files._mirror_lock:
            timer, config_files._mirror_timer = config_files._mirror_timer, None
        if timer is not None:
            timer.cancel()

    cancel()
    yield
    cancel()
