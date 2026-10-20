"""New-import native opt-in, strict fallback and filename/cover preservation."""
import importlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import wave

import pytest

from app.utils import media_metadata
from app.utils.media_sidecar import CoverResult, MediaClient


def metadata(**overrides):
    value = {
        "title": None, "artist": "Artist", "album": "Album", "album_artist": None,
        "track_number": 3, "disc_number": None, "year": 2024, "genre": None,
        "duration_seconds": 1.25,
    }
    value.update(overrides)
    return value


@pytest.mark.parametrize("flag", [None, "", "0", "true"])
def test_default_off_preserves_reference_and_never_creates_client(monkeypatch, flag):
    if flag is None:
        monkeypatch.delenv("BOBINE_MEDIA_NATIVE", raising=False)
    else:
        monkeypatch.setenv("BOBINE_MEDIA_NATIVE", flag)
    native = Mock(side_effect=AssertionError("disabled imports must not create native client"))
    monkeypatch.setattr(media_metadata, "get_media_client", native)
    radio = Mock(return_value=metadata(title="Reference"))
    duration = Mock(return_value=2.5)
    cover = Mock(return_value="covers/reference.jpg")
    monkeypatch.setattr(media_metadata.radio_utils, "extract_radio_metadata", radio)
    monkeypatch.setattr(media_metadata.audio_utils, "extract_audio_duration", duration)
    monkeypatch.setattr(media_metadata.radio_utils, "extract_embedded_cover", cover)
    assert media_metadata.extract_radio_metadata("track.mp3") == radio.return_value
    assert media_metadata.extract_audio_duration("track.mp3") == 2.5
    assert media_metadata.extract_embedded_cover("track.mp3", "covers", "id") == "covers/reference.jpg"
    radio.assert_called_once_with("track.mp3")
    duration.assert_called_once_with("track.mp3")
    cover.assert_called_once_with("track.mp3", "covers", "id")
    native.assert_not_called()


def test_native_radio_preserves_filename_fallback_without_mutating_client_result(monkeypatch):
    monkeypatch.setenv("BOBINE_MEDIA_NATIVE", "1")
    original = metadata()
    client = Mock()
    client.probe_audio.return_value = original
    monkeypatch.setattr(media_metadata, "get_media_client", Mock(return_value=client))
    reference = Mock(side_effect=AssertionError("successful native probe must not run ffprobe"))
    monkeypatch.setattr(media_metadata.radio_utils, "extract_radio_metadata", reference)
    result = media_metadata.extract_radio_metadata("01 - Warm_Up.mp3")
    assert result == metadata(title="01 - Warm Up")
    assert original["title"] is None
    client.probe_audio.assert_called_once_with("01 - Warm_Up.mp3", "radio-v1")
    reference.assert_not_called()


def test_native_course_consumes_only_duration_and_uses_distinct_profile(monkeypatch):
    monkeypatch.setenv("BOBINE_MEDIA_NATIVE", "1")
    client = Mock()
    client.probe_audio.return_value = metadata(title="Unrelated ID3 title", track_number=999)
    monkeypatch.setattr(media_metadata, "get_media_client", Mock(return_value=client))
    reference = Mock(side_effect=AssertionError("successful native duration must not run ffprobe"))
    monkeypatch.setattr(media_metadata.audio_utils, "extract_audio_duration", reference)
    assert media_metadata.extract_audio_duration("01 - Intro.mp3") == 1.25
    client.probe_audio.assert_called_once_with("01 - Intro.mp3", "course-duration-v1")


def test_probe_failure_executes_each_historical_path_in_same_call(monkeypatch):
    monkeypatch.setenv("BOBINE_MEDIA_NATIVE", "1")
    client = Mock()
    client.probe_audio.return_value = None
    monkeypatch.setattr(media_metadata, "get_media_client", Mock(return_value=client))
    radio = Mock(return_value=metadata(title="Reference", duration_seconds=None))
    course = Mock(return_value=None)
    monkeypatch.setattr(media_metadata.radio_utils, "extract_radio_metadata", radio)
    monkeypatch.setattr(media_metadata.audio_utils, "extract_audio_duration", course)
    assert media_metadata.extract_radio_metadata("unsupported.wma") == radio.return_value
    assert media_metadata.extract_audio_duration("unsupported.wma") is None
    radio.assert_called_once_with("unsupported.wma")
    course.assert_called_once_with("unsupported.wma")


@pytest.mark.parametrize("result,expected_calls", [
    (CoverResult(available=True), 0),
    (CoverResult(available=False), 1),
    (CoverResult(available=True, data=b"raw PNG image", mime="image/png"), 1),
])
def test_only_proven_cover_absence_skips_reference(monkeypatch, result, expected_calls):
    monkeypatch.setenv("BOBINE_MEDIA_NATIVE", "1")
    client = Mock()
    client.extract_cover.return_value = result
    monkeypatch.setattr(media_metadata, "get_media_client", Mock(return_value=client))
    reference = Mock(return_value="covers/cover_id.jpg")
    monkeypatch.setattr(media_metadata.radio_utils, "extract_embedded_cover", reference)
    actual = media_metadata.extract_embedded_cover("track.mp3", "covers", "id")
    assert actual == ("covers/cover_id.jpg" if expected_calls else None)
    assert reference.call_count == expected_calls
    if expected_calls:
        reference.assert_called_once_with("track.mp3", "covers", "id")


