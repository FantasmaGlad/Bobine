import asyncio
import io
import os
import sqlite3
import tempfile
import zipfile

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal, _migrate_drop_devices_access_settings, init_db  # noqa: E402
from app.devices import locality  # noqa: E402
from app.devices.base import DeviceDriver, DeviceError, NullDriver  # noqa: E402
from app.devices.linux_parse import (  # noqa: E402
    audio_kind,
    bluez_device_path,
    is_valid_mac,
    parse_bluez_objects,
    parse_known_wifi,
    parse_pw_dump,
    parse_wifi_device,
    parse_wifi_list,
    parse_wpctl_volume,
    split_terse,
    wifi_band,
)
from app.devices.service import DevicesService, service  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Setting  # noqa: E402


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


def test_split_terse_handles_escaped_colons():
    assert split_terse(r"*:Mon\:Wifi:82:WPA2:5180 MHz") == ["*", "Mon:Wifi", "82", "WPA2", "5180 MHz"]
    assert split_terse(r"a\\b:c") == ["a\\b", "c"]


def test_parse_wifi_list_dedupes_and_marks_known():
    out = "\n".join([
        "*:Livebox:76:WPA2:5180 MHz",
        " :Livebox:40:WPA2:2412 MHz",
        " :Voisin:55:WPA2 WPA3:2437 MHz",
        " ::30:WPA2:2412 MHz",
        " :Cafe:20:--:2412 MHz",
    ])
    networks = parse_wifi_list(out, {"Livebox"})
    assert [n["ssid"] for n in networks] == ["Livebox", "Voisin", "Cafe"]
    assert networks[0]["in_use"] and networks[0]["known"] and networks[0]["signal"] == 76 and networks[0]["band"] == "5 GHz"
    assert networks[2]["security"] == ""
    assert wifi_band("6000 MHz") == "6 GHz" and wifi_band("2412 MHz") == "2.4 GHz"


def test_parse_known_wifi_and_device():
    known = parse_known_wifi("Livebox:uuid1:802-11-wireless\nWired:uuid2:802-3-ethernet\nFanta:uuid3:802-11-wireless")
    assert [k["name"] for k in known] == ["Livebox", "Fanta"]
    device = parse_wifi_device("lo:loopback:connected (externally):\nwlo1:wifi:connected:Livebox")
    assert device == {"device": "wlo1", "state": "connected", "connection": "Livebox"}
    assert parse_wifi_device("eth0:ethernet:connected:Wired") is None


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
    assert set(body) == {"local", "platform", "driver", "wifi_confirm_seconds", "capabilities"}
    assert "pin_set" not in body and "access" not in body


class FakeDriver(DeviceDriver):
    name = "fake"

    def __init__(self):
        super().__init__()
        self.calls: list[tuple] = []
        self.current = "Maison"
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

    async def wifi_status(self):
        return {"supported": True, "enabled": True, "interface": "wlan0", "current": None, "networks": [], "known": ["Maison"]}

    async def wifi_current_connection(self):
        return self.current

    async def wifi_connect(self, ssid, password):
        self.calls.append(("connect", ssid, password))
        self.current = ssid

    async def wifi_activate(self, connection):
        self.calls.append(("activate", connection))
        self.current = connection

    async def wifi_set_power(self, on):
        self.calls.append(("power", on))

    async def wifi_interface_subnet(self):
        return "10.0.0.0/24"

    async def wifi_forget(self, ssid):
        self.calls.append(("forget", ssid))


@pytest.fixture()
def driver():
    init_db()
    fake = FakeDriver()
    service.set_driver(fake)
    yield fake
    service.confirm_wifi_change()
    service.set_driver(None)


@pytest.fixture()
def local(monkeypatch):
    monkeypatch.setattr("app.api.routes.devices.is_local_request", lambda request: True)


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


