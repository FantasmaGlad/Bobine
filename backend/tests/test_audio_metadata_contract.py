"""Freeze existing ffprobe semantics before changing metadata extraction."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.audio_utils import extract_audio_duration, parse_track_number_and_title
from app.utils.radio_utils import extract_radio_metadata


class AudioMetadataContractTests(unittest.TestCase):
    def probe(self, payload):
        return patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, json.dumps(payload), ""))

    def test_radio_uses_only_container_duration(self):
        for duration in (None, "bad", ""):
            with self.subTest(duration=duration), self.probe({"format": {"duration": duration},
                                                            "streams": [{"codec_type": "audio", "duration": "12.5"}]}):
                self.assertIsNone(extract_radio_metadata("test.mp3")["duration_seconds"])
        with self.probe({"format": {"duration": "3.125"}, "streams": [{"duration": "12.5"}]}):
            self.assertEqual(extract_radio_metadata("test.mp3")["duration_seconds"], 3.125)

    def test_course_prefers_container_then_first_stream_with_duration(self):
        for payload, expected in [
            ({"format": {"duration": "3.125"}, "streams": [{"duration": "12.5"}]}, 3.125),
            ({"format": {}, "streams": [{"duration": None}, {"codec_type": "video", "duration": "2.5"}, {"codec_type": "audio", "duration": "9"}]}, 2.5),
            ({"streams": [{"duration": "bad"}, {"duration": "9"}]}, None),
            ({"format": {"duration": "bad"}, "streams": [{"duration": "9"}]}, None),
            ({"format": {"duration": ""}, "streams": [{"duration": "9"}]}, None),
            ({"streams": []}, None),
        ]:
            with self.subTest(payload=payload), self.probe(payload):
                self.assertEqual(extract_audio_duration("test.mp3"), expected)

    def test_container_exact_key_wins_but_later_case_collision_wins(self):
        for container, stream, expected in [
            ({"title": "Container"}, {"title": "Stream"}, "Container"),
            ({"TITLE": "Container"}, {"title": "Stream"}, "Stream"),
            ({"title": "Container"}, {"TITLE": "Stream"}, "Stream"),
            ({"TITLE": "First", "title": "Last"}, {}, "Last"),
        ]:
            with self.subTest(container=container, stream=stream), self.probe({
                "format": {"tags": container}, "streams": [{"codec_type": "audio", "tags": stream}]
            }):
                self.assertEqual(extract_radio_metadata("test.mp3")["title"], expected)

    def test_only_first_audio_stream_tags_are_merged(self):
        with self.probe({"streams": [
            {"codec_type": "video", "tags": {"title": "Image"}},
            {"codec_type": "audio", "tags": {"artist": "First"}},
            {"codec_type": "audio", "tags": {"title": "Second", "artist": "Second"}},
        ]}):
            result = extract_radio_metadata("fallback_name.mp3")
        self.assertEqual(result["artist"], "First")
        self.assertEqual(result["title"], "fallback name")

    def test_alias_priority_and_value_parsing(self):
        with self.probe({"format": {"tags": {
            "title": "  Été 東京 🎵  ", "artist": " ", "author": "  Author ", "performer": "Performer",
            "album": " Album ", "album_artist": " ", "ALBUMARTIST": " Ensemble ", "band": "Band",
            "track": "003/12", "tracknumber": "9", "disk": "02/04", "date": "recorded in 1999-07",
            "year": "2024", "genre": " Synthetic ",
        }}}):
            self.assertEqual(extract_radio_metadata("file.mp3"), {
                "title": "Été 東京 🎵", "artist": "Author", "album": "Album", "album_artist": "Ensemble",
                "track_number": 3, "disc_number": 2, "year": 1999, "genre": "Synthetic", "duration_seconds": None,
            })

    def test_bad_preferred_alias_does_not_fall_through_after_parsing(self):
        with self.probe({"format": {"tags": {"track": "side A", "tracknumber": "2", "date": "unknown", "year": "2024"}}}):
            result = extract_radio_metadata("test.mp3")
        self.assertIsNone(result["track_number"])
        self.assertIsNone(result["year"])

    def test_number_prefix_and_year_match_are_not_normalized(self):
        for track, expected in [("-1", None), ("0000", 0), ("12345", 1234), ("05abc", 5)]:
            with self.subTest(track=track), self.probe({"format": {"tags": {"tracknumber": track, "originalyear": "x12345"}}}):
                result = extract_radio_metadata("test.mp3")
                self.assertEqual(result["track_number"], expected)
                self.assertEqual(result["year"], 1234)

    def test_title_fallback_preserves_radio_course_difference(self):
        with self.probe({"format": {"tags": {"title": " "}}}):
            self.assertEqual(extract_radio_metadata("01 - My_song.mp3")["title"], "01 - My song")
        self.assertEqual(parse_track_number_and_title("01 - My_song.mp3"), (1, "My song"))

    def test_probe_failure_and_invalid_json_keep_fallback(self):
        for error in (subprocess.CalledProcessError(1, "ffprobe"), FileNotFoundError()):
            with self.subTest(error=type(error).__name__), patch("subprocess.run", side_effect=error):
                self.assertEqual(extract_radio_metadata("failed_name.mp3")["title"], "failed name")
                self.assertIsNone(extract_audio_duration("failed_name.mp3"))
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, "bad json", "")):
            self.assertIsNone(extract_radio_metadata("test.mp3")["duration_seconds"])
            self.assertIsNone(extract_audio_duration("test.mp3"))


if __name__ == "__main__":
    unittest.main()
