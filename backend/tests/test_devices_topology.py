"""Carte des périphériques : construction du graphe (pure), moyen de liaison des clients, spectateurs WebSocket."""

import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402
from app.devices.base import DeviceDriver  # noqa: E402
from app.devices.service import service  # noqa: E402
from app.devices.topology import build_topology, client_medium, ethernet_interfaces  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Setting  # noqa: E402
from app.utils.ws_manager import ConnectionManager  # noqa: E402

AUDIO = {"supported": True, "devices": [
    {"id": "spk", "name": "Haut-parleurs", "kind": "internal", "is_default": True, "volume": 0.5, "muted": False},
    {"id": "hdmi", "name": "HDMI", "kind": "hdmi", "is_default": False, "alias": "Projecteur"},
    {"id": "jbl", "name": "JBL Live", "kind": "bluetooth", "is_default": False},
    {"id": "old", "name": "Masquée", "kind": "usb", "hidden": True},
]}
BLUETOOTH = {"supported": True, "devices": [
    {"address": "AA:BB:CC:DD:EE:01", "name": "JBL Live", "paired": True, "connected": True, "kind": "headset", "profiles": ["A2DP"], "battery": 80},
    {"address": "AA:BB:CC:DD:EE:02", "name": "Clavier", "paired": True, "connected": False, "kind": "keyboard", "profiles": [], "battery": None},
    {"address": "AA:BB:CC:DD:EE:03", "name": "Passant", "paired": False, "connected": False, "kind": "other", "profiles": [], "battery": None},
]}
WIFI = {"supported": True, "current": {"ssid": "Livebox", "signal": 80, "ip": "192.168.1.17", "band": "5 GHz", "security": "WPA2"}}


def graph(**over):
    args = dict(
        machine={"name": "wyse", "platform": "linux-headless"}, audio=AUDIO, bluetooth=BLUETOOTH, wifi=WIFI, wifi_subnet="192.168.1.0/24",
        ethernets=[{"name": "eth0", "ip": "10.0.0.5", "subnet": "10.0.0.0/24", "speed": 1000}],
        clients=[
            {"channel": "cable", "page": "kiosk", "role": "primary", "ip": "127.0.0.1", "count": 1},
            {"channel": "network", "page": "cinema", "role": "viewer", "ip": "192.168.1.60", "count": 2},
            {"channel": "cable", "page": "dashboard", "role": "viewer", "ip": "10.0.0.9", "count": 1},
            {"channel": "network", "page": "kiosk", "role": "primary", "ip": "172.16.5.4", "count": 1},
        ],
        own_ips=frozenset({"192.168.1.17", "10.0.0.5"}),
    )
    args.update(over)
    return build_topology(**args)


def by_id(g):
    return {n["id"]: n for n in g["nodes"]}


def test_machine_at_the_center_with_every_source():
    g = graph()
    nodes = by_id(g)
    assert nodes["machine"]["ring"] == 0 and nodes["machine"]["label"] == "wyse"
    assert {"wifi", "eth:eth0", "bt:AA:BB:CC:DD:EE:01", "bt:AA:BB:CC:DD:EE:02", "audio:spk", "audio:hdmi"} <= set(nodes)
    assert "bt:AA:BB:CC:DD:EE:03" not in nodes  # appareil à portée non appairé : pas sur la carte
    assert "audio:old" not in nodes  # sortie masquée
    assert nodes["audio:hdmi"]["label"] == "Projecteur"  # alias
    assert all(link["from"] in nodes and link["to"] in nodes for link in g["links"])
    assert len({link["id"] for link in g["links"]}) == len(g["links"])


def test_link_mediums_match_the_requested_styles():
    g = graph()
    mediums = {link["to"]: link["medium"] for link in g["links"]}
    assert mediums["wifi"] == "wifi" and mediums["eth:eth0"] == "wired"
    assert mediums["bt:AA:BB:CC:DD:EE:01"] == "bluetooth"
    assert mediums["audio:hdmi"] == "wired" and mediums["audio:spk"] == "internal"
    states = {link["to"]: link["state"] for link in g["links"]}
    assert states["bt:AA:BB:CC:DD:EE:01"] == "active" and states["bt:AA:BB:CC:DD:EE:02"] == "idle"


def test_bluetooth_headset_is_not_duplicated_as_an_audio_node():
    g = graph()
    nodes = by_id(g)
    assert "audio:jbl" not in nodes
    assert nodes["bt:AA:BB:CC:DD:EE:01"]["meta"]["audio_id"] == "jbl"


def test_clients_medium_and_anchor():
    g = graph()
    clients = [n for n in g["nodes"] if n["kind"] in ("screen", "remote")]
    assert {(n["meta"]["page"], n["meta"]["medium"]) for n in clients} == {("kiosk", "local"), ("cinema", "wifi"), ("dashboard", "wired"), ("kiosk", "lan")}
    link_for = {link["to"]: link for link in g["links"]}
    kinds = {n["meta"]["ip"]: n["kind"] for n in clients}
    assert kinds["10.0.0.9"] == "remote" and kinds["192.168.1.60"] == "screen"
    wifi_client = next(n for n in clients if n["meta"]["ip"] == "192.168.1.60")
    assert link_for[wifi_client["id"]]["from"] == "wifi" and link_for[wifi_client["id"]]["medium"] == "wifi"  # via le point d'accès
    eth_client = next(n for n in clients if n["meta"]["ip"] == "10.0.0.9")
    assert link_for[eth_client["id"]]["from"] == "eth:eth0"
    local = next(n for n in clients if n["meta"]["ip"] == "127.0.0.1")
    assert (link_for[local["id"]]["from"], link_for[local["id"]]["medium"]) == ("machine", "wired")
    unknown = next(n for n in clients if n["meta"]["ip"] == "172.16.5.4")
    assert (link_for[unknown["id"]]["from"], link_for[unknown["id"]]["medium"]) == ("machine", "lan")
    assert next(n for n in clients if n["meta"]["ip"] == "192.168.1.60")["meta"]["count"] == 2


