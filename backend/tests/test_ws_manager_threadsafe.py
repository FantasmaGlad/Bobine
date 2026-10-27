"""Couvre `ConnectionManager.broadcast_threadsafe`, le pont utilisé par les endpoints
FastAPI SYNCHRONES (`def`, exécutés dans le threadpool) et les exécuteurs
d'import (ffmpeg_executor/io_executor) pour diffuser un évènement WebSocket
sans jamais appeler une coroutine directement depuis un thread qui n'est pas
celui de la boucle asyncio — cf. `routers/videos.py`/`utils/watcher.py`.

Simule exactement ce contexte : une boucle asyncio tourne dans un thread
dédié (comme la boucle principale d'uvicorn), et `broadcast_threadsafe` est
appelée depuis le thread de TEST (qui n'est pas celui de la boucle) — la
même relation que threadpool FastAPI -> boucle principale.
"""

import asyncio
import threading
import time

from app.utils import ws_manager as ws_manager_module
from app.utils.ws_manager import ConnectionManager


def test_broadcast_threadsafe_without_bound_loop_is_a_safe_noop():
    """Avant `bind_loop()` (ex. un appel trop précoce, ou un test qui
    n'initialise pas le cycle de vie complet de l'app) : ne doit jamais
    lever, juste ne rien faire."""
    manager = ConnectionManager()
    manager.broadcast_threadsafe({"event": "library_change"})  # ne doit pas lever


def test_broadcast_threadsafe_delivers_message_from_another_thread():
    manager = ConnectionManager()
    received = []

    async def _fake_send_json(message):
        received.append(message)

    class _FakeWebSocket:
        async def send_json(self, message):
            await _fake_send_json(message)

    loop_ready = threading.Event()
    loop_holder = {}

    def _run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop_holder["loop"] = loop
        loop_ready.set()
        loop.run_forever()

    loop_thread = threading.Thread(target=_run_loop, daemon=True)
    loop_thread.start()
    loop_ready.wait(timeout=5)
    loop = loop_holder["loop"]

    # Enregistre une fausse connexion et lie la boucle du thread — exactement
    # ce que fait `main.py::lifespan` avec `asyncio.get_running_loop()`.
    fake_ws = _FakeWebSocket()

    async def _register():
        manager.active_connections[fake_ws] = asyncio.current_task()

    asyncio.run_coroutine_threadsafe(_register(), loop).result(timeout=5)
    manager.bind_loop(loop)

    # Appelé depuis CE thread (le thread de test), pas celui de la boucle —
    # relation identique à un endpoint FastAPI `def` (threadpool) appelant
    # broadcast_threadsafe() alors que la vraie boucle tourne ailleurs.
    manager.broadcast_threadsafe({"event": "library_change", "reason": "video_updated"})

    deadline = time.monotonic() + 5
    while not received and time.monotonic() < deadline:
        time.sleep(0.05)

    loop.call_soon_threadsafe(loop.stop)
    loop_thread.join(timeout=5)
    loop.close()

    assert received == [{"event": "library_change", "reason": "video_updated"}]


def test_broadcast_actually_closes_a_client_that_times_out(monkeypatch):
    """Bug réel trouvé en déployant sur la tablette pilote (pas en relecture
    de code) : `broadcast()` retirait un client lent/bloqué de
    `active_connections` SANS jamais fermer sa connexion WebSocket — le
    client, lui, ne recevait ni frame de fermeture ni erreur, et son objet
    WebSocket restait `OPEN` indéfiniment de son propre point de vue,
    silencieusement muet (plus aucun `position_tick`), jusqu'au keepalive
    serveur (jusqu'à 90s). Reproduit et confirmé par un test en conditions
    réelles sur Wi-Fi (pas seulement en local, où le bug ne se manifestait
    jamais).

    Ce test vérifie directement le contrat requis : un client dont l'envoi
    dépasse le délai DOIT recevoir un appel à `close()` (pour que son
    propre `onclose` se déclenche et qu'il se reconnecte), pas seulement
    être oublié en silence côté serveur."""
    monkeypatch.setattr(ws_manager_module, "BROADCAST_SEND_TIMEOUT_SECONDS", 0.1)

    manager = ConnectionManager()

    class _SlowWebSocket:
        def __init__(self):
            self.closed = False

        async def send_json(self, message):
            # Ne se termine jamais avant le timeout du test (0.1s) —
            # simule un client dont l'envoi ne progresse plus (Wi-Fi
            # dégradé), sans jamais lever d'exception de lui-même.
            await asyncio.sleep(10)

        async def close(self):
            self.closed = True

    class _FastWebSocket:
        def __init__(self):
            self.received = []
            self.closed = False

        async def send_json(self, message):
            self.received.append(message)

        async def close(self):
            self.closed = True

    async def _run():
        slow = _SlowWebSocket()
        fast = _FastWebSocket()
        manager.active_connections[slow] = None
        manager.active_connections[fast] = None

        await manager.broadcast({"event": "position_tick"})

        assert slow.closed, "le client lent/bloqué n'a jamais été fermé — il resterait figé indéfiniment côté client"
        assert slow not in manager.active_connections
        assert not fast.closed
        assert fast in manager.active_connections
        assert fast.received == [{"event": "position_tick"}]

    asyncio.run(_run())


def test_broadcast_does_not_create_a_coroutine_on_stopped_or_closed_loop(monkeypatch):
    manager = ConnectionManager()
    loop = asyncio.new_event_loop()
    manager.bind_loop(loop)
    def unexpected_broadcast(message):
        raise AssertionError("a stopped loop cannot accept a broadcast")
    monkeypatch.setattr(manager, "broadcast", unexpected_broadcast)
    try:
        manager.broadcast_threadsafe({"event": "shutdown"})
    finally:
        loop.close()
    manager.broadcast_threadsafe({"event": "shutdown"})


def test_broadcast_closes_coroutine_if_loop_closes_during_submission(monkeypatch):
    from unittest.mock import Mock
    manager = ConnectionManager()
    loop = Mock()
    loop.is_closed.return_value = False
    loop.is_running.return_value = True
    manager.bind_loop(loop)
    coroutine = Mock()
    monkeypatch.setattr(manager, "broadcast", lambda message: coroutine)
    def reject_submission(coro, target):
        assert coro is coroutine and target is loop
        raise RuntimeError("Event loop is closed")
    monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", reject_submission)
    manager.broadcast_threadsafe({"event": "shutdown"})
    coroutine.close.assert_called_once_with()
