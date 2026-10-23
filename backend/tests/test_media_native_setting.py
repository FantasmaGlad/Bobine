"""Réglage `media_native` : défaut désactivé, priorité de la variable, état réel, repli et pochettes."""
import os

# Base de test isolée AVANT tout import de l'application.
os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import importlib.util
from pathlib import Path
import shutil
import stat
import subprocess
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.utils import media_metadata, media_native
from app.utils.media_sidecar import CoverResult, close_current_media_client

ROOT = Path(__file__).resolve().parents[2]
BINARY = ROOT / "media" / "target" / "release" / ("bobine-media.exe" if os.name == "nt" else "bobine-media")


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    for name in ("BOBINE_MEDIA_NATIVE", "BOBINE_MEDIA_BIN", "BOBINE_MEDIA_SIDECAR"):
        monkeypatch.delenv(name, raising=False)
    media_native.configure(False)
    close_current_media_client()
    yield
    media_native.configure(False)
    close_current_media_client()


@pytest.fixture()
def client():
    from app.database import SessionLocal
    from app.models import Setting

    with TestClient(app) as test_client:
        with SessionLocal() as db:
            db.query(Setting).filter(Setting.key == "media_native").delete(synchronize_session=False)
            db.commit()
        media_native.configure(False)
        yield test_client
        with SessionLocal() as db:
            db.query(Setting).filter(Setting.key == "media_native").delete(synchronize_session=False)
            db.commit()


# --- activation -------------------------------------------------------------------------

def test_disabled_by_default():
    assert media_native.is_enabled() is False
    assert media_native.source() == "default"


def test_setting_enables_and_disables():
    media_native.configure("true")
    assert media_native.is_enabled() is True and media_native.source() == "setting"
    media_native.configure("false")
    assert media_native.is_enabled() is False
    # Anything but "true" is "disabled", never an accidental activation.
    for value in ("1", "yes", "", None, "TRUE ", 1):
        media_native.configure(value)
        assert media_native.is_enabled() is (isinstance(value, str) and value.strip().lower() == "true")


@pytest.mark.parametrize("setting, variable, expected", [
    (False, "1", True), (True, "1", True), (True, "0", False), (False, "0", False),
    (True, "", True), (True, "true", True), (False, "true", False), (False, "", False),
])
def test_environment_override_has_priority(monkeypatch, setting, variable, expected):
    media_native.configure(setting)
    monkeypatch.setenv("BOBINE_MEDIA_NATIVE", variable)
    assert media_native.is_enabled() is expected
    assert media_native.source() == ("env" if variable in ("0", "1") else ("setting" if setting else "default"))


def test_importers_use_the_reference_when_the_setting_is_off(monkeypatch):
    monkeypatch.setattr(media_metadata, "get_media_client", Mock(side_effect=AssertionError("client created")))
    monkeypatch.setattr(media_metadata.audio_utils, "extract_audio_duration", Mock(return_value=3.5))
    assert media_metadata.extract_audio_duration("a.mp3") == 3.5


def test_setting_alone_activates_the_native_path_and_a_failure_falls_back(monkeypatch):
    media_native.configure("true")
    failing = Mock()
    failing.probe_audio.return_value = None  # the component refused: unsupported, timeout, crash...
    failing.extract_cover.return_value = CoverResult(available=False)
    monkeypatch.setattr(media_metadata, "get_media_client", Mock(return_value=failing))
    reference = Mock(return_value=4.25)
    cover = Mock(return_value="covers/cover.jpg")
    monkeypatch.setattr(media_metadata.audio_utils, "extract_audio_duration", reference)
    monkeypatch.setattr(media_metadata.radio_utils, "extract_embedded_cover", cover)
    assert media_metadata.extract_audio_duration("a.flac") == 4.25
    assert media_metadata.extract_embedded_cover("a.flac", "covers", "id") == "covers/cover.jpg"
    failing.probe_audio.assert_called_once()
    reference.assert_called_once_with("a.flac")
    cover.assert_called_once_with("a.flac", "covers", "id")


# --- API ----------------------------------------------------------------------------------

def test_api_default_write_validation_and_persistence(client):
    assert client.get("/api/settings").json()["media_native"] == "false"
    assert client.put("/api/settings", json={"media_native": "maybe"}).status_code == 400
    assert media_native.is_enabled() is False
    response = client.put("/api/settings", json={"media_native": "true"})
    assert response.status_code == 200 and response.json()["media_native"] == "true"
    assert media_native.is_enabled() is True
    assert client.get("/api/settings").json()["media_native"] == "true"
    # The persisted value is read back at startup.
    media_native.configure(False)
    from app.database import SessionLocal

    with SessionLocal() as db:
        media_native.load_from_database(db)
    assert media_native.is_enabled() is True
    assert client.put("/api/settings", json={"media_native": "false"}).json()["media_native"] == "false"
    assert media_native.is_enabled() is False


def test_status_disabled_does_not_start_the_component(client, monkeypatch):
    monkeypatch.setattr("app.utils.media_sidecar.get_media_client", Mock(side_effect=AssertionError("started")))
    body = client.get("/api/settings/media-native").json()
    assert body["state"] == "disabled" and body["enabled"] is False and body["source"] == "default"


