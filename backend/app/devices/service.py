"""Service des périphériques : pilote unique du processus, évènements WebSocket, routage des sorties."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Callable

from app.utils.ws_manager import manager as ws_manager

from . import locality
from .base import DeviceDriver, DeviceError
from .registry import build_driver
from .routing import load_routes, player_route_state, resolve_route

logger = logging.getLogger(__name__)

MONITOR_INTERVAL_SECONDS = 8.0
_EVENT_MIN_GAP = 0.25

PLAYER_ROUTE_STATUSES = frozenset({"applied", "default", "muted", "unsupported", "insecure", "needs_labels", "no_match", "missing", "error"})


class DevicesService:
    def __init__(self, driver_factory: Callable[[], DeviceDriver] = build_driver) -> None:
        self._driver_factory = driver_factory
        self._driver: DeviceDriver | None = None
        self._last_event: dict[str, float] = {}
        self._monitor: asyncio.Task[None] | None = None
        self._snapshots: dict[str, str] = {}
        self._has_routes = False
        self._server_moved = False
        self._server_status: dict[str, dict[str, Any]] = {}
        self._reconcile_task: asyncio.Task[None] | None = None

    @property
    def driver(self) -> DeviceDriver:
        if self._driver is None:
            self._driver = self._driver_factory()
            self._driver.set_change_callback(self.notify)
        return self._driver

    def set_driver(self, driver: DeviceDriver | None) -> None:
        """Remplace le pilote (tests, rechargement)."""
        self._driver = driver
        if driver is not None:
            driver.set_change_callback(self.notify)

    def notify(self, scope: str) -> None:
        """Signale un changement (appelable depuis n'importe quel thread)."""
        now = time.monotonic()
        if now - self._last_event.get(scope, 0.0) < _EVENT_MIN_GAP:
            return
        self._last_event[scope] = now
        ws_manager.broadcast_threadsafe({"event": "devices_changed", "scope": scope})

    async def _snapshot_scope(self, scope: str) -> str:
        driver = self.driver
        try:
            if scope == "audio":
                data: Any = await driver.audio_list()
            else:
                data = await driver.bluetooth_status()
                if isinstance(data, dict):
                    data = {k: v for k, v in data.items() if k != "devices"} | {
                        "devices": [{k: v for k, v in d.items() if k != "rssi"} for d in data.get("devices", [])]
                    }
        except DeviceError as exc:
            data = {"error": exc.code}
        return hashlib.sha1(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()

    async def _monitor_loop(self) -> None:
        while True:
            await asyncio.sleep(MONITOR_INTERVAL_SECONDS)
            try:
                if not ws_manager.active_connections:
                    continue
                caps = await self.driver.capabilities()
                audio_changed = False
                for scope, key in (("audio", "audio_list"), ("bluetooth", "bluetooth_status")):
                    if not caps.get(key, {}).get("supported"):
                        continue
                    digest = await self._snapshot_scope(scope)
                    previous = self._snapshots.get(scope)
                    self._snapshots[scope] = digest
                    if previous is not None and previous != digest:
                        self.notify(scope)
                        audio_changed = audio_changed or scope == "audio"
                if audio_changed or self._has_routes or self._server_moved:
                    await self.reconcile_routes()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.debug("Surveillance des périphériques : %s", exc)

    async def start(self) -> None:
        try:
            await self.driver.start()
        except Exception as exc:
            logger.warning("Démarrage du pilote de périphériques impossible : %s", exc)
        if self._monitor is None or self._monitor.done():
            self._monitor = asyncio.create_task(self._monitor_loop())
        self.schedule_reconcile()

    async def stop(self) -> None:
        tasks = [task for task in (self._monitor, self._reconcile_task)
                 if task is not None and not task.done()]
        for task in tasks:
            task.cancel()
        self._monitor = self._reconcile_task = None
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.debug("Arrêt d'une tâche de périphériques : %s", result)
        if self._driver is not None:
            try:
                await self._driver.stop()
            except Exception as exc:
                logger.debug("Arrêt du pilote de périphériques : %s", exc)

    async def current_sinks(self) -> list[dict[str, Any]] | None:
        """Sorties audio actuelles, ou None si la plateforme ne sait pas les lister (route alors « inconnue »)."""
        try:
            caps = await self.driver.capabilities()
            if not caps.get("audio_list", {}).get("supported"):
                return None
            listing = await self.driver.audio_list()
        except Exception as exc:
            logger.debug("Sorties audio indisponibles pour le routage : %s", exc)
            return None
        return list(listing.get("devices", [])) if listing.get("supported") else None

    def schedule_reconcile(self) -> None:
        """Programme une réconciliation des routes (sans attendre, une seule à la fois)."""
        if self._reconcile_task is not None and not self._reconcile_task.done():
            return
        try:
            self._reconcile_task = asyncio.get_running_loop().create_task(self.reconcile_routes())
        except RuntimeError:
            self._reconcile_task = None

    def server_status(self, channel: str) -> dict[str, Any] | None:
        return self._server_status.get(channel)

    def note_player_report(self, channel: str) -> None:
        """Un lecteur a rapporté le résultat de sa route : les interfaces ouvertes se relisent, et le serveur réévalue (il ne déplace un flux que si le navigateur n'a pas pu appliquer la route lui-même)."""
        self.notify("routing")
        self.schedule_reconcile()

    async def reconcile_routes(self) -> None:
        """Résout les routes mémorisées contre les sorties actuelles, publie l'état « route » aux lecteurs de chaque sortie radio, puis laisse le serveur déplacer un flux quand c'est possible et nécessaire."""
        from app.database import SessionLocal
        from app.radio.manager import get_all_radio_managers

        try:
            with SessionLocal() as db:
                routes = load_routes(db)
            self._has_routes = bool(routes)
            sinks = await self.current_sinks() if routes else None
            for channel, manager in get_all_radio_managers().items():
                route = routes.get(channel)
                await manager.set_route(player_route_state(route, resolve_route(route, sinks)))
            await self._apply_server_routes(routes, sinks)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug("Réconciliation des routes audio : %s", exc)

    async def _apply_server_routes(self, routes: dict[str, dict[str, Any]], sinks: list[dict[str, Any]] | None) -> None:
        from app.radio.manager import get_all_radio_managers

        before = json.dumps(self._server_status, sort_keys=True, default=str)
        caps = await self.driver.capabilities()
        capability = caps.get("audio_route_stream", {})
        managers = get_all_radio_managers()
        candidates: list[tuple[str, dict[str, Any]]] = []
        for channel, manager in managers.items():
            route = routes.get(channel)
            local = [p for p in ws_manager.route_players(channel) if locality.is_local_client(str(p["ip"]))]
            if route is None or not local:
                self._server_status.pop(channel, None)
                continue
            if not capability.get("supported"):
                self._server_status[channel] = {"status": "unsupported", "reason": capability.get("reason", "")}
                continue
            if any((p["report"] or {}).get("status") == "applied" for p in local):
                self._server_status[channel] = {"status": "browser"}
                continue
            resolution = resolve_route(route, sinks)
            if resolution["state"] != "routed" or not manager.state.get("playing"):
                self._server_status[channel] = {"status": "waiting"}
                continue
            candidates.append((channel, resolution["sink"]))
        if capability.get("supported"):
            try:
                if len(candidates) > 1:
                    for channel, _ in candidates:
                        self._server_status[channel] = {"status": "ambiguous"}
                elif candidates:
                    channel, sink = candidates[0]
                    result = await self.driver.audio_route_stream(str(sink["id"]))
                    self._server_status[channel] = {k: v for k, v in result.items() if k in ("status", "app", "detail")}
                    self._server_moved = result.get("status") in ("moved", "unchanged")
                elif self._server_moved:
                    await self.driver.audio_route_stream(None)
                    self._server_moved = False
            except DeviceError as exc:
                for channel, _ in candidates:
                    self._server_status[channel] = {"status": "failed", "detail": exc.message}
        if json.dumps(self._server_status, sort_keys=True, default=str) != before:
            self.notify("routing")


service = DevicesService()
