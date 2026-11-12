"""Mises à jour par Tor : le nom d'hôte part au proxy SOCKS5 sans être résolu localement ; option activée et Tor
indisponible, rien ne part en direct ; Tor lancé à la demande s'arrête seul ; réglages et test exposés par l'API."""

import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import socket  # noqa: E402
import struct  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import urllib.request  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.utils import tor_proxy  # noqa: E402
from app.utils.deployment import ProfileHandler  # noqa: E402


@pytest.fixture(autouse=True)
def _tor_disabled_after_test():
    yield
    tor_proxy.configure(False, None)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class FakeSocksProxy:
    """Proxy SOCKS5 minimal : note la cible demandée et répond lui-même une page HTTP."""

    def __init__(self) -> None:
        self.server = socket.socket()
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(4)
        self.port = self.server.getsockname()[1]
        self.targets: list[tuple[int, bytes, int]] = []
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        while True:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            with conn:
                conn.recv(3)
                conn.sendall(b"\x05\x00")
                head = conn.recv(4)
                if len(head) < 4:  # sonde de présence : la connexion s'arrête après la poignée de main
                    continue
                atyp = head[3]
                if atyp == 3:
                    length = conn.recv(1)[0]
                    host = conn.recv(length)
                else:
                    host = conn.recv(4 if atyp == 1 else 16)
                port = struct.unpack(">H", conn.recv(2))[0]
                self.targets.append((atyp, host, port))
                conn.sendall(b"\x05\x00\x00\x01" + bytes(4) + b"\x00\x00")
                conn.recv(4096)
                conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")

    def close(self) -> None:
        self.server.close()


@pytest.mark.parametrize("value, expected", [("127.0.0.1:9050", ("127.0.0.1", 9050)), ("[::1]:9150", ("::1", 9150))])
def test_parse_proxy(value, expected):
    assert tor_proxy.parse_proxy(value) == expected


@pytest.mark.parametrize("value", ["", "127.0.0.1", "127.0.0.1:0", "127.0.0.1:70000", ":9050", "hôte:abc"])
def test_parse_proxy_rejects_invalid_addresses(value):
    with pytest.raises(ValueError):
        tor_proxy.parse_proxy(value)


def test_host_name_is_resolved_by_the_proxy_not_locally():
    proxy = FakeSocksProxy()
    try:
        tor_proxy.configure(True, f"127.0.0.1:{proxy.port}")
        # `.invalid` ne se résout jamais localement : la réponse prouve que le nom est parti tel quel au proxy.
        with tor_proxy.urlopen("http://releases.bobine.invalid/notes", timeout=5) as resp:
            assert resp.read() == b"ok"
        assert proxy.targets == [(3, b"releases.bobine.invalid", 80)]
    finally:
        proxy.close()


def test_enabled_without_tor_never_goes_direct(monkeypatch):
    monkeypatch.setattr(tor_proxy, "find_tor_binary", lambda: None)

    def direct(*_args, **_kwargs):
        raise AssertionError("requête partie en direct")

    monkeypatch.setattr(urllib.request, "urlopen", direct)
    tor_proxy.configure(True, f"127.0.0.1:{_free_port()}")
    with pytest.raises(tor_proxy.TorUnavailable):
        tor_proxy.urlopen("https://api.github.com/", timeout=5)


def test_disabled_uses_the_direct_connection(monkeypatch):
    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout: calls.append(req) or "direct")
    tor_proxy.configure(False, None)
    assert tor_proxy.urlopen("https://api.github.com/", timeout=5) == "direct"
    assert tor_proxy.request_timeout(6.0) == 6.0


class FakeTorProcess:
    def __init__(self, port: int) -> None:
        self.stdout = iter([
            f"[notice] Opened Socks listener connection (ready) on 127.0.0.1:{port}\n",
            "[notice] Bootstrapped 100% (done): Done\n",
        ])
        self.terminated = False

    def poll(self):
        return 0 if self.terminated else None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.terminated = True


class _LineReader:
    def __init__(self, lines):
        self._lines = list(lines)

    def readline(self):
        return self._lines.pop(0) if self._lines else ""

    def __iter__(self):
        return iter(())


