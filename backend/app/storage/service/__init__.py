"""Service du stockage externe : surveillance, état, actions, évènements WebSocket, remappage des chemins."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable

from app.storage.drivers.base import StorageDriver
from app.storage.drivers.registry import build_storage_driver
from app.storage.formatting.manager import FormatManager
from app.storage.types import Inventory, Volume

from .constants import _EVENT_MIN_GAP
from .monitor import MonitorMixin
from .mounts import MountMixin
from .views import ViewMixin
from .transfer import TransferMixin
from .libraries import LibraryMixin
from .health import HealthMixin

logger = logging.getLogger(__name__)


class StorageService(MonitorMixin, MountMixin, ViewMixin, TransferMixin, LibraryMixin, HealthMixin):
    def __init__(self, driver_factory: Callable[[], StorageDriver] = build_storage_driver) -> None:
        self._driver_factory = driver_factory
        self._driver: StorageDriver | None = None
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._monitor: asyncio.Task[None] | None = None
        self._wake: asyncio.Event | None = None
        self._inventory = Inventory()
        self._by_key: dict[str, Volume] = {}
        self._ready = False
        self._last_error: dict[str, str] | None = None
        self._ejecting: set[str] = set()
        self._busy: dict[str, set[str]] = {}
        self._rw_lease: set[str] = set()
        self._dirty: set[str] = set()
        self._recent: list[dict[str, Any]] = []
        self._online: dict[int, str] = {}
        self._health: dict[str, tuple[float, dict[str, Any]]] = {}
        self._health_last_run: dict[str, float] = {}
        self._activity: dict[str, float] = {}
        self._standby: dict[str, dict[str, Any]] = {}
        self._mount_failures: dict[str, float] = {}
        self._portable_roots: dict[str, str] = {}
        self._written_unregistered: dict[str, int] = {}
        self._last_event: dict[str, float] = {}
        self._last_maintenance = 0.0
        self._formatting: set[str] = set()
        self.formatter = FormatManager(self)

    @property
    def driver(self) -> StorageDriver:
        if self._driver is None:
            self._driver = self._driver_factory()
            self._driver.set_change_callback(self._on_driver_event)
        return self._driver

    def set_driver(self, driver: StorageDriver | None) -> None:
        """Remplace le pilote (tests)."""
        self._driver = driver
        if driver is not None:
            driver.set_change_callback(self._on_driver_event)

    def _on_driver_event(self, scope: str) -> None:
        if self._loop is not None and self._wake is not None:
            self._loop.call_soon_threadsafe(self._wake.set)

    def notify(self, scope: str, changes: list[str] | None = None) -> None:
        """Évènement WebSocket sans donnée sensible (portée + nature)."""
        from app.utils.ws_manager import manager as ws_manager

        now = time.monotonic()
        if not changes and now - self._last_event.get(scope, 0.0) < _EVENT_MIN_GAP:
            return
        self._last_event[scope] = now
        message: dict[str, Any] = {"event": "storage_changed", "scope": scope}
        if changes:
            message["changes"] = changes
        ws_manager.broadcast_threadsafe(message)

    @staticmethod
    def _log(event: str, detail: str | None = None) -> None:
        from app.database import SessionLocal
        from app.utils.activity_log import log_activity

        try:
            with SessionLocal() as db:
                log_activity(db, event, detail)
        except Exception as exc:
            logger.debug("Journal d'activité indisponible : %s", exc)


service = StorageService()
