"""Phase 2 des périphériques : routage audio par sortie radio.

Aucun matériel ni PipeWire réel : pilote factice pour le routeur et le service, exécuteur de commandes simulé pour le
déplacement de flux Linux (le test sur de vrais flux PipeWire est un script à part, hors de la suite)."""

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
from app.devices.base import CAPABILITY_KEYS, DeviceDriver, DeviceError, NullDriver  # noqa: E402
from app.devices.linux import LinuxDriver  # noqa: E402
from app.devices.linux_parse import choose_browser_stream, parse_output_streams  # noqa: E402
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

KEYS = (security.SETTING_ENABLED, security.SETTING_PIN_HASH, ROUTES_SETTING, "devices_audio_meta")

SPEAKER = {"id": "alsa_output.speaker", "name": "Haut-parleurs", "description": "Ryzen HD Audio", "kind": "internal", "is_default": True, "available": True}
JBL = {"id": "bluez_output.88_92_CC_9C_41_0E.1", "name": "JBL Live 770NC", "description": "JBL Live", "kind": "bluetooth", "is_default": False, "available": True}
HDMI = {"id": "alsa_output.hdmi", "name": "HDMI / DP", "description": "Écran HDMI", "kind": "hdmi", "is_default": False, "available": True}


# ---------------------------------------------------------------------------
# Descripteurs, résolution, état publié
# ---------------------------------------------------------------------------


def test_cle_stable_bluetooth_independante_du_profil_et_du_suffixe():
    assert stable_sink_key("bluez_output.88_92_CC_9C_41_0E.1") == "bt:88:92:CC:9C:41:0E"
    assert stable_sink_key("bluez_output.88_92_cc_9c_41_0e.a2dp-sink") == "bt:88:92:CC:9C:41:0E"
    assert stable_sink_key("bluez_sink.88_92_CC_9C_41_0E.a2dp_sink") == "bt:88:92:CC:9C:41:0E"
    assert stable_sink_key("alsa_output.pci-0000_03_00.6.analog-stereo") == "node:alsa_output.pci-0000_03_00.6.analog-stereo"
    assert stable_sink_key("bluez_output.88_92") == "node:bluez_output.88_92"  # pas une MAC complète


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
    # Le haut-parleur revient avec un autre nom de nœud (autre profil) : même MAC, la route se rétablit.
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
    assert missing["state"] == "missing" and missing["match"]  # les libellés mémorisés restent disponibles


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


# ---------------------------------------------------------------------------
# Flux PipeWire et déplacement (Linux)
# ---------------------------------------------------------------------------


def _stream(node_id, binary, app_name, state="running"):
    return {"id": node_id, "type": "PipeWire:Interface:Node", "info": {"state": state, "props": {
        "media.class": "Stream/Output/Audio", "node.name": f"{binary}-{node_id}", "application.name": app_name, "application.process.binary": binary}}}


def _sink(node_id, name):
    return {"id": node_id, "type": "PipeWire:Interface:Node", "info": {"props": {"media.class": "Audio/Sink", "node.name": name, "node.description": name}}}


def _link(out_id, in_id):
    return {"id": 900 + out_id, "type": "PipeWire:Interface:Link", "info": {"props": {"link.output.node": out_id, "link.input.node": in_id}}}


def test_analyse_des_flux_reconnait_navigateurs_etat_et_sortie_liee():
    dump = [_sink(10, "alsa_output.speaker"), _sink(11, "bluez_output.x"), _stream(70, "chromium", "Chromium"), _stream(71, "mpv", "mpv"),
            _stream(72, "firefox", "Firefox", state="idle"), _link(70, 10), _link(71, 11)]
    streams = {s["id"]: s for s in parse_output_streams(dump)}
    assert streams[70]["browser"] and streams[70]["sink"] == "alsa_output.speaker" and streams[70]["state"] == "running"
    assert not streams[71]["browser"] and streams[71]["sink"] == "bluez_output.x"
    assert streams[72]["browser"] and streams[72]["sink"] is None


def test_choix_du_flux_jamais_de_devinette():
    mpv = parse_output_streams([_stream(1, "mpv", "mpv")])
    assert choose_browser_stream(mpv) == ("none", None)
    one = parse_output_streams([_stream(1, "chromium", "Chromium"), _stream(2, "chromium", "Chromium", state="idle")])
    verdict, stream = choose_browser_stream(one)
    assert verdict == "one" and stream["id"] == 1
    two = parse_output_streams([_stream(1, "chromium", "Chromium"), _stream(2, "firefox", "Firefox")])
    assert choose_browser_stream(two) == ("ambiguous", None)


