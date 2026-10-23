"""Phase 3 des périphériques : table de mixage applicative d'une sortie radio (bornage, persistance, diffusion, vumètre)."""

import asyncio
import json
import os

# Base de test isolée AVANT tout import de l'application (comme les autres tests).
os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402
from app.devices import security  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Setting  # noqa: E402
from app.radio_manager import METER_LEASE_SECONDS, RadioPlaybackManager, get_radio_manager  # noqa: E402
from app.utils.radio_mix import (  # noqa: E402
    GAIN_MAX_DB,
    GAIN_MIN_DB,
    default_mix,
    load_all_mixes_into_managers,
    load_mix,
    mix_setting_key,
    sanitize_levels,
    sanitize_mix,
    save_mix,
)
from app.utils.radio_sound import default_sound  # noqa: E402

KEYS = ("radio_mix_radio_cable", "radio_mix_radio_network", "radio_sound_radio_cable", "radio_sound_radio_network", security.SETTING_ENABLED)


def test_reglages_neutres_et_copie_independante():
    mix = default_mix()
    assert mix == {
        "master": {"gain_db": 0, "muted": False},
        "music": {"gain_db": 0, "muted": False, "solo": False},
        "announcements": {"gain_db": 0, "muted": False, "solo": False, "sound": default_sound()},
    }
    mix["announcements"]["sound"]["bands"][0] = 9
    mix["music"]["gain_db"] = 5
    assert default_mix()["announcements"]["sound"]["bands"][0] == 0 and default_mix()["music"]["gain_db"] == 0


def test_gains_hors_plage_bornes_sans_erreur_et_arrondi_comme_javascript():
    mix = sanitize_mix({"master": {"gain_db": 99}, "music": {"gain_db": -99}, "announcements": {"gain_db": 2.5}})
    assert mix["master"]["gain_db"] == GAIN_MAX_DB and mix["music"]["gain_db"] == GAIN_MIN_DB
    assert mix["announcements"]["gain_db"] == 3  # Math.round(2.5) = 3 (et non 2, arrondi pair de Python)
    assert sanitize_mix({"music": {"gain_db": -2.5}})["music"]["gain_db"] == -2  # Math.round(-2.5) = -2


def test_valeurs_de_mauvais_type_gardent_la_valeur_courante():
    current = sanitize_mix({"music": {"gain_db": -6, "muted": True, "solo": True}, "master": {"gain_db": -3}})
    mix = sanitize_mix({"music": {"gain_db": "fort", "muted": "oui", "solo": 1}, "master": None, "announcements": [1, 2]}, base=current)
    assert mix["music"] == {"gain_db": -6, "muted": True, "solo": True}
    assert mix["master"]["gain_db"] == -3
    assert mix["announcements"] == default_mix()["announcements"]
    for junk in (None, "x", 42, [], {"music": 3}, {"music": {"gain_db": float("nan")}}):
        assert sanitize_mix(junk) == default_mix()
    assert sanitize_mix({"music": {"gain_db": True}})["music"]["gain_db"] == 0  # bool n'est pas un gain


def test_champs_absents_gardent_la_base_et_l_egaliseur_des_rappels_est_borne():
    base = sanitize_mix({"announcements": {"sound": {"bands": [3, 0, 0, 0, 0], "preset": "voice"}, "gain_db": -4}})
    updated = sanitize_mix({"announcements": {"muted": True}}, base=base)
    assert updated["announcements"]["gain_db"] == -4 and updated["announcements"]["muted"] is True
    assert updated["announcements"]["sound"]["bands"] == [3, 0, 0, 0, 0] and updated["announcements"]["sound"]["preset"] == "voice"
    loud = sanitize_mix({"announcements": {"sound": {"bands": [99, -99, 0, 0, 0], "bass_boost": 99}}})["announcements"]["sound"]
    assert loud["bands"][:2] == [12, -12] and loud["bass_boost"] == 12


def test_cle_de_persistance_par_sortie_et_alias_historique():
    assert mix_setting_key("radio_cable") == "radio_mix_radio_cable"
    assert mix_setting_key("radio") == "radio_mix_radio_network"
    assert mix_setting_key("n'importe quoi") == "radio_mix_radio_network"


def test_niveaux_du_vumetre_bornes_et_limites_aux_tranches_connues():
    assert sanitize_levels({"music": 150, "announcements": -3, "master": 41.6, "autre": 10}) == {"music": 100, "announcements": 0, "master": 42}
    assert sanitize_levels({"music": "fort", "master": float("nan"), "announcements": True}) == {}
    assert sanitize_levels(None) == {} and sanitize_levels([1]) == {}


