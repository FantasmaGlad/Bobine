"""Conformité HTTP des flux média (RFC 9110) : HEAD, Range, If-Range, 416,
ETag. Régression réelle observée sur Firefox 157 : `HEAD /stream` renvoyait
la page HTML 404 du frontend avec un statut 206."""

import os
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")
os.environ.setdefault("BOBINE_MEDIA_DIR", "data/test_videos")
os.environ.setdefault("BOBINE_WATCH_DIR", "data/test_watched")
os.environ.setdefault("BOBINE_THUMBNAILS_DIR", "data/test_thumbnails")

from app.utils.media_response import RangeNotSatisfiable, build_media_response, parse_byte_range  # noqa: E402

PAYLOAD = bytes(range(256)) * 40  # 10 240 octets


@pytest.fixture
def client(tmp_path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(PAYLOAD)
    app = FastAPI()

    @app.api_route("/stream", methods=["GET", "HEAD"])
    async def stream(request: Request):
        return await build_media_response(media, request.headers, request.method, "video/mp4")

    @app.api_route("/missing", methods=["GET", "HEAD"])
    async def missing(request: Request):
        return await build_media_response(tmp_path / "absent.mp4", request.headers, request.method, "video/mp4")

    return TestClient(app)


# --- analyse de l'en-tête Range ------------------------------------------------

@pytest.mark.parametrize("header,size,expected", [
    ("bytes=0-99", 1000, (0, 99)),
    ("bytes=900-", 1000, (900, 999)),
    ("bytes=-100", 1000, (900, 999)),
    ("bytes=-5000", 1000, (0, 999)),          # suffixe plus long que le fichier
    ("bytes=500-5000", 1000, (500, 999)),     # fin au-delà : tronquée
    ("bytes=0-0", 1000, (0, 0)),
])
def test_valid_ranges(header, size, expected):
    assert parse_byte_range(header, size) == expected


@pytest.mark.parametrize("header", [
    None, "", "items=0-5", "bytes=", "bytes=0-5,10-20", "bytes=abc-def", "bytes=5-2", "bytes=10",
])
def test_unusable_ranges_are_ignored_not_rejected(header):
    # RFC 9110 : un serveur PEUT ignorer Range -> 200 complet, jamais une 400.
    assert parse_byte_range(header, 1000) is None


@pytest.mark.parametrize("header", ["bytes=1000-", "bytes=5000-6000", "bytes=-0"])
def test_unsatisfiable_ranges(header):
    with pytest.raises(RangeNotSatisfiable):
        parse_byte_range(header, 1000)


# --- GET / HEAD ----------------------------------------------------------------

def test_get_full_file(client):
    r = client.get("/stream")
    assert r.status_code == 200 and r.content == PAYLOAD
    assert r.headers["content-type"] == "video/mp4"
    assert r.headers["accept-ranges"] == "bytes"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["etag"].startswith('"') and "last-modified" in r.headers


def test_head_has_same_headers_and_no_body(client):
    g, h = client.get("/stream"), client.head("/stream")
    assert h.status_code == 200 and h.content == b""
    assert h.headers["content-type"] == "video/mp4"          # jamais text/html
    assert h.headers["content-length"] == str(len(PAYLOAD))
    assert h.headers["etag"] == g.headers["etag"]


def test_head_with_range_describes_the_partial_response(client):
    h = client.head("/stream", headers={"Range": "bytes=0-99"})
    assert h.status_code == 206 and h.content == b""
    assert h.headers["content-type"] == "video/mp4"
    assert h.headers["content-range"] == f"bytes 0-99/{len(PAYLOAD)}"
    assert h.headers["content-length"] == "100"


def test_partial_content(client):
    r = client.get("/stream", headers={"Range": "bytes=100-199"})
    assert r.status_code == 206 and r.content == PAYLOAD[100:200]
    assert r.headers["content-range"] == f"bytes 100-199/{len(PAYLOAD)}"


def test_suffix_range(client):
    r = client.get("/stream", headers={"Range": "bytes=-50"})
    assert r.status_code == 206 and r.content == PAYLOAD[-50:]


def test_open_ended_range(client):
    r = client.get("/stream", headers={"Range": f"bytes={len(PAYLOAD) - 10}-"})
    assert r.status_code == 206 and r.content == PAYLOAD[-10:]


def test_range_past_end_is_416_with_size(client):
    r = client.get("/stream", headers={"Range": f"bytes={len(PAYLOAD)}-"})
    assert r.status_code == 416
    assert r.headers["content-range"] == f"bytes */{len(PAYLOAD)}"


def test_multiple_ranges_fall_back_to_full_body(client):
    r = client.get("/stream", headers={"Range": "bytes=0-9,20-29"})
    assert r.status_code == 200 and r.content == PAYLOAD


# --- validateurs -----------------------------------------------------------------

def test_if_none_match_gives_304(client):
    etag = client.head("/stream").headers["etag"]
    r = client.get("/stream", headers={"If-None-Match": etag})
    assert r.status_code == 304 and r.content == b""


def test_if_range_with_matching_etag_serves_the_range(client):
    etag = client.head("/stream").headers["etag"]
    r = client.get("/stream", headers={"Range": "bytes=0-9", "If-Range": etag})
    assert r.status_code == 206 and r.content == PAYLOAD[:10]


def test_if_range_with_stale_etag_serves_the_whole_file(client):
    r = client.get("/stream", headers={"Range": "bytes=0-9", "If-Range": '"stale"'})
    assert r.status_code == 200 and r.content == PAYLOAD


def test_missing_file_is_404_json_for_get_and_head(client):
    assert client.get("/missing").status_code == 404
    assert client.head("/missing").status_code == 404


def test_empty_file_is_served_without_error(tmp_path):
    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    app = FastAPI()

    @app.api_route("/s", methods=["GET", "HEAD"])
    async def s(request: Request):
        return await build_media_response(empty, request.headers, request.method, "video/mp4")

    c = TestClient(app)
    assert c.get("/s").status_code == 200
    assert c.get("/s", headers={"Range": "bytes=0-"}).status_code == 416


# --- routes réelles de l'application ---------------------------------------------

def test_unknown_api_path_is_json_404_never_the_frontend_html():
    from app.main import app

    c = TestClient(app)
    for method in ("get", "head"):
        r = getattr(c, method)("/api/chemin-inexistant")
        assert r.status_code == 404
        assert "text/html" not in r.headers.get("content-type", "")


def test_head_on_a_missing_media_resource_is_404_not_html():
    from app.main import app

    c = TestClient(app)
    for url in ("/api/videos/999999/stream", "/api/radio/tracks/999999/stream", "/api/audio/tracks/999999/stream"):
        r = c.head(url)
        assert r.status_code == 404
        assert "text/html" not in r.headers.get("content-type", "")


def _open_fds_on(path) -> int:
    base = os.path.realpath(path)
    count = 0
    for fd in os.listdir("/proc/self/fd"):
        try:
            if os.path.realpath(os.readlink(f"/proc/self/fd/{fd}")) == base:
                count += 1
        except OSError:
            pass
    return count


@pytest.mark.skipif(not os.path.isdir("/proc/self/fd"), reason="Linux uniquement")
def test_stream_released_when_client_stops_early(tmp_path):
    """Régression : un client qui coupe en cours de flux (annulation pendant `yield`) laissait le fichier ouvert, ce qui
    empêchait de démonter un support externe (« occupé »). Garde-fou : le cas réel (uvicorn + coupure du client) est
    reproduit de bout en bout par scripts/storage-real-test.py (démontage refusé « occupé » avant le correctif)."""
    import asyncio

    media = tmp_path / "gros.mp4"
    media.write_bytes(os.urandom(2 * 1024 * 1024))

    async def scenario():
        response = await build_media_response(media, {}, "GET", "video/mp4")
        iterator = response.body_iterator
        first = await iterator.__anext__()
        assert first and _open_fds_on(media) == 1
        task = asyncio.ensure_future(iterator.aclose())
        await task
        assert _open_fds_on(media) == 0

        # Annulation de la tâche de diffusion pendant la lecture : même résultat.
        response = await build_media_response(media, {}, "GET", "video/mp4")
        iterator = response.body_iterator

        async def consume():
            async for _ in iterator:
                await asyncio.sleep(0.05)

        consumer = asyncio.ensure_future(consume())
        await asyncio.sleep(0.12)
        consumer.cancel()
        try:
            await consumer
        except asyncio.CancelledError:
            pass
        await iterator.aclose()
        await asyncio.sleep(0.05)
        assert _open_fds_on(media) == 0

    asyncio.run(scenario())
