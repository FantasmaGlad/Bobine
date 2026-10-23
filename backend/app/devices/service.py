"""Service des périphériques : pilote unique du processus, évènements WebSocket, filet de sécurité Wi-Fi.

Les évènements WebSocket `devices_changed` ne portent AUCUNE donnée (juste la portée : audio,
bluetooth, wifi) : les clients relisent l'état par REST, derrière le contrôle d'accès (PIN).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

from app.utils.activity_log import log_activity
from app.utils.ws_manager import manager as ws_manager

from . import security
from .base import DeviceDriver, DeviceError
from .registry import build_driver
from .routing import load_routes, player_route_state, resolve_route

logger = logging.getLogger(__name__)

WIFI_CONFIRM_SECONDS = 60
MONITOR_INTERVAL_SECONDS = 8.0
_EVENT_MIN_GAP = 0.25

# Résultats qu'un lecteur /radio peut rapporter après avoir tenté d'appliquer sa route (lib/audioRoute.ts) ; tout autre
# texte reçu est ramené à « error » (le rapport vient d'un client, il n'est jamais cru sur parole).
PLAYER_ROUTE_STATUSES = frozenset({"applied", "default", "muted", "unsupported", "insecure", "needs_labels", "no_match", "missing", "error"})


@dataclass
class WifiPendingChange:
    """Changement de Wi-Fi à reconfirmer : sans confirmation avant l'échéance, retour à l'ancien réseau."""

    kind: str  # "connect" | "power_off"
    previous_connection: str | None
    target: str
    deadline: float  # horloge monotonique


class DevicesService:
    def __init__(self, driver_factory: Callable[[], DeviceDriver] = build_driver) -> None:
        self._driver_factory = driver_factory
        self._driver: DeviceDriver | None = None
        self._last_event: dict[str, float] = {}
        self._monitor: asyncio.Task[None] | None = None
        self._snapshots: dict[str, str] = {}
        self._wifi_pending: WifiPendingChange | None = None
        self._wifi_timer: asyncio.Task[None] | None = None
        # Routage audio par sortie radio (phase 2)
        self._has_routes = False
        self._server_moved = False
        self._server_status: dict[str, dict[str, Any]] = {}
        self._reconcile_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------ pilote
    @property
    def driver(self) -> DeviceDriver:
        if self._driver is None:
            self._driver = self._driver_factory()
            self._driver.set_change_callback(self.notify)
        return self._driver

    def set_driver(self, driver: DeviceDriver | None) -> None:
        """Remplace le pilote (tests, rechargement). L'ancien est simplement abandonné."""
        self._driver = driver
        if driver is not None:
            driver.set_change_callback(self.notify)

    # ------------------------------------------------------------------ évènements
    def notify(self, scope: str) -> None:
        """Signale un changement (appelable depuis n'importe quel thread). Limité à ~4/s et par portée."""
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
            elif scope == "bluetooth":
                data = await driver.bluetooth_status()
                if isinstance(data, dict):
                    data = {k: v for k, v in data.items() if k != "devices"} | {
                        "devices": [{k: v for k, v in d.items() if k != "rssi"} for d in data.get("devices", [])]
                    }
            else:
                data = await driver.wifi_status()
                if isinstance(data, dict) and isinstance(data.get("networks"), list):
                    data = {**data, "networks": [{k: v for k, v in n.items() if k != "signal"} for n in data["networks"]]}
        except DeviceError as exc:
            data = {"error": exc.code}
        return hashlib.sha1(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()

    async def _monitor_loop(self) -> None:
        """Détecte les changements extérieurs (branchement d'un casque, perte du Wi-Fi...) tant qu'un client écoute."""
        while True:
            await asyncio.sleep(MONITOR_INTERVAL_SECONDS)
            try:
                if not ws_manager.active_connections:
                    continue
                caps = await self.driver.capabilities()
                audio_changed = False
                for scope, key in (("audio", "audio_list"), ("bluetooth", "bluetooth_status"), ("wifi", "wifi_status")):
                    if not caps.get(key, {}).get("supported"):
                        continue
                    digest = await self._snapshot_scope(scope)
                    previous = self._snapshots.get(scope)
                    self._snapshots[scope] = digest
                    if previous is not None and previous != digest:
                        self.notify(scope)
                        audio_changed = audio_changed or scope == "audio"
                # Routes audio : une sortie qui apparaît (haut-parleur reconnecté) ou disparaît change l'état publié aux
                # lecteurs ; un flux déplacé par le serveur est revérifié (une pause/reprise le recrée sur la sortie par défaut).
                if audio_changed or self._has_routes or self._server_moved:
                    await self.reconcile_routes()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # la surveillance ne doit jamais s'arrêter ni perturber la diffusion
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
        for task in (self._monitor, self._wifi_timer, self._reconcile_task):
            if task is not None and not task.done():
                task.cancel()
        self._monitor = self._wifi_timer = self._reconcile_task = None
        if self._driver is not None:
            try:
                await self._driver.stop()
            except Exception as exc:
                logger.debug("Arrêt du pilote de périphériques : %s", exc)

    # ------------------------------------------------------------------ routage audio par sortie radio (phase 2)
    async def current_sinks(self) -> list[dict[str, Any]] | None:
        """Sorties audio actuelles, ou None si la plateforme ne sait pas les lister (route alors « inconnue »)."""
        try:
            caps = await self.driver.capabilities()
            if not caps.get("audio_list", {}).get("supported"):
                return None
            listing = await self.driver.audio_list()
        except Exception as exc:  # une panne du pilote ne doit jamais toucher à la diffusion
            logger.debug("Sorties audio indisponibles pour le routage : %s", exc)
            return None
        return list(listing.get("devices", [])) if listing.get("supported") else None

    def schedule_reconcile(self) -> None:
        """Programme une réconciliation des routes (sans attendre, une seule à la fois)."""
        if self._reconcile_task is not None and not self._reconcile_task.done():
            return
        try:
            self._reconcile_task = asyncio.get_running_loop().create_task(self.reconcile_routes())
        except RuntimeError:  # pas de boucle (tests synchrones) : rien à programmer
            self._reconcile_task = None

    def server_status(self, channel: str) -> dict[str, Any] | None:
        return self._server_status.get(channel)

    def note_player_report(self, channel: str) -> None:
        """Un lecteur a rapporté le résultat de sa route : les interfaces ouvertes se relisent, et le serveur réévalue
        (il ne déplace un flux que si le navigateur n'a pas pu appliquer la route lui-même)."""
        self.notify("routing")
        self.schedule_reconcile()

    async def reconcile_routes(self) -> None:
        """Résout les routes mémorisées contre les sorties actuelles, publie l'état « route » aux lecteurs de chaque sortie
        radio, puis laisse le serveur déplacer un flux quand c'est possible et nécessaire. Ne lève jamais."""
        from app.database import SessionLocal
        from app.models import Setting
        from app.radio_manager import get_all_radio_managers

        try:
            with SessionLocal() as db:
                enabled_row = db.query(Setting).filter(Setting.key == security.SETTING_ENABLED).first()
                enabled = bool(enabled_row and enabled_row.value == "true")
                routes = load_routes(db) if enabled else {}
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
        """Mécanisme 2 (serveur, Linux) : déplace le flux du navigateur LOCAL qui joue la radio. Uniquement pour une sortie
        dont la radio joue, avec un lecteur local, quand aucun lecteur n'a pu appliquer la route lui-même ; un seul candidat à
        la fois (sinon « ambigu », rien n'est déplacé)."""
        from app.radio_manager import get_all_radio_managers

        before = json.dumps(self._server_status, sort_keys=True, default=str)
        caps = await self.driver.capabilities()
        capability = caps.get("audio_route_stream", {})
        managers = get_all_radio_managers()
        candidates: list[tuple[str, dict[str, Any]]] = []
        for channel, manager in managers.items():
            route = routes.get(channel)
            local = [p for p in ws_manager.route_players(channel) if security.is_local_client(str(p["ip"]))]
            if route is None or not local:
                self._server_status.pop(channel, None)
                continue
            if not capability.get("supported"):
                self._server_status[channel] = {"status": "unsupported", "reason": capability.get("reason", "")}
                continue
            if any((p["report"] or {}).get("status") == "applied" for p in local):
                self._server_status[channel] = {"status": "browser"}  # le navigateur s'en charge : le serveur n'y touche pas
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
            self.notify("routing")  # l'interface relit l'état du routage (aucune donnée dans l'évènement)

    # ------------------------------------------------------------------ filet de sécurité Wi-Fi
    @property
    def wifi_pending(self) -> WifiPendingChange | None:
        return self._wifi_pending

    def wifi_pending_info(self) -> dict[str, Any] | None:
        pending = self.wifi_pending
        if pending is None:
            return None
        return {
            "kind": pending.kind,
            "target": pending.target,
            "previous": pending.previous_connection,
            "seconds_left": max(0, int(pending.deadline - time.monotonic())),
        }

    def arm_wifi_rollback(self, kind: str, previous: str | None, target: str, seconds: float = WIFI_CONFIRM_SECONDS) -> None:
        self._cancel_wifi_timer()
        self._wifi_pending = WifiPendingChange(kind, previous, target, time.monotonic() + seconds)
        self._wifi_timer = asyncio.create_task(self._rollback_after(seconds))

    def confirm_wifi_change(self) -> bool:
        if self._wifi_pending is None:
            return False
        self._cancel_wifi_timer()
        self._wifi_pending = None
        return True

    def _cancel_wifi_timer(self) -> None:
        timer, self._wifi_timer = self._wifi_timer, None
        if timer is not None and not timer.done() and timer is not asyncio.current_task():
            timer.cancel()

    async def _rollback_after(self, seconds: float) -> None:
        try:
            await asyncio.sleep(seconds)
        except asyncio.CancelledError:
            return
        pending, self._wifi_pending = self._wifi_pending, None
        if pending is None:
            return
        try:
            if pending.kind == "power_off":
                await self.driver.wifi_set_power(True)
            elif pending.previous_connection:
                await self.driver.wifi_activate(pending.previous_connection)
            self._log("devices_wifi_rollback", f"Retour automatique ({pending.kind}) : {pending.previous_connection or 'Wi-Fi activé'}")
        except Exception as exc:  # au pire l'administrateur le fera à la main : on journalise
            logger.warning("Retour automatique du Wi-Fi impossible : %s", exc)
            self._log("devices_wifi_rollback_failed", "Retour automatique impossible")
        self.notify("wifi")

    @staticmethod
    def _log(event: str, detail: str) -> None:
        from app.database import SessionLocal

        try:
            with SessionLocal() as db:
                log_activity(db, event, detail)
        except Exception as exc:
            logger.debug("Journal d'activité indisponible : %s", exc)


service = DevicesService()
