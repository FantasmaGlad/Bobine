"""Horloge serveur du canal Radio (plan 4.0.1) : position fonction du temps,
fin de piste idempotente, filet de sécurité serveur."""

import asyncio
import os

# Base de test isolée AVANT tout import de l'application (comme les autres tests).
os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

from app.radio_manager import TRACK_END_GRACE_SECONDS, RadioPlaybackManager  # noqa: E402
from app.utils.playback_clock import PlaybackClock  # noqa: E402

TRACKS = [
    {"id": 11, "title": "A", "duration_seconds": 30.0},
    {"id": 12, "title": "B", "duration_seconds": 40.0},
    {"id": 13, "title": "C", "duration_seconds": 50.0},
]


class FakeTime:
    def __init__(self):
        self.mono = 9000.0
        self.epoch = 1_900_000_000_000.0

    def advance(self, seconds):
        self.mono += seconds
        self.epoch += seconds * 1000.0

    def clock(self):
        return PlaybackClock(monotonic=lambda: self.mono, epoch_ms=lambda: self.epoch)


def _manager(events=None):
    async def _bc(payload):
        if events is not None:
            events.append(payload["cause"])

    m = RadioPlaybackManager(_bc)
    fake = FakeTime()
    m._clock = fake.clock()
    return m, fake


def test_la_position_avance_sans_aucun_poste_radio_connecte():
    async def _run():
        m, fake = _manager()
        await m.load_playlist(1, "Ambiance", TRACKS, shuffle=False)
        fake.advance(9.0)
        snap = m.snapshot()
        assert snap["state"] == "playing"
        assert abs(snap["position_seconds"] - 9.0) < 1e-6
        assert snap["clock"]["running"] is True

    asyncio.run(_run())


def test_pause_play_seek_et_piste_suivante_pilotent_l_horloge():
    async def _run():
        m, fake = _manager()
        await m.load_playlist(1, "Ambiance", TRACKS, shuffle=False)
        fake.advance(10.0)
        await m.pause()
        fake.advance(60.0)
        assert abs(m.snapshot()["position_seconds"] - 10.0) < 1e-6
        await m.play()
        fake.advance(5.0)
        assert abs(m.snapshot()["position_seconds"] - 15.0) < 1e-6
        await m.seek(20.0)
        fake.advance(2.0)
        assert abs(m.snapshot()["position_seconds"] - 22.0) < 1e-6
        await m.next_track()
        fake.advance(1.0)
        snap = m.snapshot()
        assert snap["current_track"]["id"] == 12
        assert abs(snap["position_seconds"] - 1.0) < 1e-6

    asyncio.run(_run())


def test_precedent_apres_3_secondes_redemarre_la_piste_courante():
    async def _run():
        m, fake = _manager()
        await m.load_playlist(1, "Ambiance", TRACKS, shuffle=False)
        await m.next_track()
        fake.advance(10.0)
        await m.previous_track()   # > 3 s : redémarre la piste courante (B)
        fake.advance(1.0)
        snap = m.snapshot()
        assert snap["current_track"]["id"] == 12 and abs(snap["position_seconds"] - 1.0) < 1e-6
        await m.previous_track()   # < 3 s : piste précédente (A)
        assert m.snapshot()["current_track"]["id"] == 11

    asyncio.run(_run())


def test_fin_de_piste_idempotente_deux_postes_ne_sautent_pas_deux_pistes():
    async def _run():
        m, fake = _manager()
        await m.load_playlist(1, "Ambiance", TRACKS, shuffle=False)
        fake.advance(30.0)
        await m.track_ended(track_id=11)   # poste 1
        assert m.state["current_track"]["id"] == 12
        await m.track_ended(track_id=11)   # poste 2 : signal périmé de la piste A
        assert m.state["current_track"]["id"] == 12

    asyncio.run(_run())


def test_repetition_de_piste_relance_l_horloge_a_zero():
    async def _run():
        m, fake = _manager()
        await m.load_playlist(1, "Ambiance", TRACKS, shuffle=False, repeat="track")
        fake.advance(30.0)
        await m.track_ended(track_id=11)
        fake.advance(2.0)
        snap = m.snapshot()
        assert snap["current_track"]["id"] == 11 and abs(snap["position_seconds"] - 2.0) < 1e-6

    asyncio.run(_run())


def test_fin_de_playlist_sans_repetition_arrete_l_horloge():
    async def _run():
        m, fake = _manager()
        await m.load_playlist(1, "Ambiance", TRACKS[:1], shuffle=False)
        fake.advance(30.0)
        await m.track_ended(track_id=11)
        snap = m.snapshot()
        assert snap["state"] == "paused" and snap["clock"]["running"] is False and snap["position_seconds"] == 0.0

    asyncio.run(_run())


def test_le_serveur_enchaine_lui_meme_une_piste_depassee_et_pas_pendant_un_rappel():
    async def _run():
        m, fake = _manager()
        await m.load_playlist(1, "Ambiance", TRACKS, shuffle=False)
        fake.advance(30.0 + TRACK_END_GRACE_SECONDS - 0.1)
        assert await m._end_track_if_overdue() is False
        fake.advance(0.2)
        assert await m._end_track_if_overdue() is True
        assert m.state["current_track"]["id"] == 12
        # Pendant un rappel (état « announcing »), pas de filet : le rappel gère.
        m.state["state"] = "announcing"
        fake.advance(500.0)
        assert await m._end_track_if_overdue() is False

    asyncio.run(_run())


def test_le_rapport_de_position_d_un_poste_ne_modifie_plus_la_position():
    async def _run():
        m, fake = _manager()
        await m.load_playlist(1, "Ambiance", TRACKS, shuffle=False)
        fake.advance(7.0)
        await m.report_position(999.0)
        assert abs(m.snapshot()["position_seconds"] - 7.0) < 1e-6

    asyncio.run(_run())


def test_un_seul_poste_demarre_sans_delai_deux_postes_ensemble():
    async def _run():
        m, fake = _manager()
        m.display_counter = lambda channel: 1
        await m.load_playlist(1, "Ambiance", TRACKS, shuffle=False)
        await m.pause()
        await m.play()
        assert m.snapshot()["clock"]["at_ms"] <= int(fake.epoch) + 1
        m2, fake2 = _manager()
        m2.display_counter = lambda channel: 2
        await m2.load_playlist(1, "Ambiance", TRACKS, shuffle=False)
        await m2.pause()
        await m2.play()
        assert m2.snapshot()["clock"]["at_ms"] > int(fake2.epoch)

    asyncio.run(_run())


def test_la_regle_toutes_les_n_musiques_n_est_pas_comptee_deux_fois_par_un_doublon(monkeypatch):
    from app.routers import playback as playback_router

    async def _run():
        m, fake = _manager()
        await m.load_playlist(1, "Ambiance", TRACKS, shuffle=False)
        monkeypatch.setattr(playback_router, "_due_wait_end_announcement", lambda db, manager: None)
        fake.advance(30.0)
        await playback_router._handle_radio_track_ended(m, None, None, 11)   # poste 1
        await playback_router._handle_radio_track_ended(m, None, None, 11)   # poste 2 : doublon
        assert m.state["tracks_since_announcement"] == 1
        assert m.state["current_track"]["id"] == 12

    asyncio.run(_run())
