import asyncio

from app.radio.manager import RadioPlaybackManager

TRACKS = [{"id": i, "title": f"T{i}", "duration_seconds": 60.0} for i in range(1, 5)]


def _recorder():
    events = []

    async def broadcast(payload):
        events.append(payload)

    return events, RadioPlaybackManager(broadcast, "radio_cable")


def test_position_tick_omits_the_queue_already_sent():
    async def run():
        events, manager = _recorder()
        await manager.load_playlist(1, "P", TRACKS, shuffle=False)
        await manager._emit("radio_position_tick")
        await manager.set_volume(40)
        return events

    loaded, tick, volume = asyncio.run(run())
    assert [t["id"] for t in loaded["data"]["order"]] == [1, 2, 3, 4]
    assert "order" not in tick["data"]
    assert "order" not in volume["data"]
    assert tick["data"]["index"] == 0


def test_queue_change_and_reload_with_new_metadata_send_the_queue_again():
    async def run():
        events, manager = _recorder()
        await manager.load_playlist(1, "P", TRACKS, shuffle=False)
        await manager.move_in_order(3, 1)
        await manager._emit("radio_position_tick")
        renamed = [{**t, "title": "Nouveau"} if t["id"] == 2 else t for t in TRACKS]
        await manager.load_playlist(1, "P", renamed, shuffle=False)
        return events

    _, moved, tick, reloaded = asyncio.run(run())
    assert [t["id"] for t in moved["data"]["order"]] == [1, 4, 2, 3]
    assert "order" not in tick["data"]
    assert [t["title"] for t in reloaded["data"]["order"]] == ["T1", "Nouveau", "T3", "T4"]


def test_snapshot_always_carries_the_full_queue():
    async def run():
        _, manager = _recorder()
        await manager.load_playlist(1, "P", TRACKS, shuffle=False)
        await manager._emit("radio_position_tick")
        return manager.snapshot()

    assert len(asyncio.run(run())["order"]) == 4
