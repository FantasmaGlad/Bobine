"""Réglages de son par sortie radio : bornage, persistance, diffusion avec l'état."""

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

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Setting  # noqa: E402
from app.radio_manager import RadioPlaybackManager, get_radio_manager  # noqa: E402
from app.utils.radio_sound import (  # noqa: E402
    default_sound,
    load_all_sounds_into_managers,
    load_sound,
    sanitize_sound,
    save_sound,
    sound_setting_key,
)

KEYS = ("radio_sound_radio_cable", "radio_sound_radio_network")


def _clean():
    db = SessionLocal()
    try:
        db.query(Setting).filter(Setting.key.in_(KEYS)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
    for channel in ("radio_cable", "radio_network"):
        get_radio_manager(channel).state["sound"] = default_sound()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        _clean()
        yield c
        _clean()


def test_reglages_neutres_par_defaut_et_copie_independante():
    sound = default_sound()
    assert sound == {"enabled": True, "bands": [0, 0, 0, 0, 0], "bass_boost": 0,
                     "loudness": False, "limiter": True, "preset": None}
    sound["bands"][0] = 9
    assert default_sound()["bands"][0] == 0


def test_les_gains_hors_plage_sont_bornes_sans_erreur():
    sound = sanitize_sound({"bands": [99, -99, 3.6, 0, 12], "bass_boost": 50})
    assert sound["bands"] == [12, -12, 4, 0, 12]
    assert sound["bass_boost"] == 12
    assert sanitize_sound({"bass_boost": -5})["bass_boost"] == 0


def test_les_valeurs_invalides_gardent_la_valeur_courante():
    base = {"enabled": False, "bands": [1, 2, 3, 4, 5], "bass_boost": 6, "loudness": True, "limiter": False,
            "preset": "voice"}
    out = sanitize_sound({"bands": ["x", None, True, float("nan"), 7], "bass_boost": "fort",
                          "loudness": "oui", "enabled": 1}, base=base)
    assert out["bands"] == [1, 2, 3, 4, 7]
    assert out["bass_boost"] == 6
    assert out["loudness"] is True and out["enabled"] is False and out["limiter"] is False
    assert out["preset"] == "voice"


def test_entree_non_dict_ou_bandes_de_mauvaise_longueur():
    assert sanitize_sound(None) == default_sound()
    assert sanitize_sound("n'importe quoi") == default_sound()
    short = sanitize_sound({"bands": [5, 5]})
    assert short["bands"] == [5, 5, 0, 0, 0]
    long = sanitize_sound({"bands": [1] * 20})
    assert long["bands"] == [1, 1, 1, 1, 1]


def test_preset_borne_et_nettoye():
    assert sanitize_sound({"preset": "  bass  "})["preset"] == "bass"
    assert sanitize_sound({"preset": ""})["preset"] is None
    assert sanitize_sound({"preset": None})["preset"] is None
    assert sanitize_sound({"preset": 12})["preset"] is None
    assert len(sanitize_sound({"preset": "x" * 500})["preset"]) == 40
    # Preset absent : la valeur courante est conservée.
    assert sanitize_sound({}, base={**default_sound(), "preset": "voice"})["preset"] == "voice"


def test_persistance_et_isolation_entre_sorties(client):
    db = SessionLocal()
    try:
        save_sound(db, "radio_cable", sanitize_sound({"bands": [3, 0, 0, 0, -2], "bass_boost": 4}))
        assert load_sound(db, "radio_cable")["bands"] == [3, 0, 0, 0, -2]
        assert load_sound(db, "radio_network") == default_sound()
        assert sound_setting_key("radio") == "radio_sound_radio_network"
        load_all_sounds_into_managers(db)
    finally:
        db.close()
    assert get_radio_manager("radio_cable").state["sound"]["bass_boost"] == 4
    assert get_radio_manager("radio_network").state["sound"] == default_sound()


def test_un_json_corrompu_ne_fait_jamais_d_erreur(client):
    db = SessionLocal()
    try:
        db.add(Setting(key="radio_sound_radio_cable", value="{pas du json"))
        db.commit()
        assert load_sound(db, "radio_cable") == default_sound()
        row = db.query(Setting).filter(Setting.key == "radio_sound_radio_cable").first()
        row.value = json.dumps([1, 2, 3])
        db.commit()
        assert load_sound(db, "radio_cable") == default_sound()
    finally:
        db.close()


def test_le_son_fait_partie_du_snapshot_et_set_sound_diffuse():
    async def _run():
        events = []

        async def _bc(payload):
            events.append(payload)

        manager = RadioPlaybackManager(_bc, "radio_cable")
        assert manager.snapshot()["sound"] == default_sound()
        sound = sanitize_sound({"bands": [1, 2, 3, 4, 5]})
        await manager.set_sound(sound, client_ts=42.0)
        assert events[-1]["cause"] == "radio_sound_change"
        assert events[-1]["channel"] == "radio_cable"
        assert events[-1]["data"]["sound"]["bands"] == [1, 2, 3, 4, 5]
        assert events[-1]["client_ts"] == 42.0

    asyncio.run(_run())


def test_rest_borne_persiste_et_cible_la_bonne_sortie(client):
    response = client.put("/api/radio/sound?channel=radio_cable", json={"bands": [99, 0, 0, 0, 0], "bass_boost": 3})
    assert response.status_code == 200
    assert response.json()["bands"][0] == 12
    assert client.get("/api/radio/sound?channel=radio_cable").json()["bass_boost"] == 3
    assert client.get("/api/radio/sound?channel=radio_network").json() == default_sound()
    assert client.get("/api/radio/sound").json() == default_sound()  # défaut = sortie réseau
    # Persisté en base.
    db = SessionLocal()
    try:
        assert load_sound(db, "radio_cable")["bass_boost"] == 3
    finally:
        db.close()
    # Une mise à jour partielle garde le reste.
    client.put("/api/radio/sound?channel=radio_cable", json={"loudness": True})
    state = client.get("/api/radio/sound?channel=radio_cable").json()
    assert state["loudness"] is True and state["bass_boost"] == 3


def test_commande_websocket_radio_set_sound_isolee_par_sortie(client):
    with client.websocket_connect("/ws/playback") as ws:
        ws.send_json({"command": "radio_set_sound", "params": {
            "channel": "radio_network", "sound": {"bands": [0, 0, 0, 0, 15], "limiter": False}}})
        ws.send_json({"command": "pong", "params": {}})
    network = get_radio_manager("radio_network").state["sound"]
    assert network["bands"][4] == 12 and network["limiter"] is False
    assert get_radio_manager("radio_cable").state["sound"] == default_sound()
    db = SessionLocal()
    try:
        assert load_sound(db, "radio_network")["bands"][4] == 12
    finally:
        db.close()


def test_l_etat_diffuse_en_websocket_contient_le_son(client):
    client.put("/api/radio/sound?channel=radio_cable", json={"bass_boost": 8})
    with client.websocket_connect("/ws/playback") as ws:
        seen = {}
        while not {"radio_cable", "radio_network"} <= set(seen):
            message = ws.receive_json()
            if message.get("event") == "state_change":
                seen[message["channel"]] = message["data"]
    assert seen["radio_cable"]["sound"]["bass_boost"] == 8
    assert seen["radio_network"]["sound"] == default_sound()


def test_le_demarrage_charge_les_reglages_persistes_dans_les_moteurs():
    _clean()
    db = SessionLocal()
    try:
        save_sound(db, "radio_cable", sanitize_sound({"bass_boost": 7, "preset": "bass"}))
    finally:
        db.close()
    try:
        # Un nouveau démarrage de l'application (lifespan) relit la base.
        get_radio_manager("radio_cable").state["sound"] = default_sound()
        with TestClient(app):
            assert get_radio_manager("radio_cable").state["sound"]["bass_boost"] == 7
            assert get_radio_manager("radio_network").state["sound"] == default_sound()
    finally:
        _clean()
