"""Deux moteurs radio indépendants (sortie câblée et sortie réseau), alias
historique `radio` ramené à la sortie réseau, diffusion et rôle primaire par sortie."""

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
from app.radio_manager import (  # noqa: E402
    RADIO_CHANNELS,
    RadioPlaybackManager,
    get_all_radio_managers,
    get_radio_manager,
    is_radio_channel,
    normalize_radio_channel,
)
from app.utils.ws_manager import ConnectionManager  # noqa: E402

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
    assert normalize_radio_channel("radio") == "radio_network"
    assert normalize_radio_channel("radio_network") == "radio_network"
    assert normalize_radio_channel("radio_cable") == "radio_cable"


def test_une_valeur_absente_ou_inconnue_retombe_sur_la_sortie_reseau():
    assert normalize_radio_channel(None) == "radio_network"
    assert normalize_radio_channel("cable") == "radio_network"
    assert normalize_radio_channel("n'importe quoi") == "radio_network"


def test_is_radio_channel_accepte_les_sorties_et_l_alias_seulement():
    assert is_radio_channel("radio")
    assert is_radio_channel("radio_cable")
    assert is_radio_channel("radio_network")
    assert not is_radio_channel("cable")
    assert not is_radio_channel("network")
    assert not is_radio_channel(None)


def test_les_deux_moteurs_existent_et_sont_distincts():
    managers = get_all_radio_managers()
    assert set(managers) == set(RADIO_CHANNELS)
    assert managers["radio_cable"] is not managers["radio_network"]
    assert managers["radio_cable"].channel == "radio_cable"
    assert managers["radio_network"].channel == "radio_network"
    assert get_radio_manager() is managers["radio_network"]
    assert get_radio_manager("radio") is managers["radio_network"]
    assert get_radio_manager("radio_cable") is managers["radio_cable"]


def test_chaque_evenement_porte_la_sortie_de_son_moteur():
    async def _run_case():
        events = []

        async def _bc(payload):
            events.append(payload)

        cable = RadioPlaybackManager(_bc, "radio_cable")
        network = RadioPlaybackManager(_bc, "radio_network")
        await cable.load_playlist(1, "Salle", TRACKS, shuffle=False)
        await network.load_playlist(2, "Hall", TRACKS, shuffle=False)
        assert [e["channel"] for e in events] == ["radio_cable", "radio_network"]
        assert events[0]["data"]["playlist_name"] == "Salle"
        assert events[1]["data"]["playlist_name"] == "Hall"

    _run(_run_case())


def test_les_deux_moteurs_ont_un_etat_independant():
    async def _run_case():
        async def _bc(payload):
            pass

        cable = RadioPlaybackManager(_bc, "radio_cable")
        network = RadioPlaybackManager(_bc, "radio_network")
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

        counts = {"radio_cable": 1, "radio_network": 2}
        cable = RadioPlaybackManager(_bc, "radio_cable")
        network = RadioPlaybackManager(_bc, "radio_network")
        cable.display_counter = lambda channel: counts[channel]
        network.display_counter = lambda channel: counts[channel]
        assert cable._lead_ms(150.0) == 0.0
        assert network._lead_ms(150.0) == 150.0

    _run(_run_case())


def test_abonnement_a_l_alias_recoit_la_sortie_reseau_et_pas_la_sortie_cable():
    m = ConnectionManager()
    legacy, cable_only = FakeWS(), FakeWS()
    m.active_connections.update({legacy: None, cable_only: None})
    m.subscribe(legacy, ["radio"])
    m.subscribe(cable_only, ["radio_cable"])
    for channel in ("radio_network", "radio_cable"):
        _run(m.broadcast({"event": "state_change", "cause": "radio_position_tick", "channel": channel, "data": {}}))
    assert [e["channel"] for e in legacy.received] == ["radio_network"]
    assert [e["channel"] for e in cable_only.received] == ["radio_cable"]


def test_le_role_primaire_est_distinct_par_sortie_radio():
    async def _run_case():
        m = ConnectionManager()
        ws_cable, ws_network, ws_legacy = FakeWS(), FakeWS(), FakeWS()
        assert await m.register_kiosk(ws_cable, "radio_cable", "page-cable") is True
        assert await m.register_kiosk(ws_network, "radio_network", "page-network") is True
        # Le poste qui s'identifie avec l'ancien identifiant rejoint la sortie réseau
        # (déjà occupée par un primaire) : il est miroir.
        assert await m.register_kiosk(ws_legacy, "radio", "page-legacy") is False
        assert m.kiosk_count("radio_cable") == 1
        assert m.kiosk_count("radio_network") == 2
        assert m.kiosk_count("radio") == 2

    _run(_run_case())


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_etat_rest_par_sortie_avec_defaut_et_alias(client):
    assert client.get("/api/radio/state").json()["channel"] == "radio_network"
    assert client.get("/api/radio/state?channel=radio").json()["channel"] == "radio_network"
    assert client.get("/api/radio/state?channel=radio_network").json()["channel"] == "radio_network"
    assert client.get("/api/radio/state?channel=radio_cable").json()["channel"] == "radio_cable"
    # Une valeur inconnue ne fait jamais une erreur serveur.
    assert client.get("/api/radio/state?channel=zzz").json()["channel"] == "radio_network"


def test_websocket_synchronise_les_deux_moteurs_et_accepte_l_alias(client):
    with client.websocket_connect("/ws/playback") as ws:
        sync = {}
        # boot_id, puis un état par canal de diffusion et par sortie radio.
        while not {"radio_cable", "radio_network"} <= set(sync):
            message = ws.receive_json()
            if message.get("event") == "state_change":
                sync[message["channel"]] = message
        assert {"radio_cable", "radio_network"} <= set(sync)
        assert "radio" not in sync
        # Un ancien poste s'identifie encore avec "radio" : il devient primaire
        # de la sortie réseau.
        ws.send_json({"command": "identify", "params": {"role": "kiosk", "channel": "radio", "client_id": "p-legacy"}})
        message = ws.receive_json()
        while message.get("event") != "kiosk_role":
            message = ws.receive_json()
        assert message["is_primary"] is True


def test_commande_ciblee_sur_une_sortie_ne_touche_pas_l_autre(client):
    cable, network = get_radio_manager("radio_cable"), get_radio_manager("radio_network")
    cable.state["volume"], network.state["volume"] = 100, 100
    with client.websocket_connect("/ws/playback") as ws:
        ws.send_json({"command": "volume", "params": {"channel": "radio_cable", "volume": 33}})
        ws.send_json({"command": "volume", "params": {"channel": "radio", "volume": 55}})
        # Le ping suivant garantit que les deux commandes ont été traitées (ordre WS).
        ws.send_json({"command": "pong", "params": {}})
    assert cable.state["volume"] == 33
    assert network.state["volume"] == 55