@pytest.mark.recent_stack
def test_wifi_password_only_on_local_screen(driver, local, monkeypatch):
    local_client = TestClient(app)
    ok = local_client.post("/api/devices/wifi/connect", json={"ssid": "Nouveau", "password": "secret-wifi"})
    assert ok.status_code == 200 and ok.json()["pending_change"]["seconds_left"] > 50
    assert ("connect", "Nouveau", "secret-wifi") in driver.calls
    from app.models import ActivityLog
    with SessionLocal() as db:
        details = " ".join(str(r.detail) for r in db.query(ActivityLog).filter(ActivityLog.event_type.like("devices_%")).all())
    assert "secret-wifi" not in details
    service.confirm_wifi_change()
    monkeypatch.undo()
    client = remote("10.0.5.5")
    refused = client.post("/api/devices/wifi/connect", json={"ssid": "X", "password": "pw", "acknowledge_disconnect": True})
    assert refused.status_code == 403 and refused.json()["detail"]["code"] == "password_local_only"


@pytest.mark.recent_stack
def test_wifi_change_requires_ack_when_reached_through_wifi_and_confirm_clears(driver, local, monkeypatch):
    monkeypatch.undo()
    client = remote("10.0.0.77")
    blocked = client.post("/api/devices/wifi/connect", json={"ssid": "Maison"})
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "ack_required"
    ok = client.post("/api/devices/wifi/connect", json={"ssid": "Autre", "acknowledge_disconnect": True})
    assert ok.status_code == 200
    assert client.post("/api/devices/wifi/connect", json={"ssid": "Encore", "acknowledge_disconnect": True}).json()["detail"]["code"] == "change_pending"
    assert client.get("/api/devices/wifi").json()["pending_change"]["target"] == "Autre"
    assert client.post("/api/devices/wifi/confirm").json() == {"confirmed": True}
    assert client.get("/api/devices/wifi").json()["pending_change"] is None
    outside = remote("10.9.9.4")
    assert outside.post("/api/devices/wifi/connect", json={"ssid": "Maison"}).status_code == 200


def test_wifi_rollback_restores_previous_connection_when_not_confirmed():
    async def scenario():
        fake = FakeDriver()
        svc = DevicesService(driver_factory=lambda: fake)
        fake.current = "Maison"
        await fake.wifi_connect("Autre", None)
        svc.arm_wifi_rollback("connect", "Maison", "Autre", seconds=0.05)
        assert svc.wifi_pending_info() is not None
        await asyncio.sleep(0.2)
        assert ("activate", "Maison") in fake.calls and fake.current == "Maison"
        assert svc.wifi_pending is None

        fake.calls.clear()
        svc.arm_wifi_rollback("connect", "Maison", "Autre", seconds=0.05)
        assert svc.confirm_wifi_change() is True
        await asyncio.sleep(0.15)
        assert fake.calls == []

        svc.arm_wifi_rollback("power_off", None, "Wi-Fi", seconds=0.05)
        await asyncio.sleep(0.15)
        assert ("power", True) in fake.calls

    asyncio.run(scenario())


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
    _migrate_drop_devices_access_settings()
    with SessionLocal() as db:
        remaining = {row.key for row in db.query(Setting).filter(
            Setting.key.in_(("devices_pin_hash", "devices_enabled"))
        ).all()}
    assert remaining == set()
    _migrate_drop_devices_access_settings()


def test_event_is_a_data_free_signal(monkeypatch):
    sent = []
    monkeypatch.setattr("app.devices.service.ws_manager.broadcast_threadsafe", lambda message: sent.append(message))
    svc = DevicesService(driver_factory=lambda: FakeDriver())
    svc.notify("wifi")
    svc.notify("wifi")
    assert sent == [{"event": "devices_changed", "scope": "wifi"}]


def test_system_settings_and_permission_routes(driver, local):
    client = TestClient(app)
    assert client.post("/api/devices/system-settings", json={"target": "rm -rf"}).json()["detail"]["code"] == "bad_target"
    unsupported = client.post("/api/devices/system-settings", json={"target": "wifi"})
    assert unsupported.status_code == 501 and unsupported.json()["detail"]["code"] == "unsupported"
    assert client.post("/api/devices/bluetooth/permission").status_code == 200