def _clean():
    init_db()
    with SessionLocal() as db:
        db.query(Setting).filter(Setting.key.in_(KEYS)).delete(synchronize_session=False)
        db.commit()
    for channel in ("radio_cable", "radio_network"):
        state = get_radio_manager(channel).state
        state["mix"], state["sound"], state["meter"] = default_mix(), default_sound(), False


def test_persistance_aller_retour_et_json_corrompu():
    _clean()
    with SessionLocal() as db:
        assert load_mix(db, "radio_cable") == default_mix()
        save_mix(db, "radio_cable", {"music": {"gain_db": -6, "solo": True}})
        assert load_mix(db, "radio_cable")["music"] == {"gain_db": -6, "muted": False, "solo": True}
        assert load_mix(db, "radio_network") == default_mix()  # une sortie ne touche pas l'autre
        db.query(Setting).filter(Setting.key == mix_setting_key("radio_cable")).first().value = "{pas du json"
        db.commit()
        assert load_mix(db, "radio_cable") == default_mix()
        save_mix(db, "radio_network", {"master": {"muted": True}})
        load_all_mixes_into_managers(db)
    assert get_radio_manager("radio_network").state["mix"]["master"]["muted"] is True
    assert get_radio_manager("radio_cable").state["mix"] == default_mix()
    _clean()


@pytest.fixture()
def api(monkeypatch):
    _clean()
    monkeypatch.setattr("app.routers.devices.is_local_request", lambda request: True)
    with SessionLocal() as db:
        db.add(Setting(key=security.SETTING_ENABLED, value="true"))
        db.commit()
    yield TestClient(app)
    _clean()


def test_api_ecriture_bornee_persistee_et_publiee_dans_l_etat(api):
    initial = api.get("/api/devices/mixer").json()
    assert [o["channel"] for o in initial["outputs"]] == ["radio_cable", "radio_network"]
    assert initial["outputs"][0]["mix"] == default_mix() and initial["outputs"][0]["sound"] == default_sound()

    response = api.put("/api/devices/mixer/radio_cable", json={"mix": {"music": {"gain_db": -200, "solo": True}, "announcements": {"muted": True}}})
    assert response.status_code == 200
    cable = response.json()["outputs"][0]
    assert cable["mix"]["music"] == {"gain_db": GAIN_MIN_DB, "muted": False, "solo": True} and cable["mix"]["announcements"]["muted"] is True
    assert get_radio_manager("radio_cable").state["mix"]["music"]["solo"] is True  # publié au lecteur
    assert get_radio_manager("radio_network").state["mix"] == default_mix()
    with SessionLocal() as db:
        assert load_mix(db, "radio_cable")["music"]["solo"] is True

    # Un second envoi partiel conserve le reste.
    api.put("/api/devices/mixer/radio_cable", json={"mix": {"master": {"gain_db": -3}}})
    assert get_radio_manager("radio_cable").state["mix"]["music"]["solo"] is True
    assert get_radio_manager("radio_cable").state["mix"]["master"]["gain_db"] == -3


def test_api_egaliseur_de_la_musique_meme_chemin_que_le_son_radio(api):
    response = api.put("/api/devices/mixer/radio_network", json={"sound": {"bands": [4, 0, 0, 0, -2], "bass_boost": 50}})
    assert response.status_code == 200
    sound = get_radio_manager("radio_network").state["sound"]
    assert sound["bands"] == [4, 0, 0, 0, -2] and sound["bass_boost"] == 12
    assert api.get("/api/radio/sound", params={"channel": "radio_network"}).json()["bands"][0] == 4  # même valeur côté radio


def test_api_erreurs_structurees(api):
    assert api.put("/api/devices/mixer/cinema", json={"mix": {}}).json()["detail"]["code"] == "not_found"
    assert api.put("/api/devices/mixer/radio_cable", json={}).status_code == 200  # rien à changer
    assert api.put("/api/devices/mixer/radio_cable", json={"mix": "pas un objet"}).status_code == 422


# ---------------------------------------------------------------------------
# Vumètre : bail, expiration, relais
# ---------------------------------------------------------------------------


def _manager():
    sent: list[dict] = []

    async def broadcast(message):
        sent.append(message)

    return RadioPlaybackManager(broadcast, "radio_cable"), sent


