"""Garde du réseau local : un client à l'adresse publique n'atteint ni l'API ni un WebSocket ; réseau local, VPN et
réseaux déclarés passent."""

import os

os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")
os.environ.setdefault("BOBINE_MEDIA_DIR", "data/test_videos")
os.environ.setdefault("BOBINE_WATCH_DIR", "data/test_watched")
os.environ.setdefault("BOBINE_THUMBNAILS_DIR", "data/test_thumbnails")

import pytest  # noqa: E402
from fastapi import FastAPI, WebSocket  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from app.main import app as real_app  # noqa: E402
from app.utils.network_guard import LocalNetworkGuard, allowed_networks, is_allowed_client  # noqa: E402


@pytest.mark.parametrize("host", [
    "127.0.0.1", "::1", "192.168.1.13", "10.0.0.2", "172.20.1.1", "100.101.102.103",
    "fd7a:115c:a1e0::1", "fe80::1%eth0", "::ffff:192.168.1.5", "testclient", None,
])
def test_local_clients_pass(host):
    assert is_allowed_client(host)


@pytest.mark.parametrize("host", ["8.8.8.8", "2a01:4f8::1", "::ffff:1.1.1.1", "172.32.0.1"])
def test_public_clients_refused(host):
    assert not is_allowed_client(host)


def test_declared_network_passes(monkeypatch):
    monkeypatch.setenv("BOBINE_ALLOWED_NETWORKS", "81.2.69.0/24, invalide")
    extra = allowed_networks()
    assert len(extra) == 1
    assert is_allowed_client("81.2.69.7", extra)
    assert not is_allowed_client("9.9.9.9", extra)


def _app(client_host: str) -> TestClient:
    inner = FastAPI()

    @inner.get("/api/state")
    def state() -> dict[str, bool]:
        return {"ok": True}

    @inner.websocket("/ws")
    async def ws(socket: WebSocket) -> None:
        await socket.accept()
        await socket.send_text("ok")
        await socket.close()

    return TestClient(LocalNetworkGuard(inner), client=(client_host, 50000))


def test_http_and_websocket_from_internet_refused():
    client = _app("8.8.8.8")
    response = client.get("/api/state")
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "public_client"
    with pytest.raises(WebSocketDisconnect) as closed:
        with client.websocket_connect("/ws") as socket:
            socket.receive_text()
    assert closed.value.code == 1008


def test_http_and_websocket_from_lan_pass():
    client = _app("192.168.1.20")
    assert client.get("/api/state").json() == {"ok": True}
    with client.websocket_connect("/ws") as socket:
        assert socket.receive_text() == "ok"


def test_guard_is_outermost_middleware():
    assert real_app.user_middleware[0].cls is LocalNetworkGuard
