"""Horloge de lecture serveur : la position est une fonction
du temps, indépendante de tout kiosque."""

import asyncio

from app.playback_manager import (
    LOAD_LEAD_MS,
    PLAY_LEAD_MS,
    VIDEO_END_GRACE_SECONDS,
    PlaybackManager,
)
from app.utils.playback_clock import PlaybackClock


class FakeTime:
    """Horloges injectables : `mono` (secondes) et `epoch_ms` avancent ensemble."""

    def __init__(self):
        self.mono = 1000.0
        self.epoch = 1_700_000_000_000.0

    def advance(self, seconds: float):
        self.mono += seconds
        self.epoch += seconds * 1000.0

    def clock(self) -> PlaybackClock:
        return PlaybackClock(monotonic=lambda: self.mono, epoch_ms=lambda: self.epoch)


def test_position_avance_avec_le_temps_et_la_vitesse():
    t = FakeTime()
    c = t.clock()
    c.start(10.0)
    t.advance(5.0)
    assert c.position() == 15.0
    c.set_rate(2.0)
    t.advance(3.0)
    assert c.position() == 21.0  # 15 + 3 * 2, sans saut au changement de vitesse


def test_pause_fige_et_reprise_continue():
    t = FakeTime()
    c = t.clock()
    c.start(0.0)
    t.advance(4.0)
    c.pause()
    t.advance(100.0)
    assert c.position() == 4.0
    c.start()
    t.advance(1.0)
    assert c.position() == 5.0


def test_demarrage_synchronise_position_gelee_jusqu_a_l_instant_de_depart():
    t = FakeTime()
    c = t.clock()
    c.start(0.0, lead_ms=1000)
    t.advance(0.5)
    assert c.position() == 0.0
    anchor = c.to_dict()
    # L'ancre est l'instant de départ (dans le futur), pas « maintenant ».
    assert anchor["running"] is True
    assert anchor["pos"] == 0.0
    assert anchor["at_ms"] == int(round(t.epoch + 500))
    t.advance(1.5)
    assert c.position() == 1.0  # 1 s écoulée depuis l'instant de départ


def test_ancre_est_reancree_sur_maintenant_a_chaque_emission():
    t = FakeTime()
    c = t.clock()
    c.start(0.0)
    t.advance(30.0)
    a = c.to_dict()
    assert a["pos"] == 30.0 and a["at_ms"] == int(round(t.epoch))


def test_seek_conserve_l_etat_lecture_ou_pause():
    t = FakeTime()
    c = t.clock()
    c.start(0.0)
    c.seek(50.0)
    t.advance(2.0)
    assert c.position() == 52.0
    c.pause()
    c.seek(10.0)
    t.advance(5.0)
    assert c.position() == 10.0


def test_reset_remet_a_zero_et_conserve_la_vitesse():
    t = FakeTime()
    c = t.clock()
    c.set_rate(1.5)
    c.start(20.0)
    c.reset()
    assert c.position() == 0.0 and not c.running and c.rate == 1.5


# ---------------------------------------------------------------------------
# Intégration PlaybackManager
# ---------------------------------------------------------------------------

def _manager(received):
    async def _bc(payload):
        received.append(payload)

    return PlaybackManager(_bc, channel="network")


def _patch_clock(manager, fake: FakeTime):
    manager._clock = fake.clock()


def test_la_position_avance_sans_aucun_kiosque_connecte():
    """Cause racine S4 : sans kiosque primaire, la position restait figée."""
    received = []

    async def _run():
        m = _manager(received)
        fake = FakeTime()
        _patch_clock(m, fake)
        await m.load(1, "Cours", 120.0)
        fake.advance(10.0)  # aucun écran connecté : pas de délai de démarrage
        snap = m.snapshot()
        assert snap["state"] == "playing"
        assert abs(snap["position_seconds"] - 10.0) < 1e-6
        assert snap["clock"]["running"] is True

    asyncio.run(_run())
    assert received[0]["cause"] == "load"
    assert "clock" in received[0]["data"]


def test_play_pause_seek_vitesse_pilotent_l_horloge():
    async def _run():
        m = _manager([])
        fake = FakeTime()
        _patch_clock(m, fake)
        await m.load(1, "Cours", 600.0)
        fake.advance(20)
        await m.pause()
        fake.advance(50)
        assert abs(m.snapshot()["position_seconds"] - 20.0) < 1e-6
        await m.seek(100.0)
        assert m.snapshot()["position_seconds"] == 100.0
        await m.play()
        fake.advance(4)
        assert abs(m.snapshot()["position_seconds"] - 104.0) < 1e-6
        await m.set_speed(2.0)
        fake.advance(5)
        assert abs(m.snapshot()["position_seconds"] - 114.0) < 1e-6
        await m.stop()
        assert m.snapshot()["position_seconds"] == 0.0
        assert m.snapshot()["clock"]["running"] is False

    asyncio.run(_run())