class FakePipeWire:
    """Simule `pw-dump` et `pw-metadata` : un flux de navigateur qui suit `target.object` quand on le lui donne."""

    def __init__(self, streams, follow=True):
        self.streams = streams  # id -> {"binary", "app", "state", "sink"}
        self.follow = follow
        self.calls: list[tuple] = []
        self.default = "alsa_output.speaker"

    def dump(self):
        data = [_sink(10, "alsa_output.speaker"), _sink(11, "bluez_output.88_92_CC_9C_41_0E.1"), _sink(12, "alsa_output.hdmi")]
        ids = {"alsa_output.speaker": 10, "bluez_output.88_92_CC_9C_41_0E.1": 11, "alsa_output.hdmi": 12}
        for sid, s in self.streams.items():
            data.append(_stream(sid, s["binary"], s["app"], s["state"]))
            data.append(_link(sid, ids[s["sink"] or self.default]))
        return data

    async def __call__(self, *args, timeout=10.0, stdin=None):
        self.calls.append(args)
        if args[0] == "pw-dump":
            return 0, json.dumps(self.dump()), ""
        if args[0] == "wpctl":
            return 0, "Volume: 0.40", ""
        if args[0] == "pw-metadata":
            if "-d" in args:
                self.streams[int(args[args.index("-d") + 1])]["sink"] = None
            elif self.follow:
                self.streams[int(args[3])]["sink"] = args[5]
            return 0, "", ""
        return 1, "", "commande inconnue"


@pytest.fixture()
def pw_tools(monkeypatch):
    monkeypatch.setattr("app.devices.linux.shutil.which", lambda name: f"/usr/bin/{name}")


def _driver(streams, follow=True):
    pw = FakePipeWire(streams, follow)
    driver = LinuxDriver(runner=pw)
    return driver, pw


def test_deplacement_verifie_du_flux_unique(pw_tools, monkeypatch):
    monkeypatch.setattr("app.devices.linux.asyncio.sleep", _no_sleep)
    driver, pw = _driver({70: {"binary": "chromium", "app": "Chromium", "state": "running", "sink": None}})
    result = asyncio.run(driver.audio_route_stream("bluez_output.88_92_CC_9C_41_0E.1"))
    assert result["status"] == "moved" and result["app"] == "Chromium"
    assert ("pw-metadata", "-n", "default", "70", "target.object", "bluez_output.88_92_CC_9C_41_0E.1", "Spa:String") in pw.calls
    again = asyncio.run(driver.audio_route_stream("bluez_output.88_92_CC_9C_41_0E.1"))
    assert again["status"] == "unchanged"
    released = asyncio.run(driver.audio_route_stream(None))
    assert released["status"] == "released" and pw.streams[70]["sink"] is None
    assert asyncio.run(driver.audio_route_stream(None))["status"] == "unchanged"  # rien à rendre


async def _no_sleep(_):
    return None


def test_retour_arriere_si_le_flux_ne_rejoint_pas_la_sortie(pw_tools, monkeypatch):
    monkeypatch.setattr("app.devices.linux.asyncio.sleep", _no_sleep)
    driver, pw = _driver({70: {"binary": "chromium", "app": "Chromium", "state": "running", "sink": None}}, follow=False)
    result = asyncio.run(driver.audio_route_stream("alsa_output.hdmi"))
    assert result["status"] == "failed"
    assert any("-d" in call for call in pw.calls)  # la métadonnée posée est retirée


def test_aucun_deplacement_si_flux_ambigu_ou_absent(pw_tools, monkeypatch):
    monkeypatch.setattr("app.devices.linux.asyncio.sleep", _no_sleep)
    two = {70: {"binary": "chromium", "app": "Chromium", "state": "running", "sink": None},
           71: {"binary": "firefox", "app": "Firefox", "state": "running", "sink": None}}
    driver, pw = _driver(two)
    assert asyncio.run(driver.audio_route_stream("alsa_output.hdmi"))["status"] == "ambiguous"
    assert not any(call[0] == "pw-metadata" for call in pw.calls)
    driver, pw = _driver({1: {"binary": "mpv", "app": "mpv", "state": "running", "sink": None}})
    assert asyncio.run(driver.audio_route_stream("alsa_output.hdmi"))["status"] == "no_stream"


