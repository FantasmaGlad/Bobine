"""Diffusion filtrée par canal (plan 4.0, P2-3) : un client n'est plus
inondé des évènements des canaux qui ne le concernent pas."""

import asyncio

from app.utils.ws_manager import ConnectionManager


class FakeWS:
    def __init__(self):
        self.received = []

    async def send_json(self, message):
        self.received.append(message)

    async def close(self):
        pass


def _tick(channel):
    return {"event": "state_change", "cause": "position_tick", "channel": channel, "data": {}}


def _run(coro):
    return asyncio.run(coro)


def _setup():
    m = ConnectionManager()
    clients = {name: FakeWS() for name in ("cable", "network", "legacy", "settings_only")}
    m.active_connections.update({ws: None for ws in clients.values()})
    m.subscribe(clients["cable"], ["cable"])
    m.subscribe(clients["network"], ["network"])
    m.subscribe(clients["settings_only"], [])
    return m, clients


def test_les_evenements_de_canal_ne_vont_qu_aux_abonnes_de_ce_canal():
    m, c = _setup()
    _run(m.broadcast(_tick("network")))
    assert len(c["network"].received) == 1
    assert c["cable"].received == []
    assert c["settings_only"].received == []
    # Client sans abonnement (ancien bundle) : comportement historique, tout reçu.
    assert len(c["legacy"].received) == 1


def test_les_evenements_globaux_ne_sont_jamais_filtres():
    m, c = _setup()
    for event in ({"event": "display_output", "channel": "network", "output": "cinema"},
                  {"event": "settings_change", "theme": "clair"},
                  {"event": "force_reload"},
                  {"event": "library_change"}):
        _run(m.broadcast(event))
    for name in c:
        assert len(c[name].received) == 4, name


def test_cinema_state_et_cinema_command_sont_filtres_par_canal():
    m, c = _setup()
    _run(m.broadcast({"event": "cinema_state", "channel": "cable", "data": {}}))
    _run(m.broadcast({"event": "cinema_command", "channel": "cable", "action": "play"}))
    assert len(c["cable"].received) == 2
    assert c["network"].received == []


def test_un_kiosque_est_abonne_a_son_propre_canal_a_l_identification():
    m = ConnectionManager()
    ws = FakeWS()
    m.active_connections[ws] = None
    _run(m.register_kiosk(ws, "network", "id-1"))
    _run(m.broadcast(_tick("cable")))
    assert ws.received == []
    _run(m.broadcast(_tick("network")))
    assert len(ws.received) == 1


def test_le_desabonnement_est_nettoye_a_la_deconnexion():
    m = ConnectionManager()
    ws = FakeWS()
    m.subscribe(ws, ["cable"])

    async def _go():
        m.disconnect(ws)
        await asyncio.sleep(0)

    _run(_go())
    assert ws not in m._subscriptions
