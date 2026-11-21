import os

os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")
os.environ.setdefault("BOBINE_MEDIA_DIR", "data/test_videos")
os.environ.setdefault("BOBINE_WATCH_DIR", "data/test_watched")
os.environ.setdefault("BOBINE_THUMBNAILS_DIR", "data/test_thumbnails")

import pytest
from fastapi import FastAPI, Response
from starlette.testclient import TestClient

from app.api.security_headers import SecurityHeaders, content_security_policy, socket_sources
from app.main import app as real_app


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("192.168.1.20:1903", " ws://192.168.1.20:1903 wss://192.168.1.20:1903"),
        ("bobine.local", " ws://bobine.local wss://bobine.local"),
        ("[fe80::1]:1903", " ws://[fe80::1]:1903 wss://[fe80::1]:1903"),
        ("bad host; script-src *", ""),
        ("host:notaport", ""),
        (None, ""),
    ],
)
def test_socket_sources(host, expected):
    assert socket_sources(host) == expected


def test_policy_keeps_scripts_and_frames_on_the_server():
    policy = content_security_policy("bobine.local")
    assert "script-src 'self' 'unsafe-inline'" in policy
    assert "frame-ancestors 'self'" in policy
    assert "object-src 'none'" in policy
    assert policy.endswith("connect-src 'self' ws://bobine.local wss://bobine.local")


def test_real_app_sets_headers_on_api_and_refusals():
    client = TestClient(real_app)
    for response in (client.get("/api/settings"), client.get("/api/settings", headers={"Host": "attacker.example"})):
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "same-origin"
        assert "frame-ancestors 'self'" in response.headers["content-security-policy"]


def test_existing_header_is_not_duplicated():
    inner = FastAPI()

    @inner.get("/media")
    def media() -> Response:
        return Response(b"x", headers={"X-Content-Type-Options": "nosniff"})

    response = TestClient(SecurityHeaders(inner)).get("/media")
    assert response.headers.get_list("x-content-type-options") == ["nosniff"]
