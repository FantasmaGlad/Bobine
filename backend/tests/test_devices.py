import io
import os
import sqlite3
import tempfile
import zipfile

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal, init_db
from app.database.migrations import migrate_drop_devices_access_settings
from app.devices import locality
from app.devices.base import DeviceDriver, DeviceError, NullDriver
from app.devices.linux.parse.audio import audio_kind, parse_pw_dump, parse_wpctl_volume
from app.devices.linux.parse.bluetooth import bluez_device_path, is_valid_mac, parse_bluez_objects
from app.devices.service import DevicesService, service
from app.main import app
from app.models import Setting


PW_DUMP = [
    {"id": 41, "type": "PipeWire:Interface:Device", "info": {"props": {
        "device.description": "Ryzen HD Audio", "device.bus": "pci", "device.api": "alsa", "device.form-factor": "internal"}}},
    {"id": 42, "type": "PipeWire:Interface:Device", "info": {"props": {
        "device.description": "JBL Live", "device.api": "bluez5", "device.bus": "bluetooth"}}},
    {"id": 43, "type": "PipeWire:Interface:Device", "info": {"props": {
        "device.description": "Écran HDMI", "device.api": "alsa", "device.bus": "pci", "device.profile.name": "hdmi-stereo"}}},
    {"id": 51, "type": "PipeWire:Interface:Node", "info": {"props": {
        "media.class": "Audio/Sink", "node.name": "alsa_output.speaker", "node.description": "Haut-parleurs", "device.id": 41}}},
    {"id": 52, "type": "PipeWire:Interface:Node", "info": {"props": {
        "media.class": "Audio/Sink", "node.name": "bluez_output.88_92", "node.description": "JBL Live 770NC", "device.id": 42}}},
    {"id": 53, "type": "PipeWire:Interface:Node", "info": {"props": {
        "media.class": "Audio/Sink", "node.name": "alsa_output.hdmi", "node.description": "HDMI / DP", "device.id": 43}}},
    {"id": 54, "type": "PipeWire:Interface:Node", "info": {"props": {"media.class": "Audio/Source", "node.name": "micro"}}},
    {"id": 60, "type": "PipeWire:Interface:Metadata", "metadata": [
        {"subject": 0, "key": "default.audio.sink", "type": "Spa:String:JSON", "value": {"name": "bluez_output.88_92"}}]},
]


def test_parse_pw_dump_lists_sinks_with_kind_and_default():
    data = parse_pw_dump(PW_DUMP)
    assert [s["id"] for s in data["sinks"]] == ["alsa_output.speaker", "bluez_output.88_92", "alsa_output.hdmi"]
    kinds = {s["id"]: s["kind"] for s in data["sinks"]}
    assert kinds == {"alsa_output.speaker": "internal", "bluez_output.88_92": "bluetooth", "alsa_output.hdmi": "hdmi"}
    assert data["default_id"] == "bluez_output.88_92"
    assert [s["id"] for s in data["sinks"] if s["is_default"]] == ["bluez_output.88_92"]


def test_audio_kind_usb_and_jack():
    assert audio_kind({"node.name": "alsa_output.usb-dac"}, {"device.bus": "usb", "device.api": "alsa"}) == "usb"
    assert audio_kind({"node.name": "x"}, {"device.api": "alsa", "device.form-factor": "headphones"}) == "jack"


def test_parse_wpctl_volume():
    assert parse_wpctl_volume("Volume: 0.40") == (0.4, False)
    assert parse_wpctl_volume("Volume: 1.00 [MUTED]") == (1.0, True)
    assert parse_wpctl_volume("n'importe quoi") == (None, None)


def test_parse_bluez_objects():
    objects = {
        "/org/bluez/hci0": {"org.bluez.Adapter1": {"Powered": True, "Discovering": False, "Alias": "pc"}},
        "/org/bluez/hci0/dev_88_92_CC_9C_41_0E": {
            "org.bluez.Device1": {
                "Adapter": "/org/bluez/hci0", "Address": "88:92:CC:9C:41:0E", "Alias": "JBL", "Paired": True,
                "Connected": True, "Trusted": True, "Icon": "audio-headset", "RSSI": -50,
                "UUIDs": ["0000110b-0000-1000-8000-00805f9b34fb", "0000111e-0000-1000-8000-00805f9b34fb"],
            },
            "org.bluez.Battery1": {"Percentage": 80},
        },
        "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF": {
            "org.bluez.Device1": {"Adapter": "/org/bluez/hci0", "Address": "AA:BB:CC:DD:EE:FF", "Name": "Inconnu"}},
    }
    snap = parse_bluez_objects(objects)
    assert snap["powered"] is True and snap["adapter_path"] == "/org/bluez/hci0"
    first = snap["devices"][0]
    assert first["address"] == "88:92:CC:9C:41:0E" and first["connected"] and first["kind"] == "headset"
    assert first["profiles"] == ["A2DP", "HFP"] and first["battery"] == 80
    assert snap["devices"][1]["name"] == "Inconnu" and not snap["devices"][1]["paired"]


