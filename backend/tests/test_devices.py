"""Onglet « Périphériques » : analyseurs Linux, PIN/sessions/limitation d'essais, contrôle d'accès
du routeur, filet de sécurité Wi-Fi (retour automatique), sauvegarde sans l'empreinte du PIN.

Aucun matériel requis : le routeur est testé avec un pilote factice."""

import asyncio
import io
import json
import os
import sqlite3
import tempfile
import zipfile

# Base de test isolée AVANT tout import de l'application (comme les autres tests).
os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402
from app.devices import security  # noqa: E402
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

KEYS = (security.SETTING_ENABLED, security.SETTING_PIN_HASH)


# ---------------------------------------------------------------------------
# Analyseurs d'outils Linux
# ---------------------------------------------------------------------------

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
        " ::30:WPA2:2412 MHz",  # masqué : ignoré
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


# ---------------------------------------------------------------------------
# PIN, sessions, limitation d'essais
# ---------------------------------------------------------------------------


def test_pin_hash_never_contains_the_pin_and_verifies():
    stored = security.hash_pin("123456")
    assert "123456" not in stored and stored.startswith("scrypt$")
    assert security.verify_pin("123456", stored)
    assert not security.verify_pin("654321", stored)
    assert security.hash_pin("123456") != stored  # sel aléatoire par définition
    assert not security.verify_pin("123456", "n'importe quoi")
    assert not security.verify_pin("123456", None)


def test_pin_format():
    assert security.is_valid_pin("012345")
    assert not any(security.is_valid_pin(p) for p in ("12345", "1234567", "12a456", "", " 12345"))


def test_rate_limiter_locks_and_doubles():
    now = [0.0]
    limiter = security.RateLimiter(clock=lambda: now[0])
    ip = "10.0.0.9"
    assert [limiter.register_failure(ip) for _ in range(4)] == [0, 0, 0, 0]
    assert limiter.register_failure(ip) == 60
    assert limiter.retry_after(ip) > 0
    now[0] += 61
    assert limiter.retry_after(ip) == 0
    delays = [limiter.register_failure(ip) for _ in range(5)]
    assert delays[-1] == 120  # 1 min, puis 2 min
    now[0] += 200
    for _ in range(40):
        for _ in range(5):
            last = limiter.register_failure(ip)
        now[0] += 10_000
    assert last == security.LOCKOUT_MAX_SECONDS  # plafonné à 15 min
    limiter.register_success(ip)
    assert limiter.attempts_left(ip) == security.MAX_ATTEMPTS


def test_sessions_are_signed_ip_bound_and_sliding():
    now = [0.0]
    store = security.SessionStore(ttl=100, clock=lambda: now[0])
    token = store.create("10.0.0.2")
    assert store.validate(token, "10.0.0.2")
    assert not store.validate(token, "10.0.0.3")  # autre IP : session détruite
    assert not store.validate(token, "10.0.0.2")
    token = store.create("10.0.0.2")
    assert not store.validate(token[:-1] + ("0" if token[-1] != "0" else "1"), "10.0.0.2")  # signature altérée
    now[0] += 80
    assert store.validate(token, "10.0.0.2")  # glissante : prolongée
    now[0] += 80
    assert store.validate(token, "10.0.0.2")
    now[0] += 101
    assert not store.validate(token, "10.0.0.2")  # expirée
    other = store.create("10.0.0.2")
    store.revoke(other)
    assert not store.validate(other, "10.0.0.2")


def test_local_client_detection():
    assert security.is_local_client("127.0.0.1") and security.is_local_client("::1")
    assert security.is_local_client("::ffff:127.0.0.1")
    assert not security.is_local_client("203.0.113.7") and not security.is_local_client("testclient")
    assert not security.is_local_client(None)


# ---------------------------------------------------------------------------
# Routeur avec pilote factice
# ---------------------------------------------------------------------------


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
    init_db()  # tables garanties quel que soit l'ordre d'exécution des tests
    fake = FakeDriver()
    service.set_driver(fake)
    with SessionLocal() as db:
        db.query(Setting).filter(Setting.key.in_(KEYS)).delete(synchronize_session=False)
        db.commit()
    security.sessions.revoke_all()
    security.rate_limiter = security.RateLimiter()
    import app.routers.devices as devices_router
    devices_router.security.rate_limiter = security.rate_limiter
    yield fake
    service.confirm_wifi_change()
    service.set_driver(None)
    with SessionLocal() as db:
        db.query(Setting).filter(Setting.key.in_(KEYS)).delete(synchronize_session=False)
        db.commit()


@pytest.fixture()
def local(monkeypatch):
    monkeypatch.setattr("app.routers.devices.is_local_request", lambda request: True)


