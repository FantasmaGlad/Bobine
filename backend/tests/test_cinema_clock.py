import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest  # noqa: E402

from app.api.routes import playback as pb  # noqa: E402
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
    monkeypatch.setattr(pb.cinema, "_cinema_clocks", {})
    monkeypatch.setattr(pb.cinema, "_cinema_launched_video", {})
    monkeypatch.setattr(pb.commands, "_cinema_launched_video", {})
    monkeypatch.setattr(pb.cinema, "PlaybackClock", f.clock)
    return f


def test_sans_launch_aucune_horloge_n_est_jointe_aux_ordres(fake):
    pb.cinema._apply_cinema_command_to_clock("cable", "play", {})
    pb.cinema._apply_cinema_command_to_clock("cable", "seek", {"position_seconds": 50})
    assert "cable" not in pb.cinema._cinema_launched_video


def test_launch_cree_l_horloge_puis_play_pause_seek_la_pilotent(fake):
    pb.cinema._apply_cinema_command_to_clock("cable", "launch", {"video_id": 7})
    clock = pb.cinema._cinema_clock_for("cable")
    assert pb.cinema._cinema_launched_video["cable"] == 7 and clock.running
    fake.advance(10.0)
    assert abs(clock.position() - 10.0) < 1e-6
    pb.cinema._apply_cinema_command_to_clock("cable", "pause", {})
    fake.advance(30.0)
    assert abs(clock.position() - 10.0) < 1e-6 and not clock.running
    pb.cinema._apply_cinema_command_to_clock("cable", "seek", {"position_seconds": 60})
    assert abs(clock.position() - 60.0) < 1e-6 and not clock.running
    pb.cinema._apply_cinema_command_to_clock("cable", "play", {})
    fake.advance(2.0)
    assert abs(clock.position() - 62.0) < 1e-6


def test_un_launch_peut_reprendre_a_une_position(fake):
    pb.cinema._apply_cinema_command_to_clock("cable", "launch", {"video_id": 3, "position_seconds": 45})
    fake.advance(5.0)
    assert abs(pb.cinema._cinema_clock_for("cable").position() - 50.0) < 1e-6


def test_stop_detruit_le_cours_lance_par_ordre(fake):
    pb.cinema._apply_cinema_command_to_clock("cable", "launch", {"video_id": 7})
    pb.cinema._apply_cinema_command_to_clock("cable", "stop", {})
    assert "cable" not in pb.cinema._cinema_launched_video
    assert not pb.cinema._cinema_clock_for("cable").running
    pb.cinema._apply_cinema_command_to_clock("cable", "play", {})
    assert "cable" not in pb.cinema._cinema_launched_video


def test_les_canaux_sont_independants(fake):
    pb.cinema._apply_cinema_command_to_clock("cable", "launch", {"video_id": 1})
    pb.cinema._apply_cinema_command_to_clock("network", "launch", {"video_id": 2})
    fake.advance(4.0)
    pb.cinema._apply_cinema_command_to_clock("network", "pause", {})
    fake.advance(6.0)
    assert abs(pb.cinema._cinema_clock_for("cable").position() - 10.0) < 1e-6
    assert abs(pb.cinema._cinema_clock_for("network").position() - 4.0) < 1e-6
    assert pb.cinema._cinema_launched_video == {"cable": 1, "network": 2}