def test_client_medium_rules():
    own = frozenset({"192.168.1.17"})
    assert client_medium("127.0.0.1", own, None, []) == "local"
    assert client_medium("192.168.1.17", own, "192.168.1.0/24", []) == "local"  # adresse de la machine elle-même
    assert client_medium("192.168.1.50", own, "192.168.1.0/24", []) == "wifi"
    assert client_medium("10.1.1.1", own, "192.168.1.0/24", ["10.1.1.0/24"]) == "wired"
    assert client_medium("8.8.8.8", own, "192.168.1.0/24", ["10.1.1.0/24"]) == "lan"
    assert client_medium("pas-une-ip", own, None, []) == "lan"


def test_degrades_when_sources_are_missing():
    g = graph(audio=None, bluetooth={"supported": False}, wifi=None, ethernets=[], clients=[], wifi_subnet=None)
    assert [n["id"] for n in g["nodes"]] == ["machine"] and g["links"] == []
    assert g["counts"] == {"audio": 0, "bluetooth": 0, "screens": 0}


def test_ethernet_helper_ignores_virtual_and_wifi_interfaces():
    names = {e["name"] for e in ethernet_interfaces("wlo1")}
    assert not any(n.startswith(("lo", "docker", "veth", "virbr", "lxc", "wlo1")) for n in names)


# ---------------------------------------------------------------------------
# Spectateurs WebSocket et route
# ---------------------------------------------------------------------------


class FakeWS:
    def __init__(self, ip):
        self.client = type("C", (), {"host": ip})()


def test_ws_manager_snapshot_groups_kiosks_and_viewers():
    manager = ConnectionManager()
    import asyncio

    async def scenario():
        a, b, v1, v2 = FakeWS("127.0.0.1"), FakeWS("127.0.0.1"), FakeWS("192.168.1.60"), FakeWS("192.168.1.60")
        await manager.register_kiosk(a, "cable", "k1")
        manager.set_kiosk_page(a, "kiosk")
        await manager.register_kiosk(b, "radio_network", "k2")
        manager.register_viewer(v1, "network", "cinema")
        manager.register_viewer(v2, "network", "cinema")
        manager.register_viewer(FakeWS("10.0.0.2"), "inconnu", "dashboard")  # canal invalide : retombe sur câblé
        return manager.client_snapshot()

    snap = asyncio.run(scenario())
    assert {"channel": "network", "page": "cinema", "role": "viewer", "ip": "192.168.1.60", "count": 2} in snap
    assert {"channel": "cable", "page": "kiosk", "role": "primary", "ip": "127.0.0.1", "count": 1} in snap
    assert {"channel": "radio_network", "page": "radio", "role": "primary", "ip": "127.0.0.1", "count": 1} in snap  # page par défaut d'une sortie radio
    assert any(e["channel"] == "cable" and e["page"] == "dashboard" and e["role"] == "viewer" for e in snap)


class FakeDriver(DeviceDriver):
    name = "fake"

    async def capabilities(self):
        return {}

    async def audio_list(self):
        return AUDIO

    async def bluetooth_status(self):
        return BLUETOOTH

    async def wifi_status(self):
        return {**WIFI, "interface": "wlan0"}

    async def wifi_interface_subnet(self):
        return "192.168.1.0/24"


@pytest.fixture()
def api(monkeypatch):
    init_db()
    service.set_driver(FakeDriver())
    monkeypatch.setattr("app.routers.devices.is_local_request", lambda request: True)
    with SessionLocal() as db:
        db.query(Setting).filter(Setting.key.in_(("devices_enabled", "devices_audio_meta"))).delete(synchronize_session=False)
        db.add(Setting(key="devices_enabled", value="true"))
        db.commit()
    yield TestClient(app)
    service.set_driver(None)
    with SessionLocal() as db:
        db.query(Setting).filter(Setting.key.in_(("devices_enabled", "devices_audio_meta"))).delete(synchronize_session=False)
        db.commit()


def test_topology_route_and_viewer_identify(api):
    with api.websocket_connect("/ws/playback") as ws:
        ws.send_json({"command": "identify", "params": {"role": "viewer", "channel": "network", "page": "cinema"}})
        ws.send_json({"command": "pong"})
        body = api.get("/api/devices/topology").json()
    ids = {n["id"] for n in body["nodes"]}
    assert {"machine", "wifi", "audio:spk", "bt:AA:BB:CC:DD:EE:01"} <= ids
    assert any(n["kind"] == "screen" and n["meta"]["page"] == "cinema" for n in body["nodes"])
    # Un spectateur n'a aucun effet sur le rôle primaire du canal.
    from app.utils.ws_manager import manager

    assert manager.kiosk_count("network") == 0


def test_topology_requires_access(monkeypatch):
    init_db()
    with SessionLocal() as db:
        db.query(Setting).filter(Setting.key == "devices_enabled").delete(synchronize_session=False)
        db.commit()
    assert TestClient(app).get("/api/devices/topology").status_code == 403
