"""Renforcement reseaux imparfaits (retour utilisateur, session Android) :
`position_tick` porte un numero de sequence croissant, jamais reinitialise,
pour que le client detecte un tick perdu en silence et resynchronise
immediatement au lieu d'attendre le prochain cycle du filet de securite
REST periodique (15s, cf. usePlaybackSocket.ts)."""

import asyncio

from app.playback_manager import PlaybackManager


def test_position_tick_carries_an_incrementing_sequence_number():
    received = []

    async def _fake_broadcast(payload):
        received.append(payload)

    async def _run():
        manager = PlaybackManager(_fake_broadcast, channel="network")
        await manager._emit("position_tick")
        await manager._emit("position_tick")
        await manager._emit("position_tick")

    asyncio.run(_run())

    assert [p["tick_seq"] for p in received] == [1, 2, 3]


def test_non_tick_causes_never_carry_a_tick_seq():
    received = []

    async def _fake_broadcast(payload):
        received.append(payload)

    async def _run():
        manager = PlaybackManager(_fake_broadcast, channel="cable")
        await manager._emit("play")
        await manager._emit("position_tick")
        await manager._emit("pause")

    asyncio.run(_run())

    assert "tick_seq" not in received[0]
    assert received[1]["tick_seq"] == 1
    assert "tick_seq" not in received[2]


def test_tick_sequence_is_never_reset_across_a_new_load():
    """Le compteur suit le CANAL, pas la video en cours : un changement de
    cours (load) ne doit pas faire repartir la sequence a zero, sinon un
    trou juste avant/apres un changement de video serait invisible."""
    received = []

    async def _fake_broadcast(payload):
        received.append(payload)

    async def _run():
        manager = PlaybackManager(_fake_broadcast, channel="network")
        await manager._emit("position_tick")
        await manager._emit("position_tick")
        await manager._emit("load")  # changement de cours, pas de tick_seq
        await manager._emit("position_tick")

    asyncio.run(_run())

    tick_seqs = [p["tick_seq"] for p in received if p["cause"] == "position_tick"]
    assert tick_seqs == [1, 2, 3]
