import asyncio
import json
import os
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.devices.base import CAPABILITY_KEYS, DeviceDriver, DeviceError, NullDriver  # noqa: E402
from app.devices.linux.driver import LinuxDriver  # noqa: E402
from app.devices.linux.parse.audio import choose_browser_stream, parse_output_streams  # noqa: E402
from app.devices.routing import (  # noqa: E402
    ROUTES_SETTING,
    describe_sink,
    load_routes,
    load_routes_into_managers,
    normalize_label,
    player_route_state,
    resolve_route,
    sanitize_routes,
    save_routes,
    stable_sink_key,
)
from app.devices.service import PLAYER_ROUTE_STATUSES, DevicesService, service  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Setting  # noqa: E402
from app.radio.manager import get_radio_manager  # noqa: E402
from devices_routing_support import SPEAKER, JBL, HDMI  # noqa: E402


def test_cle_stable_bluetooth_independante_du_profil_et_du_suffixe():
    assert stable_sink_key("bluez_output.88_92_CC_9C_41_0E.1") == "bt:88:92:CC:9C:41:0E"
    assert stable_sink_key("bluez_output.88_92_cc_9c_41_0e.a2dp-sink") == "bt:88:92:CC:9C:41:0E"
    assert stable_sink_key("bluez_sink.88_92_CC_9C_41_0E.a2dp_sink") == "bt:88:92:CC:9C:41:0E"
    assert stable_sink_key("alsa_output.pci-0000_03_00.6.analog-stereo") == "node:alsa_output.pci-0000_03_00.6.analog-stereo"
    assert stable_sink_key("bluez_output.88_92") == "node:bluez_output.88_92"


def test_normalisation_des_libelles_ignore_casse_accents_et_ponctuation():
    assert normalize_label("Écran  HDMI (Realtek)") == "ecran hdmi realtek"
    assert normalize_label("") == "" and normalize_label(None) == ""


def test_descripteur_deduplique_les_libelles_et_prefere_l_alias_pour_l_affichage():
    desc = describe_sink({**SPEAKER, "name": "Realtek", "description": "REALTEK", "alias": "Salle 1"})
    assert desc["labels"] == ["Realtek"]
    assert desc["label"] == "Salle 1" and desc["key"] == "node:alsa_output.speaker" and desc["kind"] == "internal"
    assert describe_sink({"id": "x", "kind": "inconnu"})["kind"] == "other"


def test_routes_illisibles_ou_inconnues_sont_ecartees_sans_exception():
    assert sanitize_routes(None) == {} and sanitize_routes("n'importe quoi") == {} and sanitize_routes([]) == {}
    good = describe_sink(JBL) | {"fallback": "mute"}
    clean = sanitize_routes({"radio_cable": good, "radio_inconnue": good, "radio_network": {"sink_id": "", "key": "k"}})
    assert list(clean) == ["radio_cable"] and clean["radio_cable"]["fallback"] == "mute"
    assert sanitize_routes({"radio_cable": {**good, "fallback": "explose", "kind": "??", "labels": "pas une liste"}})["radio_cable"]["fallback"] == "default"
    long = sanitize_routes({"radio_cable": {**good, "label": "x" * 999, "labels": ["a"] * 20}})["radio_cable"]
    assert len(long["label"]) == 120 and len(long["labels"]) == 4


def test_resolution_presente_absente_inconnue_et_reconnexion_bluetooth():
    route = describe_sink(JBL)
    assert resolve_route(None, [SPEAKER])["state"] == "default"
    assert resolve_route(route, None)["state"] == "unknown"
    assert resolve_route(route, [SPEAKER, HDMI])["state"] == "missing"
    assert resolve_route(route, [SPEAKER, {**JBL, "available": False}])["state"] == "missing"
    reconnected = {**JBL, "id": "bluez_output.88_92_CC_9C_41_0E.a2dp-sink"}
    resolved = resolve_route(route, [SPEAKER, reconnected])
    assert resolved["state"] == "routed" and resolved["sink"]["id"] == reconnected["id"]


def test_etat_publie_aux_lecteurs_sans_identifiant_de_noeud():
    route = describe_sink(JBL) | {"fallback": "mute"}
    state = player_route_state(route, resolve_route(route, [SPEAKER, JBL]))
    assert state == {"key": "bt:88:92:CC:9C:41:0E", "label": "JBL Live 770NC", "match": ["JBL Live 770NC", "JBL Live"], "kind": "bluetooth", "fallback": "mute", "state": "routed"}
    assert "sink_id" not in state and "88_92" not in json.dumps(state)
    assert player_route_state(None, resolve_route(None, [SPEAKER])) is None
    missing = player_route_state(route, resolve_route(route, [SPEAKER]))
    assert missing["state"] == "missing" and missing["match"]


def test_persistance_aller_retour_et_valeur_corrompue():
    init_db()
    with SessionLocal() as db:
        db.query(Setting).filter(Setting.key == ROUTES_SETTING).delete()
        db.commit()
        assert load_routes(db) == {}
        save_routes(db, {"radio_cable": describe_sink(JBL)})
        assert load_routes(db)["radio_cable"]["key"] == "bt:88:92:CC:9C:41:0E"
        save_routes(db, {})
        assert db.query(Setting).filter(Setting.key == ROUTES_SETTING).first() is None
        db.add(Setting(key=ROUTES_SETTING, value="{pas du json"))
        db.commit()
        assert load_routes(db) == {}
        db.query(Setting).filter(Setting.key == ROUTES_SETTING).delete()
        db.commit()


def test_chargement_au_demarrage_publie_la_route_en_etat_inconnu():
    init_db()
    manager = get_radio_manager("radio_cable")
    with SessionLocal() as db:
        db.query(Setting).filter(Setting.key == ROUTES_SETTING).delete()
        db.commit()
        save_routes(db, {"radio_cable": describe_sink(JBL)})
        load_routes_into_managers(db)
        assert manager.state["route"]["state"] == "unknown" and manager.state["route"]["label"] == "JBL Live 770NC"
        assert get_radio_manager("radio_network").state["route"] is None
        save_routes(db, {})
        load_routes_into_managers(db)
    assert manager.state["route"] is None