def test_sortie_disparue_ou_outil_absent_sont_des_erreurs_structurees(pw_tools, monkeypatch):
    driver, _ = _driver({70: {"binary": "chromium", "app": "Chromium", "state": "running", "sink": None}})
    with pytest.raises(DeviceError) as gone:
        asyncio.run(driver.audio_route_stream("alsa_output.inconnue"))
    assert gone.value.code == "not_found" and gone.value.status == 404
    monkeypatch.setattr("app.devices.linux.shutil.which", lambda name: None if name == "pw-metadata" else f"/usr/bin/{name}")
    with pytest.raises(DeviceError) as missing:
        asyncio.run(driver.audio_route_stream("alsa_output.hdmi"))
    assert missing.value.code == "tool_missing"


def test_capacite_declaree_selon_les_outils(monkeypatch):
    async def run(which):
        monkeypatch.setattr("app.devices.linux.shutil.which", which)
        driver = LinuxDriver(runner=FakePipeWire({}))
        driver._probe_bluetooth = _async_value("pas de Bluetooth")  # noqa: SLF001
        driver._probe_wifi = _async_value("pas de Wi-Fi")  # noqa: SLF001
        return await driver.capabilities()

    caps = asyncio.run(run(lambda name: f"/usr/bin/{name}"))
    assert caps["audio_route_stream"] == {"supported": True}
    caps = asyncio.run(run(lambda name: None if name == "pw-metadata" else f"/usr/bin/{name}"))
    assert caps["audio_route_stream"]["supported"] is False and "pw-metadata" in caps["audio_route_stream"]["reason"]
    caps = asyncio.run(run(lambda name: None))
    assert caps["audio_route_stream"]["supported"] is False


def _async_value(value):
    async def inner(*args, **kwargs):
        return value

    return inner


def test_tous_les_pilotes_declarent_la_capacite():
    assert "audio_route_stream" in CAPABILITY_KEYS
    caps = asyncio.run(NullDriver("raison").capabilities())
    assert caps["audio_route_stream"] == {"supported": False, "reason": "raison"}
    with pytest.raises(DeviceError) as exc:
        asyncio.run(NullDriver().audio_route_stream("x"))
    assert exc.value.status == 501


# ---------------------------------------------------------------------------
# Service : réconciliation et mécanisme serveur
# ---------------------------------------------------------------------------


class RoutingDriver(DeviceDriver):
    name = "fake-routing"

    def __init__(self, sinks=None, route_cap=True):
        super().__init__()
        self.sinks = [dict(s) for s in (sinks if sinks is not None else [SPEAKER, JBL, HDMI])]
        self.route_cap = route_cap
        self.routed: list[str | None] = []
        self.result = {"status": "moved", "app": "Chromium"}

    async def capabilities(self):
        return {"audio_list": {"supported": True}, "audio_route_stream": {"supported": self.route_cap, "reason": "" if self.route_cap else "non"}}

    async def audio_list(self):
        return {"supported": True, "devices": self.sinks, "default_id": SPEAKER["id"]}

    async def audio_route_stream(self, sink_id):
        self.routed.append(sink_id)
        return {"status": "released"} if sink_id is None else dict(self.result)

    async def bluetooth_status(self):
        return {"supported": False}

    async def wifi_status(self):
        return {"supported": False}


class FakeSocket:
    def __init__(self, host="127.0.0.1"):
        self.client = type("C", (), {"host": host})()


def _reset_managers():
    for channel in ("radio_cable", "radio_network"):
        manager = get_radio_manager(channel)
        manager.state["route"] = None
        manager.state["playing"] = False


@pytest.fixture()
def routing_env():
    init_db()
    with SessionLocal() as db:
        db.query(Setting).filter(Setting.key.in_(KEYS)).delete(synchronize_session=False)
        db.commit()
    _reset_managers()
    driver = RoutingDriver()
    fresh = DevicesService(driver_factory=lambda: driver)
    fresh.set_driver(driver)
    yield fresh, driver
    _reset_managers()
    with SessionLocal() as db:
        db.query(Setting).filter(Setting.key.in_(KEYS)).delete(synchronize_session=False)
        db.commit()
    from app.utils.ws_manager import manager as ws

    ws._kiosk_connections["radio_cable"].clear()  # noqa: SLF001
    ws._kiosk_connections["radio_network"].clear()  # noqa: SLF001
    ws._route_reports.clear()  # noqa: SLF001


