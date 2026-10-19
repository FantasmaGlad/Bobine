"""File « À suivre » : réordonnancement (glisser-déposer) limité aux pistes à venir,
commande WebSocket, style (genre) transmis avec chaque piste."""

import asyncio
import os

# Base de test isolée AVANT tout import de l'application (comme les autres tests).
os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.models import RadioTrack  # noqa: E402
from app.radio_manager import RadioPlaybackManager, get_radio_manager  # noqa: E402
from app.scheduler_manager import radio_track_dict  # noqa: E402

TRACKS = [{"id": i, "title": f"T{i}", "duration_seconds": 60.0} for i in range(1, 7)]


def _ids(manager):
    return [t["id"] for t in manager.state["order"]]


async def _loaded(events=None):
    async def _bc(payload):
        if events is not None:
            events.append(payload["cause"])

    manager = RadioPlaybackManager(_bc, "radio_cable")
    await manager.load_playlist(1, "P", TRACKS, shuffle=False)
    return manager


def test_deplacer_une_piste_a_venir_vers_le_haut_et_le_bas():
    async def _run():
        events = []
        m = await _loaded(events)  # piste courante = index 0 ; file = indices 1..5
        await m.move_in_order(4, 1, client_ts=1.0)
        assert _ids(m) == [1, 5, 2, 3, 4, 6]
        await m.move_in_order(1, 5)
        assert _ids(m) == [1, 2, 3, 4, 6, 5]
        assert events[-1] == "radio_queue_changed"
        assert m.state["current_track"]["id"] == 1

    asyncio.run(_run())


def test_la_piste_courante_et_l_historique_ne_bougent_jamais():
    async def _run():
        m = await _loaded()
        await m.next_track()
        await m.next_track()  # courante = index 2 (id 3) ; à venir = indices 3..5
        before = _ids(m)
        await m.move_in_order(2, 4)  # la piste courante : refusé
        await m.move_in_order(0, 4)  # l'historique : refusé
        await m.move_in_order(4, 2)  # vers la piste courante : refusé -> borné à la file
        assert _ids(m)[:3] == before[:3]
        assert m.state["current_track"]["id"] == 3
        await m.move_in_order(5, 0)  # destination hors file : bornée au début de la file
        assert _ids(m)[:3] == before[:3]
        assert _ids(m)[3] == before[5]

    asyncio.run(_run())


def test_les_indices_invalides_ou_identiques_n_emettent_rien():
    async def _run():
        events = []
        m = await _loaded(events)
        count = len(events)
        for args in ((3, 3), (-1, 2), (99, 1), (1, 1)):
            await m.move_in_order(*args)
        assert len(events) == count
        assert _ids(m) == [1, 2, 3, 4, 5, 6]
        idle = RadioPlaybackManager(lambda payload: asyncio.sleep(0), "radio_network")
        await idle.move_in_order(1, 2)  # file vide : sans effet, sans erreur
        assert idle.state["order"] == []

    asyncio.run(_run())


def test_destination_hors_file_bornee_a_la_fin():
    async def _run():
        m = await _loaded()
        await m.move_in_order(1, 99)
        assert _ids(m) == [1, 3, 4, 5, 6, 2]

    asyncio.run(_run())


def test_le_style_et_la_pochette_sont_transmis_avec_la_piste():
    track = RadioTrack(id=7, file_path="/tmp/x.mp3", title="Titre", artist="Art", album="Alb", genre="Rock",
                       duration_seconds=187.0, cover_path="/tmp/c.jpg", source="upload")
    d = radio_track_dict(track)
    assert d["genre"] == "Rock" and d["artist"] == "Art" and d["duration_seconds"] == 187.0
    assert d["cover_url"] == "/radio/tracks/7/cover"
    assert radio_track_dict(RadioTrack(id=8, file_path="/tmp/y.mp3", title="T", source="upload"))["cover_url"] is None


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_commande_websocket_radio_move_in_queue_cible_la_bonne_sortie(client):
    cable, network = get_radio_manager("radio_cable"), get_radio_manager("radio_network")

    async def _prepare():
        await cable.load_playlist(1, "P", TRACKS, shuffle=False)
        await network.load_playlist(2, "Q", TRACKS, shuffle=False)

    asyncio.run(_prepare())
    try:
        with client.websocket_connect("/ws/playback") as ws:
            ws.send_json({"command": "radio_move_in_queue",
                          "params": {"channel": "radio_cable", "from_index": 5, "to_index": 1}})
            ws.send_json({"command": "pong", "params": {}})
        assert _ids(cable) == [1, 6, 2, 3, 4, 5]
        assert _ids(network) == [1, 2, 3, 4, 5, 6]
    finally:
        asyncio.run(cable.stop())
        asyncio.run(network.stop())
