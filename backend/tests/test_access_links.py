import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import asyncio  # noqa: E402
import socket  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.utils import network, port80  # noqa: E402
from app.utils.deployment import ProfileHandler  # noqa: E402
from app.utils.network import LanAddress  # noqa: E402


@pytest.mark.parametrize(
    "host, target, expected",
    [
        ("bobine.local", "/kiosk/?channel=cable", "http://bobine.local:1903/kiosk/?channel=cable"),
        ("bobine.local:80", "/", "http://bobine.local:1903/"),
        ("192.168.1.20", "/settings/", "http://192.168.1.20:1903/settings/"),
        ("[fe80::1]", "/", "http://[fe80::1]:1903/"),
        ("", "*", "http://bobine.local:1903/"),
    ],
)
def test_redirect_location_keeps_host_path_and_query(host, target, expected):
    assert port80.redirect_location(host, target, 1903) == expected


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_listener_answers_a_temporary_redirect(monkeypatch):
    monkeypatch.setattr(port80, "REDIRECT_PORT", _free_port())

    async def scenario() -> bytes:
        assert await port80.start(1903)
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port80.REDIRECT_PORT)
            writer.write(b"GET /radio/?channel=cable HTTP/1.1\r\nHost: bobine.local\r\n\r\n")
            await writer.drain()
            answer = await reader.read()
            writer.close()
            return answer
        finally:
            await port80.stop()

    answer = asyncio.run(scenario())
    assert answer.startswith(b"HTTP/1.1 307 ")
    assert b"Location: http://bobine.local:1903/radio/?channel=cable\r\n" in answer
    assert not port80.is_active()


def test_occupied_port_is_left_alone(monkeypatch):
    with socket.socket() as busy:
        busy.bind(("0.0.0.0", 0))
        busy.listen(1)
        monkeypatch.setattr(port80, "REDIRECT_PORT", busy.getsockname()[1])
        assert asyncio.run(port80.start(1903)) is False
    assert not port80.is_active()


def test_access_addresses_include_vpn_but_not_containers(monkeypatch):
    monkeypatch.setattr(network, "lan_addresses", lambda: [LanAddress(ip="192.168.1.20", interface="wlan0", score=90)])
    monkeypatch.setattr(network, "_enumerate_ipv4", lambda: [
        ("wlan0", "192.168.1.20"), ("tailscale0", "100.101.102.103"), ("wg0", "10.8.0.2"),
        ("docker0", "172.17.0.1"), ("lo", "127.0.0.1"),
    ])
    assert network.access_addresses() == [
        {"ip": "192.168.1.20", "interface": "wlan0", "kind": "lan"},
        {"ip": "100.101.102.103", "interface": "tailscale0", "kind": "vpn"},
        {"ip": "10.8.0.2", "interface": "wg0", "kind": "vpn"},
    ]


class DesktopHandler(ProfileHandler):
    profile = "linux_desktop"


class ApplianceHandler(ProfileHandler):
    profile = "linux_headless"

    def has_system_port80_redirect(self):
        return True


@pytest.fixture()
def client(monkeypatch):
    init_db()
    monkeypatch.setattr("app.api.routes.settings.access.active_port", lambda: 1903)
    monkeypatch.setattr("app.api.routes.settings.values.active_port", lambda: 1903)
    monkeypatch.setattr("app.api.routes.settings.access.access_addresses", lambda: [
        {"ip": "192.168.1.20", "interface": "wlan0", "kind": "lan"},
        {"ip": "100.101.102.103", "interface": "tailscale0", "kind": "vpn"},
    ])
    return TestClient(app)


def test_desktop_without_redirect_keeps_the_port_in_every_link(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.settings.access.get_profile_handler", lambda: DesktopHandler())
    monkeypatch.setattr("app.api.routes.settings.backup.get_profile_handler", lambda: DesktopHandler())
    monkeypatch.setattr("app.api.routes.settings.maintenance.get_profile_handler", lambda: DesktopHandler())
    monkeypatch.setattr("app.api.routes.settings.values.get_profile_handler", lambda: DesktopHandler())
    network_info = client.get("/api/settings").json()["network"]
    assert network_info["mdns_url"] == "http://bobine.local:1903"
    assert network_info["port80_redirect"] is False
    assert [link["url"] for link in network_info["access"]] == [
        "http://127.0.0.1:1903", "http://192.168.1.20:1903", "http://100.101.102.103:1903", "http://bobine.local:1903",
    ]
    assert [link["kind"] for link in network_info["access"]] == ["loopback", "lan", "vpn", "mdns"]


def test_short_address_only_where_port_80_redirects(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.settings.access.get_profile_handler", lambda: ApplianceHandler())
    monkeypatch.setattr("app.api.routes.settings.backup.get_profile_handler", lambda: ApplianceHandler())
    monkeypatch.setattr("app.api.routes.settings.maintenance.get_profile_handler", lambda: ApplianceHandler())
    monkeypatch.setattr("app.api.routes.settings.values.get_profile_handler", lambda: ApplianceHandler())
    assert client.get("/api/settings").json()["network"]["mdns_url"] == "http://bobine.local"
    monkeypatch.setattr("app.api.routes.settings.access.get_profile_handler", lambda: DesktopHandler())
    monkeypatch.setattr("app.api.routes.settings.backup.get_profile_handler", lambda: DesktopHandler())
    monkeypatch.setattr("app.api.routes.settings.maintenance.get_profile_handler", lambda: DesktopHandler())
    monkeypatch.setattr("app.api.routes.settings.values.get_profile_handler", lambda: DesktopHandler())
    monkeypatch.setattr(port80, "is_active", lambda: True)
    assert client.get("/api/settings").json()["network"]["mdns_url"] == "http://bobine.local"


def test_linux_desktop_with_system_avahi_links_the_machine_name(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.settings.access.get_profile_handler", lambda: DesktopHandler())
    monkeypatch.setattr("app.api.routes.settings.backup.get_profile_handler", lambda: DesktopHandler())
    monkeypatch.setattr("app.api.routes.settings.maintenance.get_profile_handler", lambda: DesktopHandler())
    monkeypatch.setattr("app.api.routes.settings.values.get_profile_handler", lambda: DesktopHandler())
    monkeypatch.setattr("app.api.routes.settings.access.get_mdns_status", lambda: {"state": "external"})
    monkeypatch.setattr("app.api.routes.settings.values.get_mdns_status", lambda: {"state": "external"})
    monkeypatch.setattr("app.api.routes.settings.access.socket.gethostname", lambda: "Poste-Salle.home")
    assert client.get("/api/settings").json()["network"]["mdns_url"] == "http://poste-salle.local:1903"


def test_profiles_that_never_try_port_80():
    from app.utils.deployment_profiles.android import AndroidHandler
    from app.utils.deployment_profiles.linux_headless import LinuxHeadlessHandler

    assert DesktopHandler().tries_port80_redirect()
    assert not LinuxHeadlessHandler().tries_port80_redirect()
    assert not AndroidHandler().tries_port80_redirect()