def _enable_and_route(channel="radio_cable", sink=JBL, fallback="default"):
    with SessionLocal() as db:
        db.add(Setting(key=security.SETTING_ENABLED, value="true"))
        db.commit()
        save_routes(db, {channel: describe_sink(sink) | {"fallback": fallback}})


def _add_player(channel, host="127.0.0.1", primary=True, status=None):
    from app.utils.ws_manager import manager as ws

    sock = FakeSocket(host)
    ws._kiosk_connections[channel].append(sock)  # noqa: SLF001
    ws._kiosk_channel[sock] = channel  # noqa: SLF001
    ws._kiosk_primary_status[sock] = primary  # noqa: SLF001
    if status:
        ws._route_reports[sock] = {"status": status}  # noqa: SLF001
    return sock


def test_reconciliation_publie_l_etat_et_suit_la_reconnexion(routing_env):
    fresh, driver = routing_env
    _enable_and_route()
    asyncio.run(fresh.reconcile_routes())
    assert get_radio_manager("radio_cable").state["route"]["state"] == "routed"
    assert get_radio_manager("radio_network").state["route"] is None
    driver.sinks = [SPEAKER, HDMI]  # le haut-parleur Bluetooth s'éteint
    asyncio.run(fresh.reconcile_routes())
    assert get_radio_manager("radio_cable").state["route"]["state"] == "missing"
    driver.sinks = [SPEAKER, {**JBL, "id": "bluez_output.88_92_CC_9C_41_0E.a2dp-sink"}]  # il revient (autre nœud)
    asyncio.run(fresh.reconcile_routes())
    assert get_radio_manager("radio_cable").state["route"]["state"] == "routed"


def test_fonction_desactivee_aucune_route_publiee_ni_appliquee(routing_env):
    fresh, driver = routing_env
    with SessionLocal() as db:
        save_routes(db, {"radio_cable": describe_sink(JBL)})  # route mémorisée, mais la fonction n'est pas activée
    _add_player("radio_cable")
    get_radio_manager("radio_cable").state["playing"] = True
    asyncio.run(fresh.reconcile_routes())
    assert get_radio_manager("radio_cable").state["route"] is None and driver.routed == []


def test_liste_des_sorties_indisponible_route_inconnue_sans_erreur(routing_env):
    fresh, driver = routing_env
    _enable_and_route()

    async def boom():
        raise DeviceError("audio_unavailable", "PipeWire ne répond pas", 502)

    driver.audio_list = boom
    asyncio.run(fresh.reconcile_routes())
    assert get_radio_manager("radio_cable").state["route"]["state"] == "unknown"


def test_le_serveur_deplace_le_flux_d_un_lecteur_local_qui_joue(routing_env):
    fresh, driver = routing_env
    _enable_and_route()
    _add_player("radio_cable", status="unsupported")
    get_radio_manager("radio_cable").state["playing"] = True
    asyncio.run(fresh.reconcile_routes())
    assert driver.routed == [JBL["id"]]
    assert fresh.server_status("radio_cable") == {"status": "moved", "app": "Chromium"}
    # La route est effacée : le flux déplacé est rendu à la sortie par défaut.
    with SessionLocal() as db:
        save_routes(db, {})
    asyncio.run(fresh.reconcile_routes())
    assert driver.routed[-1] is None


def test_le_serveur_ne_touche_pas_a_ce_que_le_navigateur_a_applique(routing_env):
    fresh, driver = routing_env
    _enable_and_route()
    _add_player("radio_cable", status="applied")
    get_radio_manager("radio_cable").state["playing"] = True
    asyncio.run(fresh.reconcile_routes())
    assert driver.routed == [] and fresh.server_status("radio_cable") == {"status": "browser"}


def test_lecteur_distant_ou_radio_a_l_arret_le_serveur_n_agit_pas(routing_env):
    fresh, driver = routing_env
    _enable_and_route()
    _add_player("radio_cable", host="203.0.113.9", status="unsupported")  # lecteur sur un autre appareil
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
        db.add(Setting(key=security.SETTING_ENABLED, value="true"))
        db.commit()
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
    _enable_and_route()
    _add_player("radio_cable", status="unsupported")
    get_radio_manager("radio_cable").state["playing"] = True
    asyncio.run(fresh.reconcile_routes())
    assert driver.routed == [] and fresh.server_status("radio_cable")["status"] == "unsupported"


