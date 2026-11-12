"""Couvre `ConnectionManager.broadcast_threadsafe`, le pont utilisé par les endpoints FastAPI SYNCHRONES (`def`, exécutés dans le threadpool) et les exécuteurs d'import (ffmpeg_executor/io_executor) pour diffuser un évènement WebSocket sans jamais appeler une coroutine directement depuis un thread qui n'est pas celui de la boucle asyncio — cf."""

import asyncio
import threading
import time

from app.utils import ws_manager as ws_manager_module
from app.utils.ws_manager import ConnectionManager


def test_broadcast_threadsafe_without_bound_loop_is_a_safe_noop():
    """Avant `bind_loop()` (ex."""
    manager = ConnectionManager()
    manager.broadcast_threadsafe({"event": "library_change"})


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

    fake_ws = _FakeWebSocket()

    async def _register():
        manager.active_connections[fake_ws] = asyncio.current_task()

    asyncio.run_coroutine_threadsafe(_register(), loop).result(timeout=5)
    manager.bind_loop(loop)

    manager.broadcast_threadsafe({"event": "library_change", "reason": "video_updated"})

    deadline = time.monotonic() + 5
    while not received and time.monotonic() < deadline:
        time.sleep(0.05)

    loop.call_soon_threadsafe(loop.stop)
    loop_thread.join(timeout=5)
    loop.close()

    assert received == [{"event": "library_change", "reason": "video_updated"}]


def test_broadcast_actually_closes_a_client_that_times_out(monkeypatch):
    """Bug réel trouvé en déployant sur la tablette pilote (pas en relecture de code) : `broadcast()` retirait un client lent/bloqué de `active_connections` SANS jamais fermer sa connexion WebSocket — le client, lui, ne recevait ni frame de fermeture ni erreur, et son objet WebSocket restait `OPEN` indéfiniment de son propre point de vue, silencieusement muet (plus aucun `position_tick`), jusqu'au keepalive serveur (jusqu'à 90s)."""
    monkeypatch.setattr(ws_manager_module, "BROADCAST_SEND_TIMEOUT_SECONDS", 0.1)

    manager = ConnectionManager()

    class _SlowWebSocket:
        def __init__(self):
            self.closed = False

        async def send_json(self, message):
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


def test_broadcast_never_creates_coroutine_if_loop_stops_after_running_check(monkeypatch):
    from unittest.mock import Mock
    manager = ConnectionManager()
    loop = asyncio.new_event_loop()
    manager.bind_loop(loop)
    broadcast = Mock(side_effect=AssertionError("callback must be discarded"))
    monkeypatch.setattr(manager, "broadcast", broadcast)
    monkeypatch.setattr(loop, "is_running", lambda: True)
    try:
        manager.broadcast_threadsafe({"event": "shutdown"})
    finally:
        monkeypatch.setattr(loop, "is_running", lambda: False)
        loop.close()
    broadcast.assert_not_called()


def test_broadcast_handles_loop_closed_during_submission(monkeypatch, caplog):
    from unittest.mock import Mock
    manager = ConnectionManager()
    loop = Mock()
    loop.is_closed.return_value = False
    loop.is_running.return_value = True
    loop.call_soon_threadsafe.side_effect = RuntimeError("Event loop is closed")
    manager.bind_loop(loop)
    broadcast = Mock()
    monkeypatch.setattr(manager, "broadcast", broadcast)
    manager.broadcast_threadsafe({"event": "shutdown"})
    broadcast.assert_not_called()
    assert "échec de programmation" in caplog.text
