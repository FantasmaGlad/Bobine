"""Bibliothèques enregistrées sur un support et leurs réglages."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.devices.base import DeviceError
from app.storage import availability, library, longevity
from app.storage.lsblk import duplicate_uuids
from app.storage.types import uuid_key


class LibraryMixin:
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
                    offline_key = uuid_key(lib.fs_uuid)
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

        def _save() -> dict[str, Any]:
            with SessionLocal() as db:
                if key is None:
                    return library.save_global_defaults(db, values)
                vol = self._by_key.get(key)
                lib = library.get_by_uuid(db, vol.fs_uuid) if vol else None
                if lib is None:
                    for cand in library.all_libraries(db):
                        if uuid_key(cand.fs_uuid) == key:
                            lib = cand
                if lib is None:
                    raise DeviceError("not_registered", "Les réglages propres à un support exigent de l'enregistrer comme bibliothèque ; sinon modifiez les réglages par défaut.", 409)
                merged = longevity.normalize_settings(values, base=library.settings_of(db, lib))
                lib.settings = json.dumps({k: merged[k] for k in longevity.DEFAULTS})
                db.commit()
                return merged

        merged = await asyncio.to_thread(_save)
        self.notify("settings")
        await self._refresh_soon()
        return merged
