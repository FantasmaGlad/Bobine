import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import os
import pytest  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.devices.service import DevicesService  # noqa: E402
from app.models import Setting  # noqa: E402
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
