"""Service du stockage externe : surveillance, état, actions, évènements WebSocket, remappage des chemins.

Un seul service par processus (comme `app/devices/service.py`). Les évènements `storage_changed` ne portent
AUCUN nom ni chemin (juste la portée et la nature du changement) : les clients relisent l'état par REST,
derrière le contrôle d'accès (PIN). `library_change` (raison `storage_availability`) invite les pages de
médias à se relire quand des éléments deviennent (in)disponibles.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from app.devices.base import DeviceError
from app.storage import availability, fsadvisor, health, library, longevity, paths, transfer
from app.storage.drivers.base import StorageDriver
from app.storage.drivers.registry import build_storage_driver
from app.storage.lsblk import duplicate_uuids
from app.storage.types import Inventory, Volume, volume_public

logger = logging.getLogger(__name__)

POLL_SECONDS = 5.0           # sans signaux udisks2
POLL_SAFETY_SECONDS = 20.0   # avec signaux : filet de sécurité
SETTLE_SECONDS = 0.4         # laisse udev/udisks terminer avant de relire
HEALTH_TTL = 600.0
HEALTH_PERIOD = 6 * 3600.0
STANDBY_RETRY = 1800.0
MOUNT_RETRY = 15.0
MOUNT_SETTLE_TRIES = 4
UNMOUNT_BUSY_TRIES = 4
UNMOUNT_BUSY_SECONDS = 1.5
MOUNT_SETTLE_SECONDS = 1.5
RECENT_KEEP = 300.0
_EVENT_MIN_GAP = 0.25


def _media_for_kind(kind: str) -> str:
    return {"hdd": "hdd", "ssd": "ssd"}.get(kind, "flash")


@dataclass
class Source:
    """Ce qu'une action doit savoir d'une source : racine lisible, nature, identifiant de traçabilité."""

    key: str
    root: str
    portable: bool
    volume: Volume | None
    source_id: str  # UUID du support ou identifiant d'appareil portable


class StorageService:
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

    # ------------------------------------------------------------------ pilote
    @property
    def driver(self) -> StorageDriver:
        if self._driver is None:
            self._driver = self._driver_factory()
            self._driver.set_change_callback(self._on_driver_event)
        return self._driver

    def set_driver(self, driver: StorageDriver | None) -> None:
        """Remplace le pilote (tests). L'ancien est simplement abandonné."""
        self._driver = driver
        if driver is not None:
            driver.set_change_callback(self._on_driver_event)

    def _on_driver_event(self, scope: str) -> None:
        if self._loop is not None and self._wake is not None:
            self._loop.call_soon_threadsafe(self._wake.set)

    # ------------------------------------------------------------------ évènements
    def notify(self, scope: str, changes: list[str] | None = None) -> None:
        """Évènement WebSocket sans donnée sensible (portée + nature). Limité à ~4/s par portée."""
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

    # ------------------------------------------------------------------ cycle de vie
    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._wake = asyncio.Event()
        from app.database import SessionLocal

        def _offline() -> None:
            with SessionLocal() as db:
                library.mark_all_offline(db)

        try:
            await asyncio.to_thread(_offline)
            availability.set_online({})
            await asyncio.to_thread(transfer.purge_staging)
        except Exception as exc:
            logger.warning("Initialisation du stockage externe : %s", exc)
        try:
            await self.driver.start()
        except Exception as exc:
            logger.warning("Démarrage du pilote de stockage impossible : %s", exc)
        try:
            # Premier instantané AVANT la radio et le planning (une ambiance posée sur un support doit être
            # lisible au démarrage) ; borné : un montage qui traîne ne bloque jamais l'application.
            await asyncio.wait_for(self.refresh(), timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning("Premier instantané du stockage externe : délai dépassé, la surveillance continue en arrière-plan.")
        except Exception as exc:
            logger.warning("Premier instantané du stockage externe impossible : %s", exc)
        if self._monitor is None or self._monitor.done():
            self._monitor = asyncio.create_task(self._monitor_loop())

    async def stop(self) -> None:
        monitor, self._monitor = self._monitor, None
        if monitor is not None and not monitor.done():
            monitor.cancel()
        if self._driver is not None:
            try:
                await self._driver.stop()
            except Exception as exc:
                logger.debug("Arrêt du pilote de stockage : %s", exc)

    async def _monitor_loop(self) -> None:
        while True:
            push = bool(getattr(self.driver, "push_active", False))
            try:
                assert self._wake is not None
                await asyncio.wait_for(self._wake.wait(), timeout=POLL_SAFETY_SECONDS if push else POLL_SECONDS)
                await asyncio.sleep(SETTLE_SECONDS)
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                raise
            if self._wake is not None:
                self._wake.clear()
            try:
                await self.refresh()
                await self._maintenance()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # la surveillance ne s'arrête jamais
                logger.warning("Surveillance du stockage externe : %s", exc, exc_info=True)

    # ------------------------------------------------------------------ inventaire
    @staticmethod
    def protected_paths() -> list[str]:
        from app.config import DATA_ROOT, settings

        candidates = [
            settings.media_dir, settings.watch_dir, settings.thumbnails_dir, settings.backgrounds_dir,
            settings.backgrounds_watch_dir, settings.audio_dir, settings.audio_watch_dir, settings.radio_dir,
            settings.radio_covers_dir, settings.radio_announcements_dir, settings.radio_watch_dir,
            settings.branding_dir, settings.logs_dir, settings.subtitles_dir, str(DATA_ROOT),
        ]
        if settings.database_url.startswith("sqlite:///"):
            candidates.append(os.path.dirname(settings.database_url[len("sqlite:///"):]))
        return sorted({os.path.realpath(p) for p in candidates if p})

    async def refresh(self) -> None:
        async with self._lock:
            try:
                inventory = await self.driver.inventory(self.protected_paths())
                self._last_error = None
            except DeviceError as exc:
                self._last_error = {"code": exc.code, "message": exc.message}
                self._ready = True
                return
            await self._ingest(inventory)
            self._ready = True

    async def _ingest(self, inventory: Inventory) -> None:
        previous = self._by_key
        current = {v.key: v for v in inventory.volumes}
        changes: list[str] = []
        now = time.time()
        for key, vol in current.items():
            old = previous.get(key)
            if old is None:
                changes.append("added")
                self._log("storage_connected", f"{vol.display_name} ({vol.fstype or '?'})")
            elif old.mounted != vol.mounted:
                changes.append("mounted" if vol.mounted else "unmounted")
        for key, old in previous.items():
            if key in current:
                continue
            abrupt = old.mounted and key not in self._ejecting
            changes.append("removed_abruptly" if abrupt else "removed")
            self._log("storage_removed_abruptly" if abrupt else "storage_removed", old.display_name)
            self._recent.append({"key": key, "name": old.display_name, "at": now, "abrupt": abrupt})
            self._ejecting.discard(key)
            self._busy.pop(key, None)
            self._rw_lease.discard(key)
            self._health.pop(key, None)
            self._dirty.discard(key)
        self._recent = [r for r in self._recent if now - r["at"] < RECENT_KEEP][-20:]
        self._inventory = inventory
        self._by_key = current
        await self._sync_libraries()
        if changes:
            self.notify("volumes", changes)

    # ------------------------------------------------------------------ bibliothèques : disponibilité et remappage
    async def _sync_libraries(self) -> None:
        from app.database import SessionLocal

        def _libs() -> list[dict[str, Any]]:
            with SessionLocal() as db:
                return [
                    {"id": lib.id, "uuid": lib.fs_uuid, "enabled": lib.enabled, "settings": library.settings_of(db, lib)}
                    for lib in library.all_libraries(db)
                ]

        libs = await asyncio.to_thread(_libs)
        if not libs:
            return
        duplicates = duplicate_uuids(self._inventory.volumes)
        by_uuid = {v.fs_uuid.lower(): v for v in self._inventory.volumes if v.fs_uuid and v.fs_uuid.lower() not in duplicates}
        online: dict[int, str] = {}
        for lib in libs:
            vol = by_uuid.get((lib["uuid"] or "").lower())
            if vol is None or not lib["enabled"]:
                continue
            settings = lib["settings"]
            mountpoint = vol.mountpoint if vol.mounted else None
            if vol.mounted and settings.get("read_only") and vol.mounted_read_only is False and vol.key not in self._rw_lease and vol.key not in self._busy and vol.dev_type != "loop":
                # Le bureau monte tout en lecture-écriture : une bibliothèque doit rester en lecture seule (zéro écriture).
                # Jamais pour une image disque : udisks libère le périphérique loop dès son démontage (`Autoclear`).
                mountpoint = await self._attempt(self._remount(vol, writable=False, settings=settings)) or mountpoint
            elif not vol.mounted and settings.get("auto_mount_library") and time.monotonic() - self._mount_failures.get(vol.key, -MOUNT_RETRY) >= MOUNT_RETRY:
                mountpoint = await self._attempt(self._mount_volume(vol, writable=False, settings=settings))
                if mountpoint is None:
                    self._mount_failures[vol.key] = time.monotonic()
            if mountpoint:
                online[lib["id"]] = mountpoint
        if online == self._online:
            return
        previous = self._online
        # Retrait : indisponible tout de suite ; arrivée : seulement une fois les chemins remappés.
        availability.set_online({i: p for i, p in online.items() if previous.get(i) == p})

        def _remap() -> bool:
            with SessionLocal() as db:
                return library.apply_mapping(db, online, previous)

        await asyncio.to_thread(_remap)
        self._online = online
        availability.set_online(online)
        from app.utils.ws_manager import manager as ws_manager

        ws_manager.broadcast_threadsafe({"event": "library_change", "reason": "storage_availability"})
        arrived = [i for i in online if i not in previous]
        gone = [i for i in previous if i not in online]
        self.notify("library", (["library_online"] * len(arrived)) + (["library_offline"] * len(gone)))

    async def _attempt(self, coro: Any) -> str | None:
        """Exécute une action de montage ; retourne son résultat (point de montage) ou None si elle échoue (journalisé)."""
        try:
            return await coro
        except DeviceError as exc:
            logger.info("Stockage externe : %s (%s)", exc.message, exc.code)
        except Exception as exc:
            logger.warning("Stockage externe : %s", exc)
        return None

    # ------------------------------------------------------------------ résolution
    def _need(self, key: str) -> Volume:
        vol = self._by_key.get(key)
        if vol is None:
            raise DeviceError("volume_not_found", "Support introuvable : il a peut-être été retiré.", 404)
        return vol

    def _settings_for(self, vol: Volume) -> dict[str, Any]:
        from app.database import SessionLocal

        with SessionLocal() as db:
            return library.settings_of(db, library.get_by_uuid(db, vol.fs_uuid))

    async def _effective_settings(self, vol: Volume) -> dict[str, Any]:
        return await asyncio.to_thread(self._settings_for, vol)

    def request_refresh(self) -> None:
        """Demande une relecture immédiate de l'inventaire (retrait brutal soupçonné par un flux)."""
        self._on_driver_event("volumes")

    def touch(self, key: str | None) -> None:
        if key:
            self._activity[key] = time.monotonic()

    def touch_storage(self, storage_id: int | None) -> None:
        """Appelé à chaque lecture d'un média externe : réveille le suivi d'inactivité (veille des disques)."""
        if storage_id is None:
            return
        root = self._online.get(storage_id)
        if not root:
            return
        for vol in self._by_key.values():
            if vol.mountpoint == root:
                self._activity[vol.key] = time.monotonic()
                return

    # ------------------------------------------------------------------ vues
    async def status(self) -> dict[str, Any]:
        caps = await self.driver.capabilities()
        return {
            "driver": self.driver.name,
            "capabilities": caps,
            "ready": self._ready,
            "error": self._last_error,
            "hidden_count": len(self._inventory.excluded),
            "free_local_bytes": await asyncio.to_thread(transfer.free_bytes),
        }

    async def list_volumes(self) -> dict[str, Any]:
        from app.database import SessionLocal

        def _libs() -> list[dict[str, Any]]:
            with SessionLocal() as db:
                out = []
                for lib in library.all_libraries(db):
                    out.append({
                        "id": lib.id, "uuid": lib.fs_uuid, "label": lib.label, "nickname": lib.nickname, "fstype": lib.fstype,
                        "size_bytes": lib.size_bytes, "kind": lib.kind, "enabled": lib.enabled,
                        "bytes_written": lib.bytes_written or 0, "last_seen_at": lib.last_seen_at.isoformat() if lib.last_seen_at else None,
                        "health": json.loads(lib.last_health) if lib.last_health else None,
                        "stats": library.stats(db, lib.id), "settings": library.settings_of(db, lib),
                    })
                return out

        libs = await asyncio.to_thread(_libs)
        by_uuid = {l["uuid"].lower(): l for l in libs}
        duplicates = duplicate_uuids(self._inventory.volumes)
        facts = await self.driver.facts()
        views = [await self._view(v, by_uuid.get((v.fs_uuid or "").lower()), duplicates, facts) for v in self._inventory.volumes]
        connected = {(v.fs_uuid or "").lower() for v in self._inventory.volumes}
        for lib in libs:
            if lib["uuid"].lower() not in connected:
                views.append(self._offline_view(lib))
        return {
            "volumes": views,
            "recent_removals": [{"key": r["key"], "name": r["name"], "abrupt": r["abrupt"]} for r in self._recent],
            "hidden_count": len(self._inventory.excluded),
            "encrypted": [{"name": v.display_name, "fstype": v.fstype} for v in self._inventory.encrypted],
        }

    def _offline_view(self, lib: dict[str, Any]) -> dict[str, Any]:
        return {
            "key": "u-" + "".join(c if c.isalnum() or c in "._-" else "_" for c in lib["uuid"].lower()),
            "name": lib["nickname"] or lib["label"] or lib["uuid"], "label": lib["label"], "fstype": lib["fstype"],
            "size_bytes": lib["size_bytes"], "kind": lib["kind"], "connected": False, "state": "offline", "mounted": False,
            "mounted_read_only": None, "uuid_known": True, "portable": False, "transport": None, "vendor": None, "model": None,
            "rotational": None, "usage": None, "can_register": False, "register_block": "not_connected",
            "assessment": fsadvisor.assess_filesystem(lib["fstype"], media=_media_for_kind(lib["kind"])).as_dict(),
            "library": {
                "registered": True, "id": lib["id"], "nickname": lib["nickname"], "online": False, "stats": lib["stats"],
                "bytes_written": lib["bytes_written"], "wear_level": health.write_wear_level(lib["kind"], lib["bytes_written"]),
                "last_seen_at": lib["last_seen_at"], "settings": lib["settings"],
            },
            "health": lib["health"], "longevity": [], "standby": None,
        }

    async def _view(self, vol: Volume, lib: dict[str, Any] | None, duplicates: set[str], facts: dict[str, Any]) -> dict[str, Any]:
        settings = lib["settings"] if lib else await self._effective_settings(vol)
        state = "ejecting" if vol.key in self._ejecting else "busy" if self._busy.get(vol.key) else "mounted" if vol.mounted else "present"
        assessment = fsadvisor.assess_filesystem(vol.fstype, media=_media_for_kind(vol.kind), dirty=vol.key in self._dirty)
        usage = None
        if vol.mountpoint:
            try:
                du = await asyncio.to_thread(shutil.disk_usage, vol.mountpoint)
                usage = {"total_bytes": du.total, "free_bytes": du.free}
            except OSError:
                usage = None
        cached = self._health.get(vol.key)
        smart = cached[1] if cached else (lib["health"] if lib else None)
        report = longevity.report(settings, longevity.Facts(
            mounted=vol.mounted, mounted_read_only=vol.mounted_read_only, mount_options=vol.mount_options,
            rotational=vol.rotational, discard_supported=vol.discard_supported, is_root=bool(facts.get("is_root")),
            fstrim_timer_enabled=facts.get("fstrim_timer_enabled"), standby_supported=bool(facts.get("standby_supported")),
            smart_available=(smart or {}).get("available") if smart else None, smart_reason=(smart or {}).get("reason") if smart else None,
        ))
        block = None
        if not vol.fs_uuid:
            block = "uuid_missing"
        elif vol.fs_uuid.lower() in duplicates:
            block = "uuid_duplicate"
        view = volume_public(vol)
        view.update({
            "connected": True, "state": state, "portable": False, "usage": usage, "assessment": assessment.as_dict(),
            "can_register": block is None and not (lib is not None), "register_block": block,
            "library": None, "health": smart, "longevity": report,
            "standby": self._standby.get(vol.key),
        })
        if lib:
            view["library"] = {
                "registered": True, "id": lib["id"], "nickname": lib["nickname"], "online": lib["id"] in self._online,
                "stats": lib["stats"], "bytes_written": lib["bytes_written"],
                "wear_level": health.write_wear_level(vol.kind, lib["bytes_written"]), "last_seen_at": lib["last_seen_at"],
                "settings": lib["settings"],
            }
        else:
            view["library"] = {"registered": False, "settings": settings,
                               "bytes_written": self._written_unregistered.get(vol.key, 0),
                               "wear_level": health.write_wear_level(vol.kind, self._written_unregistered.get(vol.key, 0))}
        return view

    # ------------------------------------------------------------------ montage, démontage, retrait sûr
    async def _mount_volume(self, vol: Volume, *, writable: bool, settings: dict[str, Any]) -> str:
        options = longevity.mount_options(settings, writable=writable)
        mountpoint: str | None = None
        for attempt in range(MOUNT_SETTLE_TRIES):
            try:
                mountpoint = await self.driver.mount(vol, options)
                break
            except DeviceError as exc:
                if exc.code == "option_not_permitted":
                    mountpoint = await self.driver.mount(vol, ["rw" if writable else "ro"])
                    break
                if exc.code == "unsupported_fs" and attempt + 1 < MOUNT_SETTLE_TRIES:
                    # Support tout juste branché : udisks n'a pas fini d'identifier son système de fichiers.
                    await asyncio.sleep(MOUNT_SETTLE_SECONDS)
                    continue
                if exc.code == "dirty":
                    self._dirty.add(vol.key)
                raise
        assert mountpoint is not None
        self._dirty.discard(vol.key)
        self._log("storage_mounted", f"{vol.display_name} ({'rw' if writable else 'ro'})")
        await self._refresh_soon()
        return mountpoint

    async def _refresh_soon(self) -> None:
        # `refresh` prend le même verrou que l'appelant éventuel : on relit après coup, sans attendre.
        if self._wake is not None:
            self._wake.set()

    async def _sync_now(self) -> None:
        await asyncio.to_thread(os.sync)

    async def _unmount_volume(self, vol: Volume) -> None:
        if self._busy.get(vol.key):
            raise DeviceError("busy", "Un import ou un export utilise ce support : annulez-le ou attendez sa fin.", 409)
        await self._sync_now()
        for attempt in range(UNMOUNT_BUSY_TRIES):
            try:
                await self.driver.unmount(vol)
                return
            except DeviceError as exc:
                # Un indexeur du bureau (vignettes, recherche) garde parfois un support fraîchement monté quelques secondes.
                if exc.code != "busy" or attempt + 1 == UNMOUNT_BUSY_TRIES:
                    raise
                await asyncio.sleep(UNMOUNT_BUSY_SECONDS)

    async def _remount(self, vol: Volume, *, writable: bool, settings: dict[str, Any]) -> str:
        await self._unmount_volume(vol)
        return await self._mount_volume(vol, writable=writable, settings=settings)

    async def mount(self, key: str, mode: str = "ro") -> dict[str, Any]:
        if mode not in ("ro", "rw"):
            raise DeviceError("bad_mode", "Mode de montage inconnu.", 400)
        async with self._lock:
            vol = self._need(key)
            settings = await self._effective_settings(vol)
            writable = mode == "rw"
            if writable:
                assessment = fsadvisor.assess_filesystem(vol.fstype, media=_media_for_kind(vol.kind), dirty=vol.key in self._dirty)
                if not assessment.write_allowed:
                    raise DeviceError("write_refused", "Ce système de fichiers n'est pas fiable en écriture (voir le verdict) : lecture seule uniquement.", 409)
            if vol.mounted and vol.mounted_read_only == (not writable):
                return {"mounted": True, "mode": mode, "changed": False}
            if vol.mounted:
                await self._remount(vol, writable=writable, settings=settings)
            else:
                await self._mount_volume(vol, writable=writable, settings=settings)
            self.touch(key)
        await self.refresh()
        return {"mounted": True, "mode": mode, "changed": True}

    async def unmount(self, key: str) -> dict[str, Any]:
        async with self._lock:
            vol = self._need(key)
            if vol.mounted:
                await self._unmount_volume(vol)
                self._log("storage_unmounted", vol.display_name)
        await self.refresh()
        return {"mounted": False}

    async def eject(self, key: str) -> dict[str, Any]:
        """Retrait sûr : synchronisation, démontage, extinction du support. Aucun import/export en cours."""
        async with self._lock:
            vol = self._need(key)
            if self._busy.get(key):
                raise DeviceError("busy", "Un import ou un export utilise ce support : annulez-le ou attendez sa fin.", 409)
            self._ejecting.add(key)
            try:
                if vol.mounted:
                    await self._unmount_volume(vol)
                powered_off = await self.driver.power_off(vol)
            except DeviceError:
                self._ejecting.discard(key)
                raise
            self._log("storage_ejected", vol.display_name)
        await self.refresh()
        return {"ejected": True, "powered_off": powered_off}

    # ------------------------------------------------------------------ sources (volume ou appareil portable)
    def _source(self, key: str) -> Source:
        if key.startswith("p-"):
            root = self._portable_roots.get(key)
            if not root or not os.path.isdir(root):
                raise DeviceError("not_mounted", "L'appareil n'est pas ouvert : ouvrez-le d'abord.", 409)
            return Source(key, root, True, None, key)
        vol = self._need(key)
        if not vol.mounted or not vol.mountpoint:
            raise DeviceError("not_mounted", "Le support n'est pas monté : ouvrez-le d'abord.", 409)
        return Source(key, vol.mountpoint, False, vol, vol.fs_uuid or key)

    async def browse(self, key: str, path: str | None, offset: int, limit: int, show_hidden: bool, media_only: bool) -> dict[str, Any]:
        from app.database import SessionLocal

        source = self._source(key)
        self.touch(key)
        listing = await asyncio.to_thread(
            paths.list_directory, source.root, path, offset=offset, limit=limit, show_hidden=show_hidden, media_only=media_only
        )

        def _annotate() -> dict[str, dict[str, Any]]:
            if source.volume is None:
                return {}
            with SessionLocal() as db:
                lib = library.get_by_uuid(db, source.volume.fs_uuid)
                if lib is None:
                    return {}
                rels = [f"{listing.path}/{e.name}" if listing.path else e.name for e in listing.entries if e.type == "file"]
                return library.indexed_lookup(db, lib.id, rels)

        indexed = await asyncio.to_thread(_annotate)
        entries = []
        for e in listing.entries:
            rel = f"{listing.path}/{e.name}" if listing.path else e.name
            item = {"name": e.name, "type": e.type, "size": e.size, "mtime": e.mtime, "media": e.media, "hidden": e.hidden, "path": rel}
            item.update(indexed.get(rel, {"indexed": False}) if e.type == "file" else {})
            entries.append(item)
        return {
            "path": listing.path, "parent": listing.parent, "entries": entries, "total": listing.total, "offset": listing.offset,
            "limit": listing.limit, "truncated": listing.truncated, "skipped_links": listing.skipped_links,
            "portable": source.portable,
        }

    # ------------------------------------------------------------------ jobs : import, indexation, export
    def _mark_busy(self, key: str, job_id: str) -> Callable[[], None]:
        self._busy.setdefault(key, set()).add(job_id)

        def release() -> None:
            def _do() -> None:
                jobs = self._busy.get(key)
                if jobs:
                    jobs.discard(job_id)
                    if not jobs:
                        self._busy.pop(key, None)
                self.touch(key)
                self.notify("jobs")

            try:
                if self._loop is None:
                    raise RuntimeError
                self._loop.call_soon_threadsafe(_do)
            except RuntimeError:  # boucle absente ou fermée (arrêt, tests) : on libère directement
                _do()

        return release

    async def start_import(self, key: str, entries: list[dict[str, str]], kind: str, force: bool = False) -> dict[str, Any]:
        from app.database import SessionLocal
        from app.utils.import_jobs import create_job, register_job_future

        source = self._source(key)
        if not entries:
            raise transfer.TransferError("empty_selection", "Aucun élément sélectionné.", 400)

        def _plan() -> transfer.Plan:
            with SessionLocal() as db:
                return transfer.plan_import(source.root, entries, kind, source.source_id, db, force)

        plan = await asyncio.to_thread(_plan)
        if not plan.units:
            return {"job_id": None, "files": 0, "bytes": 0, "skipped": plan.skipped, "truncated": plan.truncated}
        transfer.check_space(plan.total_bytes)
        label = plan.units[0].title if len(plan.units) == 1 else f"{len(plan.units)} éléments"
        job_id = create_job(transfer.JOB_KIND[kind], label, label, source="storage")
        release = self._mark_busy(key, job_id)
        verify_source = not source.portable
        future = transfer.storage_executor.submit(
            transfer.run_import_job, job_id, source.source_id, plan, verify_source=verify_source, resume=verify_source, on_finished=release
        )
        register_job_future(job_id, future)
        self.notify("jobs")
        return {"job_id": job_id, "files": plan.total_files, "units": len(plan.units), "bytes": plan.total_bytes, "skipped": plan.skipped, "truncated": plan.truncated}

    async def start_index(self, key: str, entries: list[dict[str, str]], kind: str) -> dict[str, Any]:
        """« Utiliser comme extension » : enregistre les médias du support en base, sans copie (lecture directe, lecture seule)."""
        from app.database import SessionLocal
        from app.storage import indexer
        from app.utils.import_jobs import create_job, register_job_future

        if key.startswith("p-"):
            raise DeviceError("portable_no_direct", "Un téléphone ou une tablette ne peut pas servir d'extension de stockage (MTP n'est pas fiable pour la lecture directe) : importez les fichiers.", 409)
        source = self._source(key)
        vol = source.volume
        assert vol is not None

        def _lib_id() -> int | None:
            with SessionLocal() as db:
                lib = library.get_by_uuid(db, vol.fs_uuid)
                return lib.id if lib else None

        lib_id = await asyncio.to_thread(_lib_id)
        if lib_id is None:
            raise DeviceError("not_registered", "Enregistrez d'abord ce support comme bibliothèque externe.", 409)
        if not entries:
            raise transfer.TransferError("empty_selection", "Aucun élément sélectionné.", 400)
        plan = await asyncio.to_thread(indexer.plan_index, source.root, entries, kind)
        if not plan.units:
            return {"job_id": None, "files": 0, "skipped": plan.skipped, "truncated": plan.truncated}
        label = plan.units[0].title if len(plan.units) == 1 else f"{len(plan.units)} éléments"
        job_id = create_job(transfer.JOB_KIND[kind], label, label, source="storage")
        release = self._mark_busy(key, job_id)
        future = transfer.storage_executor.submit(indexer.run_index_job, job_id, lib_id, source.root, plan, release)
        register_job_future(job_id, future)
        self.notify("jobs")
        return {"job_id": job_id, "files": plan.total_files, "units": len(plan.units), "skipped": plan.skipped, "truncated": plan.truncated}

    async def start_export(self, key: str, kind: str, ids: list[int], dest: str | None) -> dict[str, Any]:
        """Copie des médias LOCAUX vers le support : écriture temporaire, explicite ; remonte ensuite en lecture seule."""
        from app.database import SessionLocal
        from app.utils.import_jobs import create_job, register_job_future

        if key.startswith("p-"):
            raise DeviceError("read_only_device", "Un appareil portable est en lecture seule : aucune écriture.", 409)
        source = self._source(key)
        vol = source.volume
        assert vol is not None
        assessment = fsadvisor.assess_filesystem(vol.fstype, media=_media_for_kind(vol.kind), dirty=vol.key in self._dirty)
        if not assessment.write_allowed:
            raise DeviceError("write_refused", "Ce système de fichiers n'est pas fiable en écriture : exportez vers un autre support.", 409)
        if not ids:
            raise transfer.TransferError("empty_selection", "Aucun élément sélectionné.", 400)
        paths.clean_rel_path(dest or "Bobine")  # destination hors du support : refusée AVANT toute écriture ou remontage

        def _items() -> list[tuple[str, str]]:
            from app.models import AudioTrack, RadioTrack, Video

            with SessionLocal() as db:
                model = {"video": Video, "audio": AudioTrack, "radio": RadioTrack}.get(kind)
                if model is None:
                    raise transfer.TransferError("bad_kind", "Nature d'export inconnue.", 400)
                rows = db.query(model).filter(model.id.in_(ids)).all()
                out = []
                for row in rows:
                    if row.storage_id is not None or not os.path.isfile(row.file_path):
                        continue  # seuls les médias locaux existants s'exportent
                    out.append((row.file_path, paths.safe_dest_name(f"{row.title}{os.path.splitext(row.file_path)[1].lower()}")))
                return out

        items = await asyncio.to_thread(_items)
        if not items:
            raise transfer.TransferError("nothing_to_export", "Aucun média local à exporter dans cette sélection.", 400)
        total = sum(os.path.getsize(p) for p, _ in items)
        free = (await asyncio.to_thread(shutil.disk_usage, source.root)).free
        if free < int(total * 1.02) + 16 * 1024 * 1024:
            raise transfer.TransferError("insufficient_space", "Espace libre insuffisant sur le support.", 409, needed_bytes=total, free_bytes=free)

        settings = await self._effective_settings(vol)
        was_ro = vol.mounted_read_only is not False
        job_id = create_job(kind, f"{len(items)} fichier(s) vers le support", "Export", source="storage")
        async with self._lock:
            try:
                await self._remount(vol, writable=True, settings=settings)
            except DeviceError:
                from app.utils.import_jobs import cancel_job

                cancel_job(job_id)
                raise
            self._rw_lease.add(key)
            release = self._mark_busy(key, job_id)  # occupé dès que le support est en écriture : ni retrait ni démontage
        await self.refresh()
        refreshed = self._by_key.get(key)
        root = (refreshed.mountpoint if refreshed else None) or source.root
        loop = self._loop
        assert loop is not None

        def _after() -> None:
            async def finish() -> None:
                async with self._lock:
                    self._rw_lease.discard(key)
                    self._busy.get(key, set()).discard(job_id)
                    current = self._by_key.get(key)
                    if current is not None and current.mounted:
                        try:
                            await self._sync_now()
                            if was_ro or settings.get("read_only"):
                                await self._remount(current, writable=False, settings=settings)
                        except DeviceError as exc:
                            logger.info("Retour en lecture seule impossible : %s", exc.message)
                    if not self._busy.get(key):
                        self._busy.pop(key, None)
                self.notify("jobs")
                await self.refresh()

            asyncio.run_coroutine_threadsafe(finish(), loop)

        def run() -> None:
            self._run_export(job_id, key, vol, root, dest, items, total)

        def wrapper() -> None:
            try:
                run()
            finally:
                _after()

        future = transfer.storage_executor.submit(wrapper)
        register_job_future(job_id, future)
        self.notify("jobs")
        return {"job_id": job_id, "files": len(items), "bytes": total}

    def _run_export(self, job_id: str, key: str, vol: Volume, root: str, dest: str | None, items: list[tuple[str, str]], total: int) -> None:
        from app.database import SessionLocal
        from app.utils.import_jobs import JobCancelledError, is_job_cancelled, update_job

        written = {"n": 0}
        summary: dict[str, Any] = {"exported": 0, "failed": [], "bytes": 0}
        update_job(job_id, stage="copying", bytes_total=total, bytes_done=0, files_total=len(items), files_done=0)

        def bump(n: int) -> None:
            written["n"] += n
            update_job(job_id, bytes_done=written["n"], progress_percent=round(100.0 * written["n"] / max(1, total), 1))

        try:
            target = paths.ensure_dir_within(root, dest or "Bobine")
            for index, (src, name) in enumerate(items):
                if is_job_cancelled(job_id):
                    raise JobCancelledError(job_id)
                update_job(job_id, current_file=name, files_done=index)
                try:
                    result = transfer.export_file(src, target, name, is_cancelled=lambda: is_job_cancelled(job_id), on_bytes=bump)
                    summary["exported"] += 1
                    summary["bytes"] += result["size"]
                except transfer.Cancelled:
                    raise JobCancelledError(job_id)
                except transfer.TransferError as exc:
                    summary["failed"].append({"path": name, "code": exc.code, "message": exc.message})
                    if exc.code in ("dest_io",):
                        break
            if summary["bytes"]:
                with SessionLocal() as db:
                    lib = library.get_by_uuid(db, vol.fs_uuid)
                    if lib is not None:
                        library.add_bytes_written(db, lib.id, summary["bytes"])
                    else:
                        self._written_unregistered[key] = self._written_unregistered.get(key, 0) + summary["bytes"]
            if summary["exported"] == 0 and summary["failed"]:
                update_job(job_id, stage="error", error=summary["failed"][0]["message"], details=summary)
            else:
                update_job(job_id, stage="done", details=summary, files_done=len(items), progress_percent=100.0)
        except JobCancelledError:
            update_job(job_id, stage="cancelled", details=summary)
        except transfer.TransferError as exc:
            update_job(job_id, stage="error", error=exc.message, details=summary)
        except Exception as exc:
            logger.warning("Export vers un support : %s", exc, exc_info=True)
            update_job(job_id, stage="error", error=str(exc), details=summary)

    # ------------------------------------------------------------------ bibliothèque externe
    async def register_library(self, key: str, nickname: str | None = None) -> dict[str, Any]:
        from app.database import SessionLocal

        async with self._lock:
            vol = self._need(key)
            if not vol.fs_uuid:
                raise DeviceError("uuid_missing", "Ce support n'a pas d'identifiant de système de fichiers (UUID) : il peut servir à importer, pas d'extension permanente.", 409)
            if vol.fs_uuid.lower() in duplicate_uuids(self._inventory.volumes):
                raise DeviceError("uuid_duplicate", "Deux supports branchés portent le même identifiant (copie ou clone) : débranchez l'un des deux.", 409)

            def _register() -> dict[str, Any]:
                with SessionLocal() as db:
                    lib = library.register(db, vol, nickname)
                    return {"id": lib.id, "settings": library.settings_of(db, lib)}

            info = await asyncio.to_thread(_register)
            settings = info["settings"]
            if settings.get("read_only") and vol.mounted and vol.mounted_read_only is False and vol.dev_type != "loop":
                await self._attempt(self._remount(vol, writable=False, settings=settings))
            elif not vol.mounted:
                await self._attempt(self._mount_volume(vol, writable=False, settings=settings))
            self._log("storage_library_registered", vol.display_name)
        await self.refresh()
        await self._sync_libraries()
        return {"registered": True, "library_id": info["id"]}

    async def unregister_library(self, key: str, purge: bool) -> dict[str, Any]:
        from app.database import SessionLocal

        def _target() -> dict[str, Any] | None:
            with SessionLocal() as db:
                for lib in library.all_libraries(db):
                    vol = self._by_key.get(key)
                    expected = vol.fs_uuid.lower() if vol and vol.fs_uuid else None
                    offline_key = "u-" + "".join(c if c.isalnum() or c in "._-" else "_" for c in lib.fs_uuid.lower())
                    if (expected and lib.fs_uuid.lower() == expected) or offline_key == key:
                        return {"id": lib.id, "stats": library.stats(db, lib.id), "label": lib.label}
            return None

        target = await asyncio.to_thread(_target)
        if target is None:
            raise DeviceError("not_registered", "Ce support n'est pas une bibliothèque enregistrée.", 404)
        stats = target["stats"]
        if not purge and (stats["videos"] or stats["audio_tracks"] or stats["radio_tracks"]):
            raise DeviceError("has_media", "Des médias de ce support sont indexés : confirmez leur retrait de la bibliothèque (les fichiers du support ne sont jamais supprimés).", 409)

        def _delete() -> dict[str, int]:
            from app.models import ExternalVolume

            with SessionLocal() as db:
                removed = library.purge_index(db, target["id"])
                db.query(ExternalVolume).filter(ExternalVolume.id == target["id"]).delete()
                db.commit()
                return removed

        removed = await asyncio.to_thread(_delete)
        self._online.pop(target["id"], None)
        availability.set_online(dict(self._online))
        self._log("storage_library_removed", target["label"])
        from app.utils.ws_manager import manager as ws_manager

        ws_manager.broadcast_threadsafe({"event": "library_change", "reason": "storage_availability"})
        self.notify("library", ["library_removed"])
        return {"removed": removed}

    async def update_settings(self, key: str | None, values: dict[str, Any]) -> dict[str, Any]:
        """Réglages de longévité : d'un support enregistré, ou les valeurs par défaut globales (`key=None`)."""
        from app.database import SessionLocal
        from app.models import ExternalVolume

        def _save() -> dict[str, Any]:
            with SessionLocal() as db:
                if key is None:
                    return library.save_global_defaults(db, values)
                vol = self._by_key.get(key)
                lib = library.get_by_uuid(db, vol.fs_uuid) if vol else None
                if lib is None:
                    for cand in library.all_libraries(db):
                        if "u-" + "".join(c if c.isalnum() or c in "._-" else "_" for c in cand.fs_uuid.lower()) == key:
                            lib = cand
                if lib is None:
                    raise DeviceError("not_registered", "Les réglages propres à un support exigent de l'enregistrer comme bibliothèque ; sinon modifiez les réglages par défaut.", 409)
                merged = longevity.normalize_settings(values, base=library.settings_of(db, lib))
                lib.settings = json.dumps({k: merged[k] for k in longevity.DEFAULTS})
                db.commit()
                return merged

        merged = await asyncio.to_thread(_save)
        self.notify("settings")
        await self._wake_refresh()
        return merged

    async def _wake_refresh(self) -> None:
        if self._wake is not None:
            self._wake.set()

    # ------------------------------------------------------------------ santé, TRIM
    async def health(self, key: str, refresh: bool = False) -> dict[str, Any]:
        vol = self._need(key)
        cached = self._health.get(key)
        if cached and not refresh and time.monotonic() - cached[0] < HEALTH_TTL:
            report = cached[1]
        else:
            report = await self.driver.smart(vol)
            self._health[key] = (time.monotonic(), report)
            self._health_last_run[key] = time.monotonic()
            await self._persist_health(vol, report)
        wear = "ok"
        written = 0
        from app.database import SessionLocal

        def _written() -> int:
            with SessionLocal() as db:
                lib = library.get_by_uuid(db, vol.fs_uuid)
                return (lib.bytes_written or 0) if lib else self._written_unregistered.get(key, 0)

        written = await asyncio.to_thread(_written)
        wear = health.write_wear_level(vol.kind, written)
        return {**report, "bytes_written": written, "write_wear": wear, "overall": health.combine_status(report.get("status", "unknown"), wear)}

    async def _persist_health(self, vol: Volume, report: dict[str, Any]) -> None:
        from app.database import SessionLocal

        def _save() -> None:
            with SessionLocal() as db:
                lib = library.get_by_uuid(db, vol.fs_uuid)
                if lib is not None:
                    lib.last_health = json.dumps(report)
                    db.commit()

        await asyncio.to_thread(_save)

    async def trim(self, key: str) -> dict[str, str]:
        vol = self._need(key)
        out = await self.driver.trim(vol)
        self._log("storage_trim", vol.display_name)
        return {"result": out}

    # ------------------------------------------------------------------ maintenance : santé périodique, veille
    async def _maintenance(self) -> None:
        now = time.monotonic()
        if now - self._last_maintenance < 30:
            return
        self._last_maintenance = now
        facts = await self.driver.facts()
        for key, vol in list(self._by_key.items()):
            if not vol.mounted:
                continue
            settings = await self._effective_settings(vol)
            # Santé SMART périodique (silencieuse) : seulement si le réglage est actif et que le système le permet.
            if settings.get("smart_monitor") and now - self._health_last_run.get(key, -HEALTH_PERIOD) >= HEALTH_PERIOD:
                self._health_last_run[key] = now
                before = (self._health.get(key) or (0, {}))[1].get("status")
                report = await self.driver.smart(vol)
                self._health[key] = (now, report)
                await self._persist_health(vol, report)
                if report.get("available") and report.get("status") in ("warning", "critical") and report.get("status") != before:
                    self._log("storage_health_warning", f"{vol.display_name} : {', '.join(report.get('warnings', []))}")
                    self.notify("health", ["health_warning"])
            # Veille des disques rotatifs : long délai d'inactivité, jamais agressif.
            minutes = int(settings.get("standby_minutes") or 0)
            if vol.rotational is True and minutes and facts.get("standby_supported") and not self._busy.get(key):
                last = self._activity.get(key, now - 0.0)
                self._activity.setdefault(key, now)
                state = self._standby.get(key)
                if now - last >= minutes * 60 and (state is None or (state.get("ok") is False and now - state.get("mono", 0) >= STANDBY_RETRY) or last > state.get("mono", 0)):
                    try:
                        method = await self.driver.standby(vol)
                        self._standby[key] = {"ok": True, "method": method, "at": datetime.now(timezone.utc).isoformat(), "mono": now}
                    except DeviceError as exc:
                        self._standby[key] = {"ok": False, "error": exc.message, "at": datetime.now(timezone.utc).isoformat(), "mono": now}

    # ------------------------------------------------------------------ appareils portables
    async def portable(self) -> dict[str, Any]:
        status = await self.driver.portable_status()
        for dev in status.get("devices", []):
            if dev.get("state") == "mounted" and dev["id"] not in self._portable_roots:
                dev["state"] = "ready"  # monté ailleurs : on le rouvre pour obtenir la racine
        return status

    async def portable_mount(self, device_id: str) -> dict[str, Any]:
        result = await self.driver.portable_mount(device_id)
        self._portable_roots[device_id] = result["root"]
        self.notify("portable")
        return {"id": device_id, "mounted": True}

    async def portable_unmount(self, device_id: str) -> dict[str, Any]:
        self._portable_roots.pop(device_id, None)
        await self.driver.portable_unmount(device_id)
        self.notify("portable")
        return {"mounted": False}

    # ------------------------------------------------------------------ outils pour les tests
    def volume(self, key: str) -> Volume | None:
        return self._by_key.get(key)

    def online_map(self) -> dict[int, str]:
        return dict(self._online)


service = StorageService()