def test_status_absent_when_enabled_without_executable(client, monkeypatch):
    monkeypatch.setenv("BOBINE_MEDIA_BIN", "/nonexistent/bobine-media")
    client.put("/api/settings", json={"media_native": "true"})
    body = client.get("/api/settings/media-native").json()
    assert (body["state"], body["available"], body["reason"]) == ("absent", False, "missing")


@pytest.mark.skipif(os.name == "nt", reason="shell stub")
def test_status_fallback_when_the_executable_does_not_answer_hello(client, monkeypatch, tmp_path):
    stub = tmp_path / "bobine-media"
    stub.write_text("#!/bin/sh\nexit 3\n")
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("BOBINE_MEDIA_BIN", str(stub))
    client.put("/api/settings", json={"media_native": "true"})
    body = client.get("/api/settings/media-native").json()
    assert body["state"] == "fallback" and body["available"] is True and body["reason"]


@pytest.mark.skipif(not BINARY.is_file(), reason="bobine-media not built")
def test_status_active_with_the_real_component_and_environment_forcing(client, monkeypatch):
    monkeypatch.setenv("BOBINE_MEDIA_BIN", str(BINARY))
    monkeypatch.setenv("BOBINE_MEDIA_NATIVE", "1")  # forced on although the setting is off
    body = client.get("/api/settings/media-native").json()
    assert body["state"] == "active" and body["source"] == "env" and body["setting"] is False
    assert body["forced_by_env"] is True and "m4a" in body["formats"] and body["binary_version"]
    monkeypatch.setenv("BOBINE_MEDIA_NATIVE", "0")
    assert client.get("/api/settings/media-native").json()["state"] == "disabled"


# --- covers ----------------------------------------------------------------------------

@pytest.fixture(scope="module")
def equivalence():
    spec = importlib.util.spec_from_file_location("cover_equivalence", ROOT / "scripts" / "media-bench" / "cover_equivalence.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _picture():
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (900, 700), (30, 60, 120))
    draw = ImageDraw.Draw(image)
    for step in range(0, 900, 30):
        draw.ellipse([step, step // 2, step + 140, step // 2 + 140], outline=(250 - step // 4, 90, step // 5), width=4)
    return image


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
@pytest.mark.parametrize("fmt", ["JPEG", "PNG"])
def test_native_cover_is_equivalent_to_the_reference_pipeline(tmp_path, equivalence, fmt):
    from app.utils import radio_utils

    picture = tmp_path / ("cover." + fmt.lower())
    _picture().save(picture, fmt)
    audio = tmp_path / "track.mp3"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "sine=duration=0.5",
                    "-i", str(picture), "-map", "0:a", "-map", "1:v", "-c:a", "libmp3lame", "-c:v", "copy",
                    "-disposition:v", "attached_pic", str(audio)], check=True)
    reference = radio_utils.extract_embedded_cover(str(audio), str(tmp_path / "ref"), "r")
    native = media_metadata._write_native_cover(picture.read_bytes(), str(tmp_path / "nat"), "n")
    assert reference and native and Path(native).name == "cover_n.jpg"
    measure = equivalence.measure(Path(reference).read_bytes(), Path(native).read_bytes())
    assert measure["equivalent"], measure
    assert not list((tmp_path / "nat").glob("*.tmp"))


def test_unreadable_raw_cover_falls_back_without_partial_file(tmp_path, monkeypatch):
    media_native.configure("true")
    client = Mock()
    client.extract_cover.return_value = CoverResult(available=True, data=b"\xff\xd8\xff not an image", mime="image/jpeg")
    monkeypatch.setattr(media_metadata, "get_media_client", Mock(return_value=client))
    reference = Mock(return_value="covers/from-ffmpeg.jpg")
    monkeypatch.setattr(media_metadata.radio_utils, "extract_embedded_cover", reference)
    assert media_metadata.extract_embedded_cover("a.mp3", str(tmp_path / "covers"), "x") == "covers/from-ffmpeg.jpg"
    reference.assert_called_once()
    assert not list((tmp_path / "covers").glob("*"))


def test_proven_absence_skips_the_reference(monkeypatch):
    media_native.configure("true")
    client = Mock()
    client.extract_cover.return_value = CoverResult(available=True)
    monkeypatch.setattr(media_metadata, "get_media_client", Mock(return_value=client))
    reference = Mock(side_effect=AssertionError("ffmpeg must not run"))
    monkeypatch.setattr(media_metadata.radio_utils, "extract_embedded_cover", reference)
    assert media_metadata.extract_embedded_cover("a.mp3", "covers", "x") is None


def test_equivalence_definition_rejects_a_visible_difference(equivalence):
    import io

    from PIL import Image

    def jpeg(image):
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=85)
        return buffer.getvalue()

    base = _picture()
    assert equivalence.measure(jpeg(base), jpeg(base))["equivalent"]
    assert equivalence.measure(jpeg(base), jpeg(base.resize((450, 350))))["reason"] == "dimensions"
    assert not equivalence.measure(jpeg(base), jpeg(Image.new("RGB", base.size, (255, 255, 255))))["equivalent"]