def test_bluetooth_address_helpers():
    assert is_valid_mac("AA:BB:CC:DD:EE:FF") and not is_valid_mac("zz") and not is_valid_mac("AA:BB")
    assert bluez_device_path("/org/bluez/hci0", "aa:bb:cc:dd:ee:ff") == "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"


def test_local_client_detection():
    assert locality.is_local_client("127.0.0.1") and locality.is_local_client("::1")
    assert locality.is_local_client("::ffff:127.0.0.1")
    assert not locality.is_local_client("203.0.113.7") and not locality.is_local_client("testclient")
    assert not locality.is_local_client(None)


@pytest.mark.recent_stack
def test_remote_client_reads_status_without_cookie(driver):
    response = remote("192.168.1.42").get("/api/devices/status")
    assert response.status_code == 200
    assert "set-cookie" not in response.headers
    body = response.json()
    assert body["local"] is False
    assert set(body) == {"local", "platform", "driver", "capabilities"}
    assert "pin_set" not in body and "access" not in body


class FakeDriver(DeviceDriver):
    name = "fake"

    def __init__(self):
        super().__init__()
        self.calls: list[tuple] = []
        self.fail_with: Exception | None = None

    async def capabilities(self):
        return {"audio_list": {"supported": True}}

    async def audio_list(self):
        if self.fail_with:
            raise self.fail_with
        return {"supported": True, "devices": [{"id": "hp", "name": "HP", "kind": "internal", "is_default": True}], "default_id": "hp"}

    async def audio_set_default(self, device_id):
        self.calls.append(("default", device_id))

    async def bluetooth_status(self):
        return {"supported": True, "powered": True, "discovering": False, "devices": [], "pending_pairing": None}



@pytest.fixture()
def driver():
    init_db()
    fake = FakeDriver()
    service.set_driver(fake)
    yield fake
    service.set_driver(None)


@pytest.fixture()
def local(monkeypatch):
    monkeypatch.setattr("app.api.routes.devices.access.is_local_request", lambda request: True)


def remote(host="192.168.1.7"):
    return TestClient(app, client=(host, 50000))


def test_device_errors_become_structured_responses_never_500(driver, local):
    client = TestClient(app)
    driver.fail_with = DeviceError("tool_missing", "Outil introuvable", 501)
    response = client.get("/api/devices/audio")
    assert response.status_code == 501 and response.json()["detail"] == {"code": "tool_missing", "message": "Outil introuvable"}
    driver.fail_with = RuntimeError("boum")
    response = client.get("/api/devices/audio")
    assert response.status_code == 502 and response.json()["detail"]["code"] == "driver_error"


def test_null_driver_reports_unsupported(local):
    init_db()
    service.set_driver(NullDriver("pas encore"))
    try:
        body = TestClient(app).get("/api/devices/audio").json()
        assert body == {"supported": False, "reason": "pas encore"}
        caps = TestClient(app).get("/api/devices/status").json()["capabilities"]
        assert all(not c["supported"] for c in caps.values())
    finally:
        service.set_driver(None)


def test_backup_keeps_settings_unchanged():
    init_db()
    with SessionLocal() as db:
        db.merge(Setting(key="test_backup_probe", value="conservé"))
        db.commit()
    try:
        response = TestClient(app).get("/api/settings/backup/export")
        assert response.status_code == 200
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            db_bytes = zf.read("database.db")
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            tmp.write(db_bytes)
            tmp.flush()
            con = sqlite3.connect(tmp.name)
            rows = dict(con.execute("SELECT key, value FROM settings"))
            con.close()
        assert rows.get("test_backup_probe") == "conservé"
    finally:
        with SessionLocal() as db:
            db.query(Setting).filter(Setting.key == "test_backup_probe").delete()
            db.commit()


def test_migration_drops_devices_access_settings():
    init_db()
    with SessionLocal() as db:
        db.merge(Setting(key="devices_pin_hash", value="scrypt$sel$empreinte"))
        db.merge(Setting(key="devices_enabled", value="true"))
        db.commit()
    migrate_drop_devices_access_settings()
    with SessionLocal() as db:
        remaining = {row.key for row in db.query(Setting).filter(
            Setting.key.in_(("devices_pin_hash", "devices_enabled"))
        ).all()}
    assert remaining == set()
    migrate_drop_devices_access_settings()


def test_event_is_a_data_free_signal(monkeypatch):
    sent = []
    monkeypatch.setattr("app.devices.service.ws_manager.broadcast_threadsafe", lambda message: sent.append(message))
    svc = DevicesService(driver_factory=lambda: FakeDriver())
    svc.notify("bluetooth")
    svc.notify("bluetooth")
    assert sent == [{"event": "devices_changed", "scope": "bluetooth"}]


def test_system_settings_and_permission_routes(driver, local):
    client = TestClient(app)
    assert client.post("/api/devices/system-settings", json={"target": "rm -rf"}).json()["detail"]["code"] == "bad_target"
    assert client.post("/api/devices/system-settings", json={"target": "wifi"}).json()["detail"]["code"] == "bad_target"
    unsupported = client.post("/api/devices/system-settings", json={"target": "bluetooth"})
    assert unsupported.status_code == 501 and unsupported.json()["detail"]["code"] == "unsupported"
    assert client.post("/api/devices/bluetooth/permission").status_code == 200
