"""Garde d'origine : une page web d'une autre origine ne pilote pas l'API (ni requête modifiante, ni WebSocket,
ni lecture d'une réponse par CORS) ; l'interface servie par Bobine, la CLI et le serveur de développement passent."""

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
from app.utils import origin_guard  # noqa: E402
from app.utils.origin_guard import SameOriginGuard, is_same_origin, is_trusted_host_name  # noqa: E402

EVIL = "https://evil.example"


def _guarded_app() -> SameOriginGuard:
    inner = FastAPI()

    @inner.post("/api/action")
    def action() -> dict[str, bool]:
        return {"ok": True}

    @inner.get("/api/state")
    def state() -> dict[str, bool]:
        return {"ok": True}

    @inner.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_json({"ok": True})
        await websocket.close()

    return SameOriginGuard(inner, allowed_origins=("http://localhost:3000",))


@pytest.mark.parametrize(
    ("origin", "host", "scheme", "expected"),
    [
        ("http://192.168.1.20:1903", "192.168.1.20:1903", "http", True),
        ("http://bobine.local", "bobine.local", "http", True),
        ("http://bobine.local:80", "BOBINE.local", "http", True),
        ("http://[fe80::1]:1903", "[fe80::1]:1903", "http", True),
        ("http://192.168.1.20:1904", "192.168.1.20:1903", "http", False),
        (EVIL, "192.168.1.20:1903", "http", False),
        ("null", "192.168.1.20:1903", "http", False),
        ("http://192.168.1.20:1903", "", "http", False),
    ],
)
def test_is_same_origin(origin, host, scheme, expected):
    assert is_same_origin(origin, host, scheme) is expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("192.168.1.20", True), ("fe80::1", True), ("[fe80::1]", True), ("localhost", True), ("wyse", True),
        ("bobine.local", True), ("Bobine.Local.", True), ("abc.onion", True), ("tv.home.arpa", True), ("wyse.lan", True),
        ("evil.example", False), ("192.168.1.20.nip.io", False), ("bobine.local.evil.example", False),
        ("salle.exemple.fr", False),
    ],
)
def test_trusted_host_names(name, expected):
    assert is_trusted_host_name(name) is expected


def test_declared_host_name_is_trusted():
    assert is_trusted_host_name("salle.exemple.fr", frozenset({"salle.exemple.fr"}))


def test_dns_rebinding_is_refused(monkeypatch):
    rebound = {"Origin": "http://evil.example:1903", "Host": "evil.example:1903"}
    client = TestClient(_guarded_app())
    assert client.post("/api/action", headers=rebound).status_code == 403
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws", headers=rebound):
            pass
    monkeypatch.setenv("BOBINE_ALLOWED_HOSTS", "evil.example")
    assert TestClient(_guarded_app()).post("/api/action", headers=rebound).status_code == 200


def test_foreign_origin_cannot_change_state():
    client = TestClient(_guarded_app())
    refused = client.post("/api/action", headers={"Origin": EVIL})
    assert refused.status_code == 403
    assert refused.json()["detail"]["code"] == "cross_origin"
    assert client.post("/api/action", headers={"Origin": "null"}).status_code == 403


def test_same_origin_cli_and_dev_server_pass():
    client = TestClient(_guarded_app())
    assert client.post("/api/action", headers={"Origin": "http://testserver"}).status_code == 200
    assert client.post("/api/action").status_code == 200  # CLI, assistant, curl : pas d'en-tête Origin
    assert client.post("/api/action", headers={"Origin": "http://localhost:3000"}).status_code == 200
    assert client.get("/api/state", headers={"Origin": EVIL}).status_code == 200


def test_foreign_origin_cannot_open_websocket():
    client = TestClient(_guarded_app())
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws", headers={"Origin": EVIL}):
            pass
    with client.websocket_connect("/ws", headers={"Origin": "http://testserver"}) as ws:
        assert ws.receive_json() == {"ok": True}


def test_real_app_refuses_foreign_preflight_and_destructive_route():
    client = TestClient(real_app)
    preflight = client.options(
        "/api/settings/system/uninstall",
        headers={"Origin": EVIL, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"},
    )
    assert preflight.headers.get("access-control-allow-origin") is None
    refused = client.post("/api/settings/system/uninstall", json={"confirm": "x"}, headers={"Origin": EVIL})
    assert refused.status_code == 403


def test_dev_origins_from_environment(monkeypatch):
    monkeypatch.setenv("BOBINE_DEV_ORIGINS", "http://10.0.0.5:3000/, ")
    assert origin_guard.dev_origins() == ("http://10.0.0.5:3000",)
    monkeypatch.delenv("BOBINE_DEV_ORIGINS")
    assert origin_guard.dev_origins() == origin_guard.DEFAULT_DEV_ORIGINS
