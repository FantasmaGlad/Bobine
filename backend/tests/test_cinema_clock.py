"""Horloge du cours /cinema lancé par ordre (plan 4.0.1) : créée par `launch`,
pilotée par play/pause/seek, détruite par `stop`, jamais jointe à une lecture locale."""

import os

# Base de test isolée AVANT tout import de l'application (comme les autres tests).
os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest  # noqa: E402

from app.routers import playback as pb  # noqa: E402
from app.utils.playback_clock import PlaybackClock  # noqa: E402


class FakeTime:
    def __init__(self):
        self.mono = 100.0
        self.epoch = 1_950_000_000_000.0

    def advance(self, s):
        self.mono += s
        self.epoch += s * 1000.0

    def clock(self):
        return PlaybackClock(monotonic=lambda: self.mono, epoch_ms=lambda: self.epoch)


@pytest.fixture()
def fake(monkeypatch):
    f = FakeTime()
    monkeypatch.setattr(pb, "_cinema_clocks", {})
    monkeypatch.setattr(pb, "_cinema_launched_video", {})
    monkeypatch.setattr(pb, "PlaybackClock", f.clock)
    return f


def test_sans_launch_aucune_horloge_n_est_jointe_aux_ordres(fake):
    pb._apply_cinema_command_to_clock("cable", "play", {})
    pb._apply_cinema_command_to_clock("cable", "seek", {"position_seconds": 50})
    assert "cable" not in pb._cinema_launched_video


def test_launch_cree_l_horloge_puis_play_pause_seek_la_pilotent(fake):
    pb._apply_cinema_command_to_clock("cable", "launch", {"video_id": 7})
    clock = pb._cinema_clock_for("cable")
    assert pb._cinema_launched_video["cable"] == 7 and clock.running
    fake.advance(10.0)
    assert abs(clock.position() - 10.0) < 1e-6
    pb._apply_cinema_command_to_clock("cable", "pause", {})
    fake.advance(30.0)
    assert abs(clock.position() - 10.0) < 1e-6 and not clock.running
    pb._apply_cinema_command_to_clock("cable", "seek", {"position_seconds": 60})
    assert abs(clock.position() - 60.0) < 1e-6 and not clock.running
    pb._apply_cinema_command_to_clock("cable", "play", {})
    fake.advance(2.0)
    assert abs(clock.position() - 62.0) < 1e-6


def test_un_launch_peut_reprendre_a_une_position(fake):
    pb._apply_cinema_command_to_clock("cable", "launch", {"video_id": 3, "position_seconds": 45})
    fake.advance(5.0)
    assert abs(pb._cinema_clock_for("cable").position() - 50.0) < 1e-6


def test_stop_detruit_le_cours_lance_par_ordre(fake):
    pb._apply_cinema_command_to_clock("cable", "launch", {"video_id": 7})
    pb._apply_cinema_command_to_clock("cable", "stop", {})
    assert "cable" not in pb._cinema_launched_video
    assert not pb._cinema_clock_for("cable").running
    # Un ordre ultérieur sans nouveau launch n'a plus d'horloge à piloter.
    pb._apply_cinema_command_to_clock("cable", "play", {})
    assert "cable" not in pb._cinema_launched_video


def test_les_canaux_sont_independants(fake):
    pb._apply_cinema_command_to_clock("cable", "launch", {"video_id": 1})
    pb._apply_cinema_command_to_clock("network", "launch", {"video_id": 2})
    fake.advance(4.0)
    pb._apply_cinema_command_to_clock("network", "pause", {})
    fake.advance(6.0)
    assert abs(pb._cinema_clock_for("cable").position() - 10.0) < 1e-6
    assert abs(pb._cinema_clock_for("network").position() - 4.0) < 1e-6
    assert pb._cinema_launched_video == {"cable": 1, "network": 2}