def remote(host="203.0.113.7"):
    return TestClient(app, client=(host, 50000))


def enable_with_pin(pin="123456", monkeypatch=None):
    client = TestClient(app)
    assert client.post("/api/devices/admin/enable", json={"enabled": True}).status_code == 200
    assert client.post("/api/devices/admin/pin", json={"pin": pin}).status_code == 200


def test_disabled_by_default_blocks_everything(driver, local):
    client = TestClient(app)
    status = client.get("/api/devices/status").json()
    assert status["enabled"] is False and status["access"] == "disabled" and "capabilities" not in status
    response = client.get("/api/devices/audio")
    assert response.status_code == 403 and response.json()["detail"]["code"] == "devices_disabled"


def test_remote_without_pin_is_refused_with_explanation(driver, local, monkeypatch):
    TestClient(app).post("/api/devices/admin/enable", json={"enabled": True})
    monkeypatch.undo()  # redevient « distant »
    response = remote().get("/api/devices/audio")
    assert response.status_code == 403 and response.json()["detail"]["code"] == "pin_not_set"
    assert remote().get("/api/devices/status").json()["access"] == "pin_not_set"


def test_pin_and_enable_are_local_only(driver):
    client = remote()
    assert client.post("/api/devices/admin/enable", json={"enabled": True}).json()["detail"]["code"] == "local_only"
    assert client.post("/api/devices/admin/pin", json={"pin": "123456"}).status_code == 403
    assert client.delete("/api/devices/admin/pin").status_code == 403


def test_pin_validation_and_storage(driver, local):
    client = TestClient(app)
    assert client.post("/api/devices/admin/pin", json={"pin": "12"}).json()["detail"]["code"] == "bad_pin"
    assert client.post("/api/devices/admin/pin", json={"pin": "123456"}).status_code == 200
    with SessionLocal() as db:
        stored = db.query(Setting).filter(Setting.key == security.SETTING_PIN_HASH).first().value
    assert "123456" not in stored
    # Jamais exposé par l'API des réglages.
    assert security.SETTING_PIN_HASH not in json.dumps(client.get("/api/settings").json())


def test_login_flow_cookie_and_lockout(driver, local, monkeypatch):
    enable_with_pin("123456")
    monkeypatch.undo()
    client = remote()
    assert client.get("/api/devices/audio").json()["detail"]["code"] == "pin_required"
    bad = client.post("/api/devices/session", json={"pin": "000000"})
    assert bad.status_code == 401 and bad.json()["detail"]["attempts_left"] == 4
    ok = client.post("/api/devices/session", json={"pin": "123456"})
    assert ok.status_code == 200
    cookie = ok.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api/devices" in cookie
    assert client.get("/api/devices/audio").status_code == 200
    assert client.get("/api/devices/status").json()["access"] == "granted"
    assert client.delete("/api/devices/session").status_code == 200
    assert client.get("/api/devices/audio").status_code == 401


def test_lockout_after_five_failures(driver, local, monkeypatch):
    enable_with_pin("123456")
    monkeypatch.undo()
    client = remote("203.0.113.50")
    codes = [client.post("/api/devices/session", json={"pin": "999999"}).status_code for _ in range(5)]
    assert codes == [401, 401, 401, 401, 429]
    locked = client.post("/api/devices/session", json={"pin": "123456"})  # même le bon PIN est refusé pendant le blocage
    assert locked.status_code == 429 and locked.headers["retry-after"]
    assert remote("203.0.113.51").post("/api/devices/session", json={"pin": "123456"}).status_code == 200  # autre IP


def test_session_is_bound_to_ip(driver, local, monkeypatch):
    enable_with_pin("123456")
    monkeypatch.undo()
    client = remote("203.0.113.60")
    client.post("/api/devices/session", json={"pin": "123456"})
    stolen = remote("203.0.113.61")
    stolen.cookies.set(security.SESSION_COOKIE, client.cookies.get(security.SESSION_COOKIE), path="/api/devices")
    assert stolen.get("/api/devices/audio").status_code == 401


def test_device_errors_become_structured_responses_never_500(driver, local):
    TestClient(app).post("/api/devices/admin/enable", json={"enabled": True})
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
        TestClient(app).post("/api/devices/admin/enable", json={"enabled": True})
        body = TestClient(app).get("/api/devices/audio").json()
        assert body == {"supported": False, "reason": "pas encore"}
        caps = TestClient(app).get("/api/devices/status").json()["capabilities"]
        assert all(not c["supported"] for c in caps.values())
    finally:
        service.set_driver(None)
        with SessionLocal() as db:
            db.query(Setting).filter(Setting.key.in_(KEYS)).delete(synchronize_session=False)
            db.commit()