def test_une_panne_du_pilote_ne_leve_jamais_et_ne_touche_pas_a_la_lecture(routing_env):
    fresh, driver = routing_env
    _enable_and_route()
    _add_player("radio_cable", status="unsupported")
    manager = get_radio_manager("radio_cable")
    manager.state["playing"] = True

    async def boom(sink_id):
        raise RuntimeError("D-Bus a planté")

    driver.audio_route_stream = boom
    asyncio.run(fresh.reconcile_routes())  # ne lève pas
    assert manager.state["playing"] is True


# ---------------------------------------------------------------------------
# API : accès, validation, vue
# ---------------------------------------------------------------------------


@pytest.fixture()
def api(routing_env, monkeypatch):
    fresh, driver = routing_env
    from app.devices import service as service_module
    import app.routers.devices as devices_router

    monkeypatch.setattr(devices_router, "service", fresh)
    monkeypatch.setattr(service_module, "service", fresh)
    security.sessions.revoke_all()
    security.rate_limiter = security.RateLimiter()
    devices_router.security.rate_limiter = security.rate_limiter
    return fresh, driver


def _local(monkeypatch):
    monkeypatch.setattr("app.routers.devices.is_local_request", lambda request: True)


def test_acces_desactive_pin_requis_et_session(api, monkeypatch):
    client = TestClient(app, client=("203.0.113.7", 50000))
    assert client.get("/api/devices/routing").json()["detail"]["code"] == "devices_disabled"
    assert client.get("/api/devices/mixer").json()["detail"]["code"] == "devices_disabled"
    with SessionLocal() as db:
        db.add(Setting(key=security.SETTING_ENABLED, value="true"))
        db.commit()
    assert client.get("/api/devices/routing").json()["detail"]["code"] == "pin_not_set"
    with SessionLocal() as db:
        db.add(Setting(key=security.SETTING_PIN_HASH, value=security.hash_pin("123456")))
        db.commit()
    for call in (lambda: client.get("/api/devices/routing"), lambda: client.put("/api/devices/routing", json={"channel": "radio_cable", "clear": True}),
                 lambda: client.get("/api/devices/mixer"), lambda: client.put("/api/devices/mixer/radio_cable", json={"mix": {}})):
        response = call()
        assert response.status_code == 401 and response.json()["detail"]["code"] == "pin_required"
    assert client.post("/api/devices/session", json={"pin": "123456"}).status_code == 200
    assert client.get("/api/devices/routing").status_code == 200


def test_choix_effacement_et_repli_d_une_route(api, monkeypatch):
    fresh, driver = api
    _local(monkeypatch)
    with SessionLocal() as db:
        db.add(Setting(key=security.SETTING_ENABLED, value="true"))
        db.commit()
    client = TestClient(app)
    view = client.get("/api/devices/routing").json()
    assert view["supported"] is True and [o["channel"] for o in view["outputs"]] == ["radio_cable", "radio_network"]
    assert all(o["route"] is None and o["state"] == "default" for o in view["outputs"])
    assert view["server_mechanism"]["supported"] is True and view["fallbacks"] == ["default", "mute"]

    chosen = client.put("/api/devices/routing", json={"channel": "radio_cable", "sink_id": JBL["id"]})
    assert chosen.status_code == 200
    cable = chosen.json()["outputs"][0]
    assert cable["route"]["label"] == "JBL Live 770NC" and cable["route"]["fallback"] == "default" and cable["state"] == "routed" and cable["sink_id"] == JBL["id"]
    assert get_radio_manager("radio_cable").state["route"]["state"] == "routed"  # publié au lecteur
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
    with SessionLocal() as db:
        db.add(Setting(key=security.SETTING_ENABLED, value="true"))
        db.commit()
    client = TestClient(app)
    assert client.put("/api/devices/audio/meta", json={"id": JBL["id"], "alias": "Enceinte du fond"}).status_code == 200
    route = client.put("/api/devices/routing", json={"channel": "radio_network", "sink_id": JBL["id"]}).json()["outputs"][1]["route"]
    assert route["label"] == "Enceinte du fond"
    # Les libellés de correspondance restent ceux du système (l'alias n'existe pas dans le navigateur).
    assert "Enceinte du fond" not in get_radio_manager("radio_network").state["route"]["match"]


