import os
import tempfile
from pathlib import Path

os.environ.setdefault("BOBINE_MDNS", "0")


def pytest_configure(config):
    if getattr(config.option, "basetemp", None) is None:
        config.option.basetemp = Path(tempfile.gettempdir()) / "pytest-bobine"
    config.addinivalue_line("markers", "recent_stack: banc qui exige le client de test de Starlette recent")


def pytest_collection_modifyitems(config, items):
    import fastapi

    if tuple(int(part) for part in fastapi.__version__.split(".")[:2]) >= (0, 100):
        return
    skip = pytest.mark.skip(reason="client de test de Starlette trop ancien (profil Android)")
    for item in items:
        if "recent_stack" in item.keywords:
            item.add_marker(skip)


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
