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
from app.api.network_guard import LocalNetworkGuard, allowed_networks, is_allowed_client  # noqa: E402


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


@pytest.mark.recent_stack
def test_http_and_websocket_from_internet_refused():
    client = _app("8.8.8.8")
    response = client.get("/api/state")
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "public_client"
    with pytest.raises(WebSocketDisconnect) as closed:
        with client.websocket_connect("/ws") as socket:
            socket.receive_text()
    assert closed.value.code == 1008


@pytest.mark.recent_stack
@pytest.mark.parametrize("headers", [
    {"X-Forwarded-For": "8.8.8.8"},
    {"X-Forwarded-For": "192.168.1.9, 8.8.8.8"},
    {"X-Forwarded-For": "nimportequoi"},
    {"X-Forwarded-For": ""},
    {"X-Real-IP": "1.1.1.1"},
    {"CF-Connecting-IP": "2a01:4f8::1"},
    {"Forwarded": "for=8.8.8.8;proto=https"},
    {"Forwarded": 'for="[2a01:4f8::1]:443"'},
    {"Forwarded": "for=unknown"},
    {"Forwarded": "by=10.0.0.1"},
])
@pytest.mark.parametrize("peer", ["127.0.0.1", "172.17.0.1", "192.168.1.10"])
def test_relayed_public_or_unreadable_client_refused(peer, headers):
    assert _app(peer).get("/api/state", headers=headers).status_code == 403


@pytest.mark.recent_stack
@pytest.mark.parametrize("headers", [
    {"X-Forwarded-For": "192.168.1.9"},
    {"X-Forwarded-For": "10.0.0.2:5000, 100.64.1.1"},
    {"Forwarded": "for=192.168.1.9;proto=http"},
    {"Forwarded": 'for="[fd7a:115c:a1e0::1]:443"'},
])
def test_relayed_local_client_passes(headers):
    assert _app("127.0.0.1").get("/api/state", headers=headers).status_code == 200


@pytest.mark.recent_stack
def test_headers_never_widen_access():
    assert _app("8.8.8.8").get("/api/state", headers={"X-Forwarded-For": "127.0.0.1"}).status_code == 403


@pytest.mark.recent_stack
def test_http_and_websocket_from_lan_pass():
    client = _app("192.168.1.20")
    assert client.get("/api/state").json() == {"ok": True}
    with client.websocket_connect("/ws") as socket:
        assert socket.receive_text() == "ok"


def test_guard_is_outermost_middleware():
    assert real_app.user_middleware[0].cls is LocalNetworkGuard


@pytest.mark.recent_stack
def test_real_app_refuses_public_client():
    client = TestClient(real_app, client=("8.8.8.8", 50000))
    for path in ("/api/state", "/", "/api/videos"):
        assert client.get(path).status_code == 403
    assert TestClient(real_app, client=("8.8.8.8", 50000)).get("/api/state", headers={"X-Forwarded-For": "192.168.1.2"}).status_code == 403


def test_uvicorn_does_not_rewrite_peer():
    from pathlib import Path

    import app.main  # noqa: F401  (le point d'entrée lance uvicorn depuis run_backend.py)

    source = (Path(__file__).resolve().parents[1] / "run_backend.py").read_text(encoding="utf-8")
    assert "proxy_headers=False" in source


@pytest.mark.parametrize("headers, expected", [
    ([(b"host", b"192.168.1.5:8000")], True),
    ([(b"host", b"abcdef.onion")], False),
    ([(b"host", b"abcdef.onion:80")], False),
    ([(b"host", b"bobine.local"), (b"x-forwarded-for", b"192.168.1.9")], False),
    ([(b"host", b"bobine.local"), (b"forwarded", b"for=10.0.0.2")], False),
])
def test_local_screen_rights_need_a_direct_clean_request(headers, expected):
    from starlette.requests import Request

    from app.api.routes.devices import is_local_request

    request = Request({"type": "http", "client": ("127.0.0.1", 5000), "headers": headers})
    assert is_local_request(request) is expected