def test_wifi_password_only_on_local_screen(driver, local, monkeypatch):
    enable_with_pin("123456")
    local_client = TestClient(app)
    ok = local_client.post("/api/devices/wifi/connect", json={"ssid": "Nouveau", "password": "secret-wifi"})
    assert ok.status_code == 200 and ok.json()["pending_change"]["seconds_left"] > 50
    assert ("connect", "Nouveau", "secret-wifi") in driver.calls
    # Le mot de passe n'apparaît nulle part dans le journal d'activité.
    from app.models import ActivityLog
    with SessionLocal() as db:
        details = " ".join(str(r.detail) for r in db.query(ActivityLog).filter(ActivityLog.event_type.like("devices_%")).all())
    assert "secret-wifi" not in details and "123456" not in details
    service.confirm_wifi_change()
    monkeypatch.undo()
    client = remote("10.0.5.5")
    client.post("/api/devices/session", json={"pin": "123456"})
    refused = client.post("/api/devices/wifi/connect", json={"ssid": "X", "password": "pw", "acknowledge_disconnect": True})
    assert refused.status_code == 403 and refused.json()["detail"]["code"] == "password_local_only"


def test_wifi_change_requires_ack_when_reached_through_wifi_and_confirm_clears(driver, local, monkeypatch):
    enable_with_pin("123456")
    monkeypatch.undo()
    client = remote("10.0.0.77")  # dans le sous-réseau du pilote factice
    client.post("/api/devices/session", json={"pin": "123456"})
    blocked = client.post("/api/devices/wifi/connect", json={"ssid": "Maison"})
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "ack_required"
    ok = client.post("/api/devices/wifi/connect", json={"ssid": "Autre", "acknowledge_disconnect": True})
    assert ok.status_code == 200
    assert client.post("/api/devices/wifi/connect", json={"ssid": "Encore", "acknowledge_disconnect": True}).json()["detail"]["code"] == "change_pending"
    assert client.get("/api/devices/wifi").json()["pending_change"]["target"] == "Autre"
    assert client.post("/api/devices/wifi/confirm").json() == {"confirmed": True}
    assert client.get("/api/devices/wifi").json()["pending_change"] is None
    outside = remote("198.51.100.4")  # hors du sous-réseau Wi-Fi : pas de confirmation préalable exigée
    outside.post("/api/devices/session", json={"pin": "123456"})
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
        assert fake.calls == []  # confirmé : aucun retour arrière

        svc.arm_wifi_rollback("power_off", None, "Wi-Fi", seconds=0.05)
        await asyncio.sleep(0.15)
        assert ("power", True) in fake.calls  # coupure non confirmée : le Wi-Fi est rallumé

    asyncio.run(scenario())


def test_backup_never_contains_the_pin_hash(driver, local):
    enable_with_pin("123456")
    with SessionLocal() as db:
        assert db.query(Setting).filter(Setting.key == security.SETTING_PIN_HASH).first() is not None
    response = TestClient(app).get("/api/settings/backup/export")
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        db_bytes = zf.read("database.db")
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        tmp.write(db_bytes)
        tmp.flush()
        con = sqlite3.connect(tmp.name)
        keys = {row[0] for row in con.execute("SELECT key FROM settings")}
        con.close()
    assert security.SETTING_PIN_HASH not in keys
    assert b"scrypt$" not in db_bytes  # purgé physiquement (VACUUM), pas seulement logiquement
    # La base vivante, elle, garde l'empreinte.
    with SessionLocal() as db:
        assert db.query(Setting).filter(Setting.key == security.SETTING_PIN_HASH).first() is not None


def test_event_is_a_data_free_signal(monkeypatch):
    sent = []
    monkeypatch.setattr("app.devices.service.ws_manager.broadcast_threadsafe", lambda message: sent.append(message))
    svc = DevicesService(driver_factory=lambda: FakeDriver())
    svc.notify("wifi")
    svc.notify("wifi")  # rafale : dédoublonnée
    assert sent == [{"event": "devices_changed", "scope": "wifi"}]


def test_system_settings_and_permission_routes(driver, local):
    TestClient(app).post("/api/devices/admin/enable", json={"enabled": True})
    client = TestClient(app)
    assert client.post("/api/devices/system-settings", json={"target": "rm -rf"}).json()["detail"]["code"] == "bad_target"
    unsupported = client.post("/api/devices/system-settings", json={"target": "wifi"})
    assert unsupported.status_code == 501 and unsupported.json()["detail"]["code"] == "unsupported"
    assert client.post("/api/devices/bluetooth/permission").status_code == 200  # no-op par défaut
