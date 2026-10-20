"""Compression HTTP : gzip des réponses JSON/texte de l'API et du frontend
statique, jamais des flux média, des requêtes Range ni des réponses déjà
encodées ; l'ETag par contenu de `RevalidateStaticFiles` doit rester exact.

Mesuré sur la 5.0.2 : `frontend/out` 2,7 Mo -> 0,76 Mo, JSON des pistes
1,09 Mo -> 39 Ko.
"""

import gzip
import hashlib
import json
import os

os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")
os.environ.setdefault("BOBINE_MEDIA_DIR", "data/test_videos")
os.environ.setdefault("BOBINE_WATCH_DIR", "data/test_watched")
os.environ.setdefault("BOBINE_THUMBNAILS_DIR", "data/test_thumbnails")

import pytest  # noqa: E402
from fastapi import FastAPI, WebSocket  # noqa: E402
from fastapi.responses import JSONResponse, PlainTextResponse, Response, StreamingResponse  # noqa: E402
from starlette.applications import Starlette  # noqa: E402
from starlette.routing import Mount  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from app.main import RevalidateStaticFiles, app as real_app  # noqa: E402
from app.utils.http_compression import (  # noqa: E402
    ApiCompressionMiddleware,
    accepts_gzip,
    is_compressible_media_type,
)

