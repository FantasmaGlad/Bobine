"""Horloge serveur du mode coach (plan 4.0.1) : la position de la piste audio est
une fonction du temps, la fin de piste est idempotente."""

import asyncio

from app.playback_manager import AUDIO_END_GRACE_SECONDS, PlaybackManager
from app.utils.playback_clock import PlaybackClock

TRACKS = [
    {"id": 1, "number": 1, "title": "Warm Up", "duration_seconds": 30.0},
    {"id": 2, "number": 2, "title": "Climb", "duration_seconds": 40.0},
    {"id": 3, "number": 3, "title": "Sprint", "duration_seconds": 50.0},
]


class FakeTime:
    def __init__(self):
        self.mono = 5000.0
        self.epoch = 1_800_000_000_000.0

    def advance(self, seconds):
        self.mono += seconds
        self.epoch += seconds * 1000.0

    def clock(self):
        return PlaybackClock(monotonic=lambda: self.mono, epoch_ms=lambda: self.epoch)


def _manager():
    async def _bc(payload):
        pass

    m = PlaybackManager(_bc, channel="cable")
    fake = FakeTime()
    m._audio_clock = fake.clock()
    m._clock = fake.clock()
    return m, fake


def test_la_piste_avance_sans_aucun_ecran_connecte_et_expose_son_ancre():
    async def _run():
        m, fake = _manager()
        await m.load_audio_course(1, "RPM", "RPM", None, TRACKS)
        assert m.snapshot()["audio_clock"]["running"] is False  # démarre en pause
        await m.play()
        fake.advance(12.0)
        snap = m.snapshot()
        assert abs(snap["audio_position_seconds"] - 12.0) < 1e-6
        assert snap["audio_clock"]["running"] is True
        await m.pause()
        fake.advance(30.0)
        assert abs(m.snapshot()["audio_position_seconds"] - 12.0) < 1e-6
        await m.play()
        fake.advance(5.0)
        assert abs(m.snapshot()["audio_position_seconds"] - 17.0) < 1e-6

    asyncio.run(_run())


def test_piste_suivante_et_relance_remettent_l_horloge_a_zero():
    async def _run():
        m, fake = _manager()
        await m.load_audio_course(1, "RPM", "RPM", None, TRACKS)
        await m.play()
        fake.advance(20.0)
        await m.audio_next_track()
        fake.advance(3.0)
        snap = m.snapshot()
        assert snap["audio_track_index"] == 1
        assert abs(snap["audio_position_seconds"] - 3.0) < 1e-6
        await m.audio_restart_track()
        fake.advance(1.0)
        assert abs(m.snapshot()["audio_position_seconds"] - 1.0) < 1e-6

    asyncio.run(_run())


def test_fin_de_piste_idempotente_deux_ecrans_ne_sautent_pas_deux_pistes():
    """Tous les écrans envoient `audio_track_ended` : en mode auto, le second
    signal (même piste) sautait une piste de plus."""
    async def _run():
        m, fake = _manager()
        await m.load_audio_course(1, "RPM", "RPM", None, TRACKS, chain_mode="auto")
        await m.play()
        fake.advance(30.0)
        await m.audio_track_ended(track_index=0)   # écran 1
        assert m.state["audio_track_index"] == 1
        await m.audio_track_ended(track_index=0)   # écran 2 : signal tardif de la piste 0
        assert m.state["audio_track_index"] == 1
        assert m.state["audio_playing"] is True

    asyncio.run(_run())


def test_fin_de_piste_en_mode_manuel_et_minuterie_ne_se_rejoue_pas():
    async def _run():
        m, fake = _manager()
        await m.load_audio_course(1, "RPM", "RPM", None, TRACKS, chain_mode="manual")
        await m.play()
        fake.advance(30.0)
        await m.audio_track_ended(track_index=0)
        assert m.state["audio_playing"] is False
        assert m.snapshot()["audio_clock"]["running"] is False
        await m.audio_track_ended(track_index=0)   # doublon : sans effet
        assert m.state["audio_track_index"] == 0

    asyncio.run(_run())


def test_le_serveur_enchaine_lui_meme_une_piste_depassee():
    async def _run():
        m, fake = _manager()
        await m.load_audio_course(1, "RPM", "RPM", None, TRACKS, chain_mode="auto")
        await m.play()
        fake.advance(30.0 + AUDIO_END_GRACE_SECONDS - 0.1)
        assert await m._end_audio_track_if_overdue() is False
        fake.advance(0.2)
        assert await m._end_audio_track_if_overdue() is True
        assert m.state["audio_track_index"] == 1

    asyncio.run(_run())


def test_le_rapport_de_position_d_un_ecran_ne_modifie_plus_la_position_audio():
    async def _run():
        m, fake = _manager()
        await m.load_audio_course(1, "RPM", "RPM", None, TRACKS)
        await m.play()
        fake.advance(8.0)
        await m.audio_report_position(999.0)
        assert abs(m.snapshot()["audio_position_seconds"] - 8.0) < 1e-6

    asyncio.run(_run())


def test_sortie_du_mode_coach_remet_l_horloge_audio_a_zero():
    async def _run():
        m, fake = _manager()
        await m.load_audio_course(1, "RPM", "RPM", None, TRACKS)
        await m.play()
        fake.advance(10.0)
        await m.stop()
        snap = m.snapshot()
        assert snap["audio_clock"]["running"] is False
        assert snap["audio_position_seconds"] == 0.0

    asyncio.run(_run())

