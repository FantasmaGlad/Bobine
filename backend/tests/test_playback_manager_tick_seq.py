import asyncio

from app.playback.manager import PlaybackManager


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
    received = []

    async def _fake_broadcast(payload):
        received.append(payload)

    async def _run():
        manager = PlaybackManager(_fake_broadcast, channel="network")
        await manager._emit("position_tick")
        await manager._emit("position_tick")
        await manager._emit("load")
        await manager._emit("position_tick")

    asyncio.run(_run())

    tick_seqs = [p["tick_seq"] for p in received if p["cause"] == "position_tick"]
    assert tick_seqs == [1, 2, 3]
