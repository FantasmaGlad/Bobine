import asyncio
import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.contract import RADIO_CHANNELS
from app.radio.channels import is_radio_channel, normalize_radio_channel
from app.radio.manager import RadioPlaybackManager, get_all_radio_managers, get_radio_manager
from app.utils.ws_manager import ConnectionManager

TRACKS = [
    {"id": 11, "title": "A", "duration_seconds": 30.0},
    {"id": 12, "title": "B", "duration_seconds": 40.0},
]


class FakeWS:
    def __init__(self):
        self.received = []

    async def send_json(self, message):
        self.received.append(message)

    async def close(self):
        pass


def _run(coro):
    return asyncio.run(coro)


def test_l_alias_historique_designe_la_sortie_reseau():
    assert normalize_radio_channel("radio") == "radio_network_2"
    assert normalize_radio_channel("radio_network_2") == "radio_network_2"
    assert normalize_radio_channel("radio_cable") == "radio_cable"


def test_une_valeur_absente_ou_inconnue_retombe_sur_la_sortie_reseau():
    assert normalize_radio_channel(None) == "radio_network_2"
    assert normalize_radio_channel("cable") == "radio_network_2"
    assert normalize_radio_channel("n'importe quoi") == "radio_network_2"


def test_is_radio_channel_accepte_les_sorties_radio_seulement():
    assert is_radio_channel("radio_cable")
    assert is_radio_channel("radio_network")
    assert is_radio_channel("radio_network_2")
    assert not is_radio_channel("radio")
    assert not is_radio_channel("cable")
    assert not is_radio_channel("network")
    assert not is_radio_channel(None)


def test_les_deux_moteurs_existent_et_sont_distincts():
    managers = get_all_radio_managers()
    assert set(managers) == set(RADIO_CHANNELS)
    assert managers["radio_cable"] is not managers["radio_network_2"]
    assert managers["radio_cable"].channel == "radio_cable"
    assert managers["radio_network_2"].channel == "radio_network_2"
    assert get_radio_manager() is managers["radio_network_2"]
    assert get_radio_manager("radio") is managers["radio_network_2"]
    assert get_radio_manager("radio_cable") is managers["radio_cable"]


def test_chaque_evenement_porte_la_sortie_de_son_moteur():
    async def _run_case():
        events = []

        async def _bc(payload):
            events.append(payload)

        cable = RadioPlaybackManager(_bc, "radio_cable")
        network = RadioPlaybackManager(_bc, "radio_network_2")
        await cable.load_playlist(1, "Salle", TRACKS, shuffle=False)
        await network.load_playlist(2, "Hall", TRACKS, shuffle=False)
        assert [e["channel"] for e in events] == ["radio_cable", "radio_network_2"]
        assert events[0]["data"]["playlist_name"] == "Salle"
        assert events[1]["data"]["playlist_name"] == "Hall"

    _run(_run_case())


def test_les_deux_moteurs_ont_un_etat_independant():
    async def _run_case():
        async def _bc(payload):
            pass

        cable = RadioPlaybackManager(_bc, "radio_cable")
        network = RadioPlaybackManager(_bc, "radio_network_2")
        await cable.load_playlist(1, "Salle", TRACKS, shuffle=False)
        await cable.set_volume(40)
        await network.load_playlist(2, "Hall", TRACKS, shuffle=False)
        await network.pause()
        assert cable.state["state"] == "playing"
        assert cable.state["volume"] == 40
        assert cable.state["playlist_id"] == 1
        assert network.state["state"] == "paused"
        assert network.state["volume"] != 40
        assert network.state["playlist_id"] == 2

    _run(_run_case())


def test_le_decompte_d_ecrans_pour_le_depart_synchronise_est_par_sortie():
    async def _run_case():
        async def _bc(payload):
            pass

        counts = {"radio_cable": 1, "radio_network_2": 2}
        cable = RadioPlaybackManager(_bc, "radio_cable")
        network = RadioPlaybackManager(_bc, "radio_network_2")
        cable.display_counter = lambda channel: counts[channel]
        network.display_counter = lambda channel: counts[channel]
        assert cable._lead_ms(150.0) == 0.0
        assert network._lead_ms(150.0) == 150.0

    _run(_run_case())


def test_abonnement_filtre_par_sortie_radio_et_ignore_l_ancien_alias():
    m = ConnectionManager()
    legacy, network_2, cable_only = FakeWS(), FakeWS(), FakeWS()
    m.active_connections.update({legacy: None, network_2: None, cable_only: None})
    m.subscribe(legacy, ["radio"])
    m.subscribe(network_2, ["radio_network_2"])
    m.subscribe(cable_only, ["radio_cable"])
    for channel in ("radio_network_2", "radio_cable"):
        _run(m.broadcast({"event": "state_change", "cause": "radio_position_tick", "channel": channel, "data": {}}))
    assert legacy.received == []
    assert [e["channel"] for e in network_2.received] == ["radio_network_2"]
    assert [e["channel"] for e in cable_only.received] == ["radio_cable"]


def test_le_role_primaire_est_distinct_par_sortie_radio():
    async def _run_case():
        m = ConnectionManager()
        ws_cable, ws_network, ws_mirror = FakeWS(), FakeWS(), FakeWS()
        assert await m.register_kiosk(ws_cable, "radio_cable", "page-cable") is True
        assert await m.register_kiosk(ws_network, "radio_network_2", "page-network") is True
        assert await m.register_kiosk(ws_mirror, "radio_network_2", "page-mirror") is False
        assert m.kiosk_count("radio_cable") == 1
        assert m.kiosk_count("radio_network_2") == 2
        assert m.kiosk_count("radio") == 0

    _run(_run_case())


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_etat_rest_de_la_radio_de_chaque_sortie(client):
    for output, radio in (("cable", "radio_cable"), ("network", "radio_network"), ("network_2", "radio_network_2")):
        assert client.get(f"/api/outputs/{output}").json()["radio"]["channel"] == radio
    assert [o["radio"]["channel"] for o in client.get("/api/outputs").json()] == ["radio_cable", "radio_network", "radio_network_2"]
    assert client.get("/api/outputs/zzz").status_code == 404


def test_websocket_synchronise_les_moteurs_radio(client):
    with client.websocket_connect("/ws/playback") as ws:
        sync = {}
        while not {"radio_cable", "radio_network_2"} <= set(sync):
            message = ws.receive_json()
            if message.get("event") == "state_change":
                sync[message["channel"]] = message
        assert {"radio_cable", "radio_network_2"} <= set(sync)
        assert "radio" not in sync
        ws.send_json({"command": "identify", "params": {"role": "kiosk", "channel": "radio_network_2", "client_id": "p-net2"}})
        message = ws.receive_json()
        while message.get("event") != "kiosk_role":
            message = ws.receive_json()
        assert message["is_primary"] is True


@pytest.mark.recent_stack
def test_commande_ciblee_sur_une_sortie_ne_touche_pas_l_autre(client):
    cable, network = get_radio_manager("radio_cable"), get_radio_manager("radio_network_2")
    cable.state["volume"], network.state["volume"] = 100, 100
    with client.websocket_connect("/ws/playback") as ws:
        ws.send_json({"command": "volume", "params": {"channel": "radio_cable", "volume": 33}})
        ws.send_json({"command": "volume", "params": {"channel": "radio_network_2", "volume": 55}})
        ws.send_json({"command": "pong", "params": {}})
    try:
        assert cable.state["volume"] == 33
        assert network.state["volume"] == 55
    finally:
        cable.state["volume"] = network.state["volume"] = 100