def test_le_vumetre_demande_s_active_une_fois_puis_expire_sans_renouvellement(monkeypatch):
    manager, sent = _manager()
    clock = [1000.0]
    monkeypatch.setattr("app.radio_manager.time.monotonic", lambda: clock[0])

    async def scenario():
        assert manager.state["meter"] is False
        await manager.request_meter()
        await manager.request_meter()  # renouvellement : pas de nouvel état diffusé
        assert manager.state["meter"] is True
        assert [m["cause"] for m in sent if m["event"] == "state_change"] == ["radio_meter"]
        clock[0] += METER_LEASE_SECONDS - 1
        await manager._expire_meter()  # noqa: SLF001
        assert manager.state["meter"] is True
        await manager.request_meter()  # l'interface renouvelle
        clock[0] += METER_LEASE_SECONDS - 1
        await manager._expire_meter()  # noqa: SLF001
        assert manager.state["meter"] is True
        clock[0] += 2
        await manager._expire_meter()  # noqa: SLF001
        assert manager.state["meter"] is False
        assert [m["cause"] for m in sent if m["event"] == "state_change"] == ["radio_meter", "radio_meter"]

    asyncio.run(scenario())


def test_les_niveaux_ne_sont_relayes_que_pendant_un_bail_et_portent_la_sortie():
    manager, sent = _manager()

    async def scenario():
        await manager.relay_levels({"music": 40})
        assert not [m for m in sent if m["event"] == "radio_levels"]
        await manager.request_meter()
        await manager.relay_levels({"music": 40, "master": 35})
        await manager.relay_levels({})
        levels = [m for m in sent if m["event"] == "radio_levels"]
        assert levels == [{"event": "radio_levels", "channel": "radio_cable", "levels": {"music": 40, "master": 35}}]

    asyncio.run(scenario())


def test_set_route_ne_diffuse_que_si_la_route_change():
    manager, sent = _manager()

    async def scenario():
        await manager.set_route(None)
        assert sent == []
        route = {"key": "k", "label": "L", "match": ["L"], "kind": "usb", "fallback": "default", "state": "routed"}
        await manager.set_route(route)
        await manager.set_route(dict(route))
        assert [m["cause"] for m in sent] == ["radio_route_change"]
        assert sent[0]["data"]["route"] == route

    asyncio.run(scenario())


def test_le_flux_d_evenement_niveaux_est_propre_a_la_sortie():
    from app.utils.ws_manager import CHANNEL_SCOPED_EVENTS, ConnectionManager

    assert "radio_levels" in CHANNEL_SCOPED_EVENTS

    class WS:
        def __init__(self):
            self.received = []

        async def send_json(self, message):
            self.received.append(message)

    async def scenario():
        m = ConnectionManager()
        cable, network = WS(), WS()
        m.active_connections.update({cable: None, network: None})
        m.subscribe(cable, ["radio_cable"])
        m.subscribe(network, ["radio_network"])
        await m.broadcast({"event": "radio_levels", "channel": "radio_cable", "levels": {"music": 10}})
        assert len(cable.received) == 1 and network.received == []

    asyncio.run(scenario())


def test_commandes_websocket_du_vumetre(monkeypatch):
    _clean()
    client = TestClient(app)
    cable = get_radio_manager("radio_cable")
    with client.websocket_connect("/ws/playback") as ws:
        ws.send_json({"command": "identify", "params": {"role": "kiosk", "channel": "radio_cable", "client_id": "p1", "page": "radio"}})
        while ws.receive_json()["event"] != "kiosk_role":
            pass
        ws.send_json({"command": "radio_report_levels", "params": {"channel": "radio_cable", "levels": {"music": 50}}})  # sans bail : ignoré
        ws.send_json({"command": "radio_meter", "params": {"channel": "radio_cable"}})
        events = []
        while not any(e["event"] == "state_change" and e["cause"] == "radio_meter" for e in events):
            events.append(ws.receive_json())
        assert cable.state["meter"] is True
        ws.send_json({"command": "radio_report_levels", "params": {"channel": "radio_cable", "levels": {"music": 50, "x": 3}}})
        got = None
        for _ in range(20):
            message = ws.receive_json()
            if message["event"] == "radio_levels":
                got = message
                break
        assert got == {"event": "radio_levels", "channel": "radio_cable", "levels": {"music": 50}}
    cable.state["meter"] = False
    _clean()
