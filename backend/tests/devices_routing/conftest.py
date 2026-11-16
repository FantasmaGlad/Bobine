import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import asyncio
import json
import os
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.devices.base import CAPABILITY_KEYS, DeviceDriver, DeviceError, NullDriver  # noqa: E402
from app.devices.linux.driver import LinuxDriver  # noqa: E402
from app.devices.linux.parse.audio import choose_browser_stream, parse_output_streams  # noqa: E402
from app.devices.routing import (  # noqa: E402
    ROUTES_SETTING,
    describe_sink,
    load_routes,
    load_routes_into_managers,
    normalize_label,
    player_route_state,
    resolve_route,
    sanitize_routes,
    save_routes,
    stable_sink_key,
)
from app.devices.service import PLAYER_ROUTE_STATUSES, DevicesService, service  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Setting  # noqa: E402
from app.radio_manager import get_radio_manager  # noqa: E402
from devices_routing_support import KEYS, RoutingDriver, _reset_managers


@pytest.fixture()
def pw_tools(monkeypatch):
    monkeypatch.setattr("app.devices.linux.driver.shutil.which", lambda name: f"/usr/bin/{name}")


@pytest.fixture()
def routing_env():
    init_db()
    with SessionLocal() as db:
        db.query(Setting).filter(Setting.key.in_(KEYS)).delete(synchronize_session=False)
        db.commit()
    _reset_managers()
    driver = RoutingDriver()
    fresh = DevicesService(driver_factory=lambda: driver)
    fresh.set_driver(driver)
    yield fresh, driver
    _reset_managers()
    with SessionLocal() as db:
        db.query(Setting).filter(Setting.key.in_(KEYS)).delete(synchronize_session=False)
        db.commit()
    from app.utils.ws_manager import manager as ws

    ws._kiosk_connections["radio_cable"].clear()  # noqa: SLF001
    ws._kiosk_connections["radio_network"].clear()  # noqa: SLF001
    ws._route_reports.clear()  # noqa: SLF001


@pytest.fixture()
def api(routing_env, monkeypatch):
    fresh, driver = routing_env
    from app.devices import service as service_module
    import app.api.routes.devices as devices_routes
    import app.api.routes.devices.radio as radio_routes

    monkeypatch.setattr(devices_routes, "service", fresh)
    monkeypatch.setattr(radio_routes, "service", fresh)
    monkeypatch.setattr(service_module, "service", fresh)
    return fresh, driver