def test_erreurs_structurees_jamais_de_500(api, monkeypatch):
    fresh, driver = api
    _local(monkeypatch)
    with SessionLocal() as db:
        db.add(Setting(key=security.SETTING_ENABLED, value="true"))
        db.commit()
    client = TestClient(app)

    def code(response):
        return response.status_code, response.json()["detail"]["code"]

    assert code(client.put("/api/devices/routing", json={"channel": "cinema", "sink_id": "x"})) == (400, "bad_channel")
    assert code(client.put("/api/devices/routing", json={"channel": "radio", "sink_id": "x"})) == (400, "bad_channel")
    assert code(client.put("/api/devices/routing", json={"channel": "radio_cable", "sink_id": "x", "fallback": "boum"})) == (400, "bad_fallback")
    assert code(client.put("/api/devices/routing", json={"channel": "radio_cable", "sink_id": "disparue"})) == (404, "not_found")
    assert code(client.put("/api/devices/routing", json={"channel": "radio_cable", "fallback": "mute"})) == (400, "no_route")
    assert code(client.put("/api/devices/routing", json={"channel": "radio_cable"})) == (400, "bad_request")
    assert client.put("/api/devices/routing", json={}).status_code == 422  # corps invalide : validation FastAPI, pas une 500

    async def boom():
        raise DeviceError("audio_unavailable", "PipeWire ne répond pas", 502)

    driver.audio_list = boom
    assert code(client.put("/api/devices/routing", json={"channel": "radio_cable", "sink_id": JBL["id"]})) == (501, "unsupported")
    view = client.get("/api/devices/routing")
    assert view.status_code == 200  # la vue dégrade proprement (route « inconnue »)


def test_pilote_nul_vue_non_prise_en_charge(api, monkeypatch):
    fresh, _ = api
    fresh.set_driver(NullDriver("Pas ici."))
    _local(monkeypatch)
    with SessionLocal() as db:
        db.add(Setting(key=security.SETTING_ENABLED, value="true"))
        db.commit()
    client = TestClient(app)
    view = client.get("/api/devices/routing").json()
    assert view["supported"] is False and view["reason"] == "Pas ici." and view["server_mechanism"]["supported"] is False
    response = client.put("/api/devices/routing", json={"channel": "radio_cable", "sink_id": "x"})
    assert response.status_code == 501 and response.json()["detail"]["code"] == "unsupported"


# ---------------------------------------------------------------------------
# WebSocket : rapport du lecteur
# ---------------------------------------------------------------------------


def test_le_rapport_du_lecteur_est_memorise_borne_et_retire_a_la_deconnexion(api, monkeypatch):
    fresh, driver = api
    _local(monkeypatch)
    with SessionLocal() as db:
        db.add(Setting(key=security.SETTING_ENABLED, value="true"))
        db.commit()
    client = TestClient(app)
    from app.routers import playback as playback_router

    monkeypatch.setattr(playback_router, "devices_service", fresh)
    with client.websocket_connect("/ws/playback") as ws:
        ws.send_json({"command": "identify", "params": {"role": "kiosk", "channel": "radio_cable", "client_id": "t1", "page": "radio"}})
        while ws.receive_json()["event"] != "kiosk_role":  # après boot_id et les états de synchronisation
            pass
        ws.send_json({"command": "radio_report_route", "params": {"channel": "radio_cable", "status": "needs_labels"}})
        _wait_for(lambda: _players(client, "radio_cable") == ["needs_labels"])
        ws.send_json({"command": "radio_report_route", "params": {"channel": "radio_cable", "status": "n'importe quoi"}})
        _wait_for(lambda: _players(client, "radio_cable") == ["error"])
        assert "error" in PLAYER_ROUTE_STATUSES
    _wait_for(lambda: _players(client, "radio_cable") == [])


def _players(client, channel):
    view = client.get("/api/devices/routing").json()
    output = next(o for o in view["outputs"] if o["channel"] == channel)
    return [p["status"] for p in output["players"]]


def _wait_for(predicate, tries=60):
    import time

    for _ in range(tries):
        if predicate():
            return
        time.sleep(0.05)
    assert predicate()


def test_un_client_non_identifie_ne_peut_pas_poser_de_rapport(api, monkeypatch):
    fresh, _ = api
    client = TestClient(app)
    with client.websocket_connect("/ws/playback") as ws:
        ws.send_json({"command": "radio_report_route", "params": {"channel": "radio_cable", "status": "applied"}})
        ws.send_json({"command": "pong"})
    from app.utils.ws_manager import manager as manager_ws

    assert not manager_ws._route_reports  # noqa: SLF001
