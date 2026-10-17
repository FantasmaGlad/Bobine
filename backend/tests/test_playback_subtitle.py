"""Choix des sous-titres depuis l'admin : état diffusé aux kiosques du canal."""

import asyncio

from tests.test_playback_clock import FakeTime, _manager, _patch_clock


def test_choix_de_sous_titres_diffuse_et_remis_a_zero_au_prochain_cours():
    async def _run():
        received: list[dict] = []
        m = _manager(received)
        _patch_clock(m, FakeTime())
        await m.load(1, "Cours", 600.0)
        assert m.snapshot()["subtitle"] is None

        await m.set_subtitle(7)
        assert m.snapshot()["subtitle"] == 7
        assert received[-1]["cause"] == "subtitle"

        await m.set_subtitle("off")
        assert m.snapshot()["subtitle"] == "off"

        await m.set_subtitle("n'importe quoi")
        assert m.snapshot()["subtitle"] == "off"  # valeur invalide ignorée

        await m.load(2, "Autre cours", 300.0)
        assert m.snapshot()["subtitle"] is None

    asyncio.run(_run())