def _from_client(app, host: str):
    """Impose l'adresse du client (le `client=` de TestClient n'existe pas dans
    le Starlette 0.27 du profil Android)."""

    async def wrapped(scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            scope = {**scope, "client": (host, 50000)}
        await app(scope, receive, send)

    return wrapped


GZIP = {"Accept-Encoding": "gzip"}
IDENTITY = {"Accept-Encoding": "identity"}
BIG_ROWS = [{"id": i, "title": f"Morceau {i}", "artist": "Artiste"} for i in range(400)]


@pytest.mark.parametrize(
    "header, expected",
    [
        (None, False),
        ("", False),
        ("identity", False),
        ("gzip", True),
        ("gzip, deflate, br", True),
        ("br, GZip;q=0.5", True),
        ("gzip;q=0", False),
        ("*", True),
        ("*;q=0", False),
        ("gzip;q=0, *", False),
        ("deflate, *;q=0.1", True),
        ("deflate", False),
        ("gzip;q=abc", False),
    ],
)
def test_accepts_gzip(header, expected):
    assert accepts_gzip(header) is expected


@pytest.mark.parametrize(
    "content_type, expected",
    [
        ("application/json", True),
        ("application/json; charset=utf-8", True),
        ("text/html; charset=utf-8", True),
        ("text/plain", True),
        ("text/css", True),
        ("application/javascript", True),
        ("image/svg+xml", True),
        ("application/problem+json", True),
        ("text/event-stream", False),
        ("video/mp4", False),
        ("audio/mpeg", False),
        ("image/jpeg", False),
        ("image/webp", False),
        ("application/zip", False),
        ("application/octet-stream", False),
        (None, False),
    ],
)
def test_is_compressible_media_type(content_type, expected):
    assert is_compressible_media_type(content_type) is expected


def _api_app() -> FastAPI:
    api = FastAPI()
    api.add_middleware(ApiCompressionMiddleware)

    @api.get("/api/tracks")
    def tracks():
        return BIG_ROWS

    @api.get("/api/small")
    def small():
        return {"ok": True}

    @api.get("/api/vary")
    def vary():
        return JSONResponse(BIG_ROWS, headers={"Vary": "Origin"})

    @api.get("/api/videos/1/stream")
    def stream_json():
        return JSONResponse(BIG_ROWS)

    @api.get("/api/thumbnails/a.svg")
    def thumbnail():
        return Response("<svg>" + "x" * 5000 + "</svg>", media_type="image/svg+xml")

    @api.get("/api/encoded")
    def encoded():
        return Response(b"\x00" * 5000, media_type="application/json", headers={"Content-Encoding": "br"})

    @api.get("/api/audio")
    def audio():
        return Response(b"\x00" * 5000, media_type="audio/mpeg")

    @api.get("/api/etag")
    def etag():
        return JSONResponse(BIG_ROWS, headers={"ETag": '"abc"'})

    @api.get("/api/download")
    def download():
        return JSONResponse(BIG_ROWS, headers={"Content-Disposition": 'attachment; filename="x.json"'})

    @api.get("/api/partial")
    def partial():
        return Response(json.dumps(BIG_ROWS), status_code=206, media_type="application/json")

    @api.get("/api/chunks")
    def chunks():
        def gen():
            for i in range(200):
                yield f'{{"line": {i}, "pad": "{"x" * 40}"}}\n'

        return StreamingResponse(gen(), media_type="text/plain")

    @api.get("/other")
    def other():
        return PlainTextResponse("y" * 5000)

    @api.websocket("/api/ws")
    async def ws(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text("z" * 5000)
        await websocket.close()

    return api


@pytest.fixture(scope="module")
def client():
    return TestClient(_api_app())


def test_json_is_gzipped_and_roundtrips(client):
    response = client.get("/api/tracks", headers=GZIP)
    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["vary"] == "Accept-Encoding"
    assert response.json() == BIG_ROWS
    # Content-Length annoncé == octets réellement reçus (compressés).
    assert int(response.headers["content-length"]) == response.num_bytes_downloaded
    assert response.num_bytes_downloaded < len(response.content) / 3


def test_existing_vary_is_extended_not_replaced(client):
    response = client.get("/api/vary", headers=GZIP)
    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["vary"] == "Origin, Accept-Encoding"


def test_small_response_is_untouched_but_still_varies(client):
    response = client.get("/api/small", headers=GZIP)
    assert "content-encoding" not in response.headers
    assert response.headers["vary"] == "Accept-Encoding"
    assert response.json() == {"ok": True}


def test_client_without_gzip_gets_identity(client):
    response = client.get("/api/tracks", headers=IDENTITY)
    assert "content-encoding" not in response.headers
    assert response.json() == BIG_ROWS


@pytest.mark.parametrize(
    "url",
    [
        "/api/videos/1/stream",  # flux média : jamais compressé
        "/api/thumbnails/a.svg",  # miniatures/branding : jamais compressés
        "/api/encoded",  # déjà encodé : pas de double encodage
        "/api/audio",  # pas du texte
        "/api/etag",  # validateur d'origine préservé
        "/api/download",  # téléchargement
        "/api/partial",  # 206
        "/other",  # hors /api
    ],
)
def test_never_compressed(client, url):
    response = client.get(url, headers=GZIP)
    assert response.headers.get("content-encoding") in (None, "br")
    if url == "/api/encoded":
        assert response.headers["content-encoding"] == "br"
    assert "gzip" not in response.headers.get("content-encoding", "")


def test_range_request_is_never_compressed(client):
    response = client.get("/api/tracks", headers={**GZIP, "Range": "bytes=0-99"})
    assert "content-encoding" not in response.headers
    assert response.json() == BIG_ROWS


def test_head_request_is_never_compressed(client):
    response = client.head("/api/tracks", headers=GZIP)
    assert "content-encoding" not in response.headers


def test_loopback_client_is_never_compressed():
    loopback = TestClient(_from_client(_api_app(), "127.0.0.1"))
    response = loopback.get("/api/tracks", headers=GZIP)
    assert "content-encoding" not in response.headers
    assert response.json() == BIG_ROWS


def test_chunked_response_is_streamed_through_gzip(client):
    response = client.get("/api/chunks", headers=GZIP)
    assert response.headers["content-encoding"] == "gzip"
    assert "content-length" not in response.headers
    lines = response.text.splitlines()
    assert len(lines) == 200 and json.loads(lines[199])["line"] == 199


def test_websocket_passes_through(client):
    with client.websocket_connect("/api/ws") as ws:
        assert ws.receive_text() == "z" * 5000


# --- frontend statique -------------------------------------------------------
JS = ("console.log('bobine');\n" * 400).encode()


@pytest.fixture()
def static_app(tmp_path):
    (tmp_path / "app.js").write_bytes(JS)
    (tmp_path / "tiny.js").write_bytes(b"var a=1;")
    (tmp_path / "logo.png").write_bytes(b"\x89PNG" + b"\x00" * 4000)
    (tmp_path / "index.html").write_bytes(b"<html>" + b"<p>bonjour</p>" * 200 + b"</html>")
    return tmp_path, TestClient(Starlette(routes=[Mount("/", RevalidateStaticFiles(directory=str(tmp_path), html=True))]))


def _md5(data: bytes) -> str:
    return hashlib.md5(data, usedforsecurity=False).hexdigest()


def test_static_text_is_gzipped_with_a_distinct_etag(static_app):
    _, client = static_app
    response = client.get("/app.js", headers=GZIP)
    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["etag"] == f'"{_md5(JS)}-gzip"'
    assert response.headers["vary"] == "Accept-Encoding"
    assert response.headers["cache-control"] == "no-cache"
    assert "content-length" in response.headers
    assert int(response.headers["content-length"]) == response.num_bytes_downloaded < len(JS) / 5
    assert response.content == JS  # httpx décode : contenu identique à l'original
    assert response.headers["content-type"].startswith("text/javascript") or response.headers[
        "content-type"
    ].startswith("application/javascript")


def test_static_identity_keeps_the_content_etag(static_app):
    _, client = static_app
    response = client.get("/app.js", headers=IDENTITY)
    assert "content-encoding" not in response.headers
    assert response.headers["etag"] == f'"{_md5(JS)}"'
    assert response.headers["vary"] == "Accept-Encoding"
    assert response.content == JS


def test_static_index_html_is_gzipped(static_app):
    _, client = static_app
    response = client.get("/", headers=GZIP)
    assert response.headers["content-encoding"] == "gzip"
    assert response.text.startswith("<html>")


def test_static_gzip_etag_revalidates_to_304(static_app):
    _, client = static_app
    etag = client.get("/app.js", headers=GZIP).headers["etag"]
    response = client.get("/app.js", headers={**GZIP, "If-None-Match": etag})
    assert response.status_code == 304
    assert response.headers["etag"] == etag
    assert response.headers["cache-control"] == "no-cache"


def test_static_cached_raw_copy_stays_valid_when_client_now_accepts_gzip(static_app):
    _, client = static_app
    response = client.get("/app.js", headers={**GZIP, "If-None-Match": f'"{_md5(JS)}"'})
    assert response.status_code == 304
    assert response.headers["etag"] == f'"{_md5(JS)}"'


def test_static_gzip_etag_without_gzip_support_serves_full_content(static_app):
    _, client = static_app
    response = client.get("/app.js", headers={**IDENTITY, "If-None-Match": f'"{_md5(JS)}-gzip"'})
    assert response.status_code == 200
    assert response.content == JS


def test_static_content_change_invalidates_etag_and_compressed_copy(static_app):
    tmp_path, client = static_app
    old = client.get("/app.js", headers=GZIP)
    new_content = JS.replace(b"bobine", b"BOBINE")
    assert len(new_content) == len(JS)
    (tmp_path / "app.js").write_bytes(new_content)
    response = client.get("/app.js", headers={**GZIP, "If-None-Match": old.headers["etag"]})
    assert response.status_code == 200
    assert response.headers["etag"] == f'"{_md5(new_content)}-gzip"'
    assert response.content == new_content


def test_static_range_loopback_small_and_binary_files_stay_identity(static_app):
    _, client = static_app
    ranged = client.get("/app.js", headers={**GZIP, "Range": "bytes=0-9"})
    assert "content-encoding" not in ranged.headers
    assert ranged.headers["etag"] == f'"{_md5(JS)}"'
    tiny = client.get("/tiny.js", headers=GZIP)
    assert "content-encoding" not in tiny.headers and tiny.content == b"var a=1;"
    png = client.get("/logo.png", headers=GZIP)
    assert "content-encoding" not in png.headers and "vary" not in png.headers


def test_static_loopback_client_gets_identity(static_app):
    tmp_path, _ = static_app
    loopback = TestClient(
        _from_client(Starlette(routes=[Mount("/", RevalidateStaticFiles(directory=str(tmp_path)))]), "::1")
    )
    response = loopback.get("/app.js", headers=GZIP)
    assert "content-encoding" not in response.headers
    assert response.content == JS


# --- application réelle --------------------------------------------------------
def test_real_app_compresses_api_json_and_leaves_streams_alone():
    client = TestClient(real_app)
    settings = client.get("/api/settings", headers=GZIP)
    assert settings.status_code == 200
    assert settings.headers["content-encoding"] == "gzip"
    assert settings.json()
    missing_stream = client.get("/api/videos/987654321/stream", headers={**GZIP, "Range": "bytes=0-1"})
    assert missing_stream.status_code == 404
    assert "content-encoding" not in missing_stream.headers