@pytest.mark.parametrize("native_success", [True, False])
def test_radio_ingest_reads_source_before_move_and_keeps_existing_model_contract(tmp_path, monkeypatch, native_success):
    monkeypatch.setenv("BOBINE_MEDIA_NATIVE", "1")
    importer = importlib.import_module("app.utils.radio_importer")
    from app.models import ImportSource

    source = tmp_path / "03_Music.mp3"
    source.write_bytes(b"synthetic input; extraction mocked")
    target = tmp_path / "radio"
    covers = tmp_path / "covers"
    monkeypatch.setattr(importer, "settings", SimpleNamespace(radio_dir=str(target), radio_covers_dir=str(covers)))
    client = Mock()

    def probe(path, profile):
        assert Path(path) == source and source.exists()
        assert profile == "radio-v1"
        return metadata() if native_success else None

    def cover(path):
        assert Path(path) == source and source.exists()
        return CoverResult(available=native_success)

    client.probe_audio.side_effect = probe
    client.extract_cover.side_effect = cover
    monkeypatch.setattr(media_metadata, "get_media_client", Mock(return_value=client))
    reference = Mock(return_value=metadata(title="Reference"))
    reference_cover = Mock(return_value=None)
    monkeypatch.setattr(media_metadata.radio_utils, "extract_radio_metadata", reference)
    monkeypatch.setattr(media_metadata.radio_utils, "extract_embedded_cover", reference_cover)
    db = Mock()
    track = importer._ingest_one(db, source, ImportSource.upload)
    assert track.title == ("03 Music" if native_success else "Reference")
    assert track.duration_seconds == 1.25 and track.track_number == 3
    assert track.artist == "Artist" and track.album == "Album"
    assert track.cover_path is None
    assert Path(track.file_path).exists() and not source.exists()
    assert Path(track.file_path).read_bytes() == b"synthetic input; extraction mocked"
    db.add.assert_called_once_with(track)
    assert reference.call_count == (0 if native_success else 1)
    assert reference_cover.call_count == (0 if native_success else 1)


def test_course_import_preserves_filename_titles_order_and_ignores_tag_numbers(tmp_path, monkeypatch):
    monkeypatch.setenv("BOBINE_MEDIA_NATIVE", "1")
    importer = importlib.import_module("app.utils.audio_importer")
    from app.models import AudioTrack

    source_a, source_b = tmp_path / "02 - Climb.mp3", tmp_path / "01_Warm_Up.mp3"
    source_a.write_bytes(b"second")
    source_b.write_bytes(b"first")
    monkeypatch.setattr(importer, "settings", SimpleNamespace(audio_dir=str(tmp_path / "courses")))
    db = Mock()
    monkeypatch.setattr(importer, "SessionLocal", lambda: db)
    monkeypatch.setattr(importer, "log_activity", Mock())
    client = Mock()

    def probe(path, profile):
        assert Path(path).exists() and profile == "course-duration-v1"
        return metadata(title="Ignored ID3", track_number=999)

    client.probe_audio.side_effect = probe
    monkeypatch.setattr(media_metadata, "get_media_client", Mock(return_value=client))
    course = importer.import_audio_course_from_files([str(source_a), str(source_b)], "Synthetic course")
    tracks = [args.args[0] for args in db.add.call_args_list if isinstance(args.args[0], AudioTrack)]
    assert course.title == "Synthetic course"
    assert [(track.number, track.title, track.position) for track in tracks] == [(1,"Warm Up",0),(2,"Climb",1)]
    assert [track.duration_seconds for track in tracks] == [1.25, 1.25]
    assert [Path(track.file_path).read_bytes() for track in tracks] == [b"first", b"second"]
    assert not source_a.exists() and not source_b.exists()
    db.commit.assert_called_once()
    db.close.assert_called_once()


def test_real_component_new_import_wrappers_and_corrupt_fallback(tmp_path, monkeypatch):
    binary = Path(__file__).resolve().parents[2] / "media" / "target" / "release" / "bobine-media"
    if not binary.is_file():
        pytest.skip("optional native component has not been built")
    monkeypatch.setenv("BOBINE_MEDIA_NATIVE", "1")
    source = tmp_path / "01_Native_WAV.wav"
    with wave.open(str(source), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(b"\0\0" * 8000)
    client = MediaClient(command=[str(binary)], timeout=5)
    monkeypatch.setattr(media_metadata, "get_media_client", lambda: client)
    radio_ref, audio_ref, cover_ref = Mock(), Mock(), Mock()
    monkeypatch.setattr(media_metadata.radio_utils, "extract_radio_metadata", radio_ref)
    monkeypatch.setattr(media_metadata.audio_utils, "extract_audio_duration", audio_ref)
    monkeypatch.setattr(media_metadata.radio_utils, "extract_embedded_cover", cover_ref)
    try:
        assert media_metadata.extract_radio_metadata(str(source))["title"] == "01 Native WAV"
        assert media_metadata.extract_audio_duration(str(source)) == pytest.approx(1.0,abs=0.001)
        assert media_metadata.extract_embedded_cover(str(source), str(tmp_path / "covers"), "native") is None
        radio_ref.assert_not_called()
        audio_ref.assert_not_called()
        cover_ref.assert_not_called()
        bad = tmp_path / "bad.mp3"
        bad.write_bytes(b"corrupt")
        radio_ref.return_value = metadata(title="Reference for corrupt input",duration_seconds=None)
        assert media_metadata.extract_radio_metadata(str(bad)) == radio_ref.return_value
        radio_ref.assert_called_once_with(str(bad))
    finally:
        client.close()
