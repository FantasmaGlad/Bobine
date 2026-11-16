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
from app.radio_manager import get_radio_manager  # noqa: E402
from devices_routing_support import SPEAKER, JBL, HDMI, _route, _add_player  # noqa: E402


def test_reconciliation_publie_l_etat_et_suit_la_reconnexion(routing_env):
    fresh, driver = routing_env
    _route()
    asyncio.run(fresh.reconcile_routes())
    assert get_radio_manager("radio_cable").state["route"]["state"] == "routed"
    assert get_radio_manager("radio_network").state["route"] is None
    driver.sinks = [SPEAKER, HDMI]
    asyncio.run(fresh.reconcile_routes())
    assert get_radio_manager("radio_cable").state["route"]["state"] == "missing"
    driver.sinks = [SPEAKER, {**JBL, "id": "bluez_output.88_92_CC_9C_41_0E.a2dp-sink"}]
    asyncio.run(fresh.reconcile_routes())
    assert get_radio_manager("radio_cable").state["route"]["state"] == "routed"


def test_liste_des_sorties_indisponible_route_inconnue_sans_erreur(routing_env):
    fresh, driver = routing_env
    _route()

    async def boom():
        raise DeviceError("audio_unavailable", "PipeWire ne répond pas", 502)

    driver.audio_list = boom
    asyncio.run(fresh.reconcile_routes())
    assert get_radio_manager("radio_cable").state["route"]["state"] == "unknown"


def test_le_serveur_deplace_le_flux_d_un_lecteur_local_qui_joue(routing_env):
    fresh, driver = routing_env
    _route()
    _add_player("radio_cable", status="unsupported")
    get_radio_manager("radio_cable").state["playing"] = True
    asyncio.run(fresh.reconcile_routes())
    assert driver.routed == [JBL["id"]]
    assert fresh.server_status("radio_cable") == {"status": "moved", "app": "Chromium"}
    with SessionLocal() as db:
        save_routes(db, {})
    asyncio.run(fresh.reconcile_routes())
    assert driver.routed[-1] is None


def test_le_serveur_ne_touche_pas_a_ce_que_le_navigateur_a_applique(routing_env):
    fresh, driver = routing_env
    _route()
    _add_player("radio_cable", status="applied")
    get_radio_manager("radio_cable").state["playing"] = True
    asyncio.run(fresh.reconcile_routes())
    assert driver.routed == [] and fresh.server_status("radio_cable") == {"status": "browser"}


def test_lecteur_distant_ou_radio_a_l_arret_le_serveur_n_agit_pas(routing_env):
    fresh, driver = routing_env
    _route()
    _add_player("radio_cable", host="203.0.113.9", status="unsupported")
    get_radio_manager("radio_cable").state["playing"] = True
    asyncio.run(fresh.reconcile_routes())
    assert driver.routed == [] and fresh.server_status("radio_cable") is None
    _add_player("radio_cable", status="unsupported")
    get_radio_manager("radio_cable").state["playing"] = False
    asyncio.run(fresh.reconcile_routes())
    assert driver.routed == [] and fresh.server_status("radio_cable") == {"status": "waiting"}


def test_deux_sorties_qui_jouent_en_local_c_est_ambigu_rien_n_est_deplace(routing_env):
    fresh, driver = routing_env
    with SessionLocal() as db:
        save_routes(db, {"radio_cable": describe_sink(JBL), "radio_network": describe_sink(HDMI)})
    for channel in ("radio_cable", "radio_network"):
        _add_player(channel, status="insecure")
        get_radio_manager(channel).state["playing"] = True
    asyncio.run(fresh.reconcile_routes())
    assert driver.routed == []
    assert fresh.server_status("radio_cable") == {"status": "ambiguous"} and fresh.server_status("radio_network") == {"status": "ambiguous"}


def test_pilote_sans_capacite_le_statut_est_non_pris_en_charge(routing_env):
    fresh, driver = routing_env
    driver.route_cap = False
    _route()
    _add_player("radio_cable", status="unsupported")
    get_radio_manager("radio_cable").state["playing"] = True
    asyncio.run(fresh.reconcile_routes())
    assert driver.routed == [] and fresh.server_status("radio_cable")["status"] == "unsupported"


def test_une_panne_du_pilote_ne_leve_jamais_et_ne_touche_pas_a_la_lecture(routing_env):
    fresh, driver = routing_env
    _route()
    _add_player("radio_cable", status="unsupported")
    manager = get_radio_manager("radio_cable")
    manager.state["playing"] = True

    async def boom(sink_id):
        raise RuntimeError("D-Bus a planté")

    driver.audio_route_stream = boom
    asyncio.run(fresh.reconcile_routes())
    assert manager.state["playing"] is True