def test_on_demand_tor_starts_once_and_stops_when_idle(monkeypatch, tmp_path):
    launched = []

    def popen(command, **_kwargs):
        assert "-f" in command and os.devnull in command  # jamais le torrc du système (relais possible)
        process = FakeTorProcess(19999)
        process.stdout = _LineReader(process.stdout)
        launched.append(process)
        return process

    monkeypatch.setattr(tor_proxy.subprocess, "Popen", popen)
    monkeypatch.setattr(tor_proxy, "_cache_dir", lambda: tmp_path / "tor")
    monkeypatch.setattr(tor_proxy, "IDLE_STOP_SECONDS", 0.2)
    on_demand = tor_proxy._OnDemandTor()
    assert on_demand.acquire("/usr/bin/tor") == ("127.0.0.1", 19999)
    assert on_demand.acquire("/usr/bin/tor") == ("127.0.0.1", 19999)
    assert len(launched) == 1
    on_demand.release()
    on_demand.release()
    time.sleep(0.5)
    assert launched[0].terminated


def test_existing_proxy_is_preferred_to_launching_tor(monkeypatch):
    proxy = FakeSocksProxy()
    monkeypatch.setattr(tor_proxy, "find_tor_binary", lambda: pytest.fail("Tor lancé alors qu'un proxy répond"))
    try:
        session = tor_proxy.TorSession(f"127.0.0.1:{proxy.port}")
        assert session.source == "existing"
        session.close()
    finally:
        proxy.close()


class DesktopHandler(ProfileHandler):
    profile = "linux_desktop"


class ApplianceHandler(ProfileHandler):
    profile = "linux_headless"

    def supports_update_over_tor(self):
        return False


@pytest.fixture()
def client():
    init_db()
    return TestClient(app)


def test_settings_expose_and_validate_tor(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.settings.access.get_profile_handler", lambda: DesktopHandler())
    monkeypatch.setattr("app.api.routes.settings.backup.get_profile_handler", lambda: DesktopHandler())
    monkeypatch.setattr("app.api.routes.settings.maintenance.get_profile_handler", lambda: DesktopHandler())
    monkeypatch.setattr("app.api.routes.settings.values.get_profile_handler", lambda: DesktopHandler())
    data = client.get("/api/settings").json()
    assert data["update_tor_supported"] is True
    assert client.put("/api/settings", json={"update_tor_proxy": "pas une adresse"}).status_code == 400
    saved = client.put("/api/settings", json={"update_tor": "true", "update_tor_proxy": "127.0.0.1:9150"}).json()
    assert saved["update_tor"] == "true" and saved["update_tor_proxy"] == "127.0.0.1:9150"
    assert tor_proxy.is_enabled()
    client.put("/api/settings", json={"update_tor": "false"})
    assert not tor_proxy.is_enabled()


def test_appliance_refuses_tor_updates(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.settings.access.get_profile_handler", lambda: ApplianceHandler())
    monkeypatch.setattr("app.api.routes.settings.backup.get_profile_handler", lambda: ApplianceHandler())
    monkeypatch.setattr("app.api.routes.settings.maintenance.get_profile_handler", lambda: ApplianceHandler())
    monkeypatch.setattr("app.api.routes.settings.values.get_profile_handler", lambda: ApplianceHandler())
    assert client.get("/api/settings").json()["update_tor_supported"] is False
    assert client.put("/api/settings", json={"update_tor": "true"}).status_code == 409


def test_tor_check_endpoint(client, monkeypatch):
    monkeypatch.setattr(tor_proxy, "check", lambda proxy: {"ok": True, "is_tor": True, "proxy": proxy, "source": "existing"})
    assert client.post("/api/updates/tor-check", json={"proxy": "127.0.0.1:9150"}).json()["proxy"] == "127.0.0.1:9150"
    assert client.post("/api/updates/tor-check", json={"proxy": "faux"}).status_code == 400


def test_automatic_checks_reuse_the_last_result_longer_under_tor(monkeypatch):
    from app.api.routes import updates
    from app.updates import github

    calls = []
    monkeypatch.setattr(github, "github_get", lambda url, etag=None: calls.append(url) or (200, {"tag_name": "V9.9.9"}, None))
    github.RELEASE_CACHE.clear()
    tor_proxy.configure(True, None)
    github.lookup_release_blocking("stable", False)
    github.RELEASE_CACHE["stable"]["checked_at"] -= 60  # au-delà de la fenêtre directe de 10 s
    github.lookup_release_blocking("stable", False)
    assert len(calls) == 1
    github.lookup_release_blocking("stable", True)
    assert len(calls) == 2
    github.RELEASE_CACHE.clear()
