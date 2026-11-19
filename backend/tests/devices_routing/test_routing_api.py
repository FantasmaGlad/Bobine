from fastapi.testclient import TestClient  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.devices.base import DeviceError, NullDriver  # noqa: E402
from app.devices.routing import (  # noqa: E402
    load_routes,
)
from app.devices.service import PLAYER_ROUTE_STATUSES  # noqa: E402
from app.main import app  # noqa: E402
from app.radio.manager import get_radio_manager  # noqa: E402
from devices_routing_support import JBL, _local, _players, _wait_for  # noqa: E402


def test_choix_effacement_et_repli_d_une_route(api, monkeypatch):
    fresh, driver = api
    _local(monkeypatch)
    client = TestClient(app)
    view = client.get("/api/devices/routing").json()
    assert view["supported"] is True and [o["channel"] for o in view["outputs"]] == ["radio_cable", "radio_network"]
    assert all(o["route"] is None and o["state"] == "default" for o in view["outputs"])
    assert view["server_mechanism"]["supported"] is True and view["fallbacks"] == ["default", "mute"]

    chosen = client.put("/api/devices/routing", json={"channel": "radio_cable", "sink_id": JBL["id"]})
    assert chosen.status_code == 200
    cable = chosen.json()["outputs"][0]
    assert cable["route"]["label"] == "JBL Live 770NC" and cable["route"]["fallback"] == "default" and cable["state"] == "routed" and cable["sink_id"] == JBL["id"]
    assert get_radio_manager("radio_cable").state["route"]["state"] == "routed"
    assert get_radio_manager("radio_network").state["route"] is None
    with SessionLocal() as db:
        assert load_routes(db)["radio_cable"]["key"] == "bt:88:92:CC:9C:41:0E"

    muted = client.put("/api/devices/routing", json={"channel": "radio_cable", "fallback": "mute"}).json()["outputs"][0]
    assert muted["route"]["fallback"] == "mute" and muted["route"]["sink_id"] == JBL["id"]
    assert get_radio_manager("radio_cable").state["route"]["fallback"] == "mute"

    cleared = client.put("/api/devices/routing", json={"channel": "radio_cable", "clear": True}).json()["outputs"][0]
    assert cleared["route"] is None and get_radio_manager("radio_cable").state["route"] is None


def test_alias_de_bobine_utilise_pour_l_affichage_de_la_route(api, monkeypatch):
    fresh, driver = api
    _local(monkeypatch)
    client = TestClient(app)
    assert client.put("/api/devices/audio/meta", json={"id": JBL["id"], "alias": "Enceinte du fond"}).status_code == 200
    route = client.put("/api/devices/routing", json={"channel": "radio_network", "sink_id": JBL["id"]}).json()["outputs"][1]["route"]
    assert route["label"] == "Enceinte du fond"
    assert "Enceinte du fond" not in get_radio_manager("radio_network").state["route"]["match"]


def test_erreurs_structurees_jamais_de_500(api, monkeypatch):
    fresh, driver = api
    _local(monkeypatch)
    client = TestClient(app)

    def code(response):
        return response.status_code, response.json()["detail"]["code"]

    assert code(client.put("/api/devices/routing", json={"channel": "cinema", "sink_id": "x"})) == (400, "bad_channel")
    assert code(client.put("/api/devices/routing", json={"channel": "radio", "sink_id": "x"})) == (400, "bad_channel")
    assert code(client.put("/api/devices/routing", json={"channel": "radio_cable", "sink_id": "x", "fallback": "boum"})) == (400, "bad_fallback")
    assert code(client.put("/api/devices/routing", json={"channel": "radio_cable", "sink_id": "disparue"})) == (404, "not_found")
    assert code(client.put("/api/devices/routing", json={"channel": "radio_cable", "fallback": "mute"})) == (400, "no_route")
    assert code(client.put("/api/devices/routing", json={"channel": "radio_cable"})) == (400, "bad_request")
    assert client.put("/api/devices/routing", json={}).status_code == 422

    async def boom():
        raise DeviceError("audio_unavailable", "PipeWire ne répond pas", 502)

    driver.audio_list = boom
    assert code(client.put("/api/devices/routing", json={"channel": "radio_cable", "sink_id": JBL["id"]})) == (501, "unsupported")
    view = client.get("/api/devices/routing")
    assert view.status_code == 200


def test_pilote_nul_vue_non_prise_en_charge(api, monkeypatch):
    fresh, _ = api
    fresh.set_driver(NullDriver("Pas ici."))
    _local(monkeypatch)
    client = TestClient(app)
    view = client.get("/api/devices/routing").json()
    assert view["supported"] is False and view["reason"] == "Pas ici." and view["server_mechanism"]["supported"] is False
    response = client.put("/api/devices/routing", json={"channel": "radio_cable", "sink_id": "x"})
    assert response.status_code == 501 and response.json()["detail"]["code"] == "unsupported"


def test_le_rapport_du_lecteur_est_memorise_borne_et_retire_a_la_deconnexion(api, monkeypatch):
    fresh, driver = api
    _local(monkeypatch)
    client = TestClient(app)
    from app.api.routes import playback as playback_router

    monkeypatch.setattr(playback_router.radio_commands, "devices_service", fresh)
    with client.websocket_connect("/ws/playback") as ws:
        ws.send_json({"command": "identify", "params": {"role": "kiosk", "channel": "radio_cable", "client_id": "t1", "page": "radio"}})
        while ws.receive_json()["event"] != "kiosk_role":
            pass
        ws.send_json({"command": "radio_report_route", "params": {"channel": "radio_cable", "status": "needs_labels"}})
        _wait_for(lambda: _players(client, "radio_cable") == ["needs_labels"])
        ws.send_json({"command": "radio_report_route", "params": {"channel": "radio_cable", "status": "n'importe quoi"}})
        _wait_for(lambda: _players(client, "radio_cable") == ["error"])
        assert "error" in PLAYER_ROUTE_STATUSES
    _wait_for(lambda: _players(client, "radio_cable") == [])


def test_un_client_non_identifie_ne_peut_pas_poser_de_rapport(api, monkeypatch):
    fresh, _ = api
    client = TestClient(app)
    with client.websocket_connect("/ws/playback") as ws:
        ws.send_json({"command": "radio_report_route", "params": {"channel": "radio_cable", "status": "applied"}})
        ws.send_json({"command": "pong"})
    from app.utils.ws_manager import manager as manager_ws

    assert not manager_ws._route_reports  # noqa: SLF001