def test_report_position_ne_modifie_plus_la_position():
    async def _run():
        m = _manager([])
        fake = FakeTime()
        _patch_clock(m, fake)
        await m.load(1, "Cours", 600.0)
        fake.advance(7.0)
        await m.report_position(999.0)
        assert abs(m.snapshot()["position_seconds"] - 7.0) < 1e-6

    asyncio.run(_run())


def test_video_ended_est_idempotent_et_ignore_le_signal_d_un_autre_cours():
    """Tous les écrans envoient `video_ended` : le 2e signal ne doit pas
    terminer le cours suivant."""
    async def _run():
        m = _manager([])
        fake = FakeTime()
        _patch_clock(m, fake)
        items = [
            {"id": 1, "title": "A", "duration_seconds": 10.0},
            {"id": 2, "title": "B", "duration_seconds": 10.0},
        ]
        await m.load_playlist(5, "P", items)
        # wait_time_between_courses est lu dans settings ; on force 0 pour
        # que le cours suivant démarre aussitôt.
        from app.config import settings
        settings.wait_time_between_courses = 0
        await m.video_ended(video_id=1)          # écran 1
        await asyncio.sleep(0.05)
        assert m.state["current_video"]["id"] == 2
        await m.video_ended(video_id=1)          # écran 2, signal tardif du cours 1
        assert m.state["current_video"]["id"] == 2
        assert m.state["state"] == "playing"

    asyncio.run(_run())


def test_le_serveur_termine_lui_meme_un_cours_depasse():
    async def _run():
        m = _manager([])
        fake = FakeTime()
        _patch_clock(m, fake)
        await m.load(1, "Cours", 30.0)
        fake.advance(30.0 + VIDEO_END_GRACE_SECONDS - 0.1)
        assert await m._end_video_if_overdue() is False
        fake.advance(0.2)
        assert await m._end_video_if_overdue() is True
        assert m.state["state"] == "waiting"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Délai de démarrage synchronisé ADAPTATIF (réponse immédiate avec un seul écran)
# ---------------------------------------------------------------------------

def test_un_seul_ecran_ou_aucun_demarre_sans_delai():
    """Mesuré avant correction : play = 300 ms, chargement = 1 009 ms de latence
    ressentie, alors que pause répondait en 1 à 3 ms."""
    async def _run():
        for screens in (0, 1):
            m = _manager([])
            m.display_counter = lambda channel, n=screens: n
            fake = FakeTime()
            _patch_clock(m, fake)
            await m.load(1, "Cours", 600.0)
            anchor = m.snapshot()["clock"]
            assert anchor["at_ms"] <= int(fake.epoch) + 1, f"{screens} écran(s) : départ différé"
            await m.pause()
            await m.play()
            assert m.snapshot()["clock"]["at_ms"] <= int(fake.epoch) + 1
            await m.seek(30.0)
            assert m.snapshot()["clock"]["at_ms"] <= int(fake.epoch) + 1

    asyncio.run(_run())


def test_plusieurs_ecrans_demarrent_ensemble_a_un_instant_commun_futur():
    async def _run():
        m = _manager([])
        m.display_counter = lambda channel: 2
        fake = FakeTime()
        _patch_clock(m, fake)
        await m.load(1, "Cours", 600.0)
        assert m.snapshot()["clock"]["at_ms"] == int(round(fake.epoch + LOAD_LEAD_MS))
        fake.advance(LOAD_LEAD_MS / 1000)
        await m.pause()
        await m.play()
        assert m.snapshot()["clock"]["at_ms"] == int(round(fake.epoch + PLAY_LEAD_MS))

    asyncio.run(_run())


def test_un_compteur_d_ecrans_defaillant_ne_bloque_jamais_la_lecture():
    async def _run():
        m = _manager([])

        def boom(channel):
            raise RuntimeError("compteur indisponible")

        m.display_counter = boom
        fake = FakeTime()
        _patch_clock(m, fake)
        await m.load(1, "Cours", 600.0)
        assert m.snapshot()["clock"]["at_ms"] <= int(fake.epoch) + 1

    asyncio.run(_run())


def test_l_epoch_change_a_chaque_ordre_et_reste_stable_entre_deux_heartbeats():
    """Permet à un écran de distinguer un ORDRE explicite (à appliquer sans délai
    de grâce) d'une simple dérive."""
    t = FakeTime()
    c = t.clock()
    e0 = c.to_dict()["epoch"]
    c.start(0.0)
    e1 = c.to_dict()["epoch"]
    t.advance(5)
    assert c.to_dict()["epoch"] == e1  # simple heartbeat : inchangé
    c.seek(40.0)
    e2 = c.to_dict()["epoch"]
    c.pause()
    e3 = c.to_dict()["epoch"]
    c.set_rate(1.5)
    e4 = c.to_dict()["epoch"]
    c.reset()
    e5 = c.to_dict()["epoch"]
    assert len({e0, e1, e2, e3, e4, e5}) == 6
