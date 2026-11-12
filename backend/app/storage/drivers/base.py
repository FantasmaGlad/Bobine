"""Interface commune des pilotes de stockage externe."""
from __future__ import annotations

import logging

from abc import ABC, abstractmethod
from typing import Any, Callable

from app.devices.base import DeviceError
from app.storage.health import unavailable
from app.storage.formatting.model import DiskInfo, FormatSpec
from app.storage.types import Inventory, Volume

logger = logging.getLogger(__name__)

ChangeCallback = Callable[[str], None]

CAPABILITY_KEYS = (
    "inventory",
    "push_events",
    "mount",
    "eject",
    "smart",
    "trim",
    "standby",
    "portable",
    "format",
)

__all__ = ["StorageDriver", "NullStorageDriver", "DeviceError", "CAPABILITY_KEYS", "unavailable"]


class StorageDriver(ABC):
    name: str = "none"

    def __init__(self) -> None:
        self._on_change: ChangeCallback | None = None

    def set_change_callback(self, callback: ChangeCallback | None) -> None:
        self._on_change = callback

    def _emit(self, scope: str = "volumes") -> None:
        if self._on_change is not None:
            try:
                self._on_change(scope)
            except Exception as exc:
                logger.debug("_emit : %s", exc)

    async def start(self) -> None:  # pragma: no cover - crochet optionnel
        """Démarre les ressources longues (abonnement D-Bus...)."""

    async def stop(self) -> None:  # pragma: no cover - crochet optionnel
        """Libère les ressources longues."""

    @abstractmethod
    async def capabilities(self) -> dict[str, dict[str, Any]]:
        """`{clé: {"supported": bool, "reason"?: str}}` pour chaque clé de CAPABILITY_KEYS."""

    @abstractmethod
    async def inventory(self, protected_paths: list[str]) -> Inventory:
        """Supports branchés (déjà débarrassés des disques système et des données de Bobine)."""

    async def mount(self, volume: Volume, options: list[str]) -> str:
        raise DeviceError("unsupported", "Le montage de supports n'est pas possible sur cette plateforme.", 501)

    async def unmount(self, volume: Volume) -> None:
        raise DeviceError("unsupported", "Le démontage n'est pas possible sur cette plateforme.", 501)

    async def power_off(self, volume: Volume) -> bool:
        """Éteint le support après démontage."""
        return False

    async def smart(self, volume: Volume) -> dict[str, Any]:
        return unavailable("no_smart", "La santé du support n'est pas lisible sur cette plateforme.")

    async def standby(self, volume: Volume) -> str:
        raise DeviceError("unsupported", "La mise en veille n'est pas pilotable sur cette plateforme.", 501)

    async def trim(self, volume: Volume) -> str:
        raise DeviceError("unsupported", "TRIM n'est pas disponible sur cette plateforme.", 501)

    async def facts(self) -> dict[str, Any]:
        """Faits machine pour le rapport de longévité (root, minuteur TRIM...)."""
        return {"is_root": False, "fstrim_timer_enabled": None, "standby_supported": False}

    async def disks(self) -> list[DiskInfo]:
        """Disques entiers avec partitions, relus à chaque appel (jamais un cache)."""
        return []

    async def format_support(self) -> dict[str, Any]:
        """`{"supported": bool, "reason": str|None, "tools": {système de fichiers: outil présent}}`."""
        return {"supported": False, "reason": "Le formatage n'est pas pris en charge sur cette plateforme.", "tools": {}}

    async def unmount_device(self, device_path: str) -> None:
        raise DeviceError("unsupported", "Le démontage n'est pas possible sur cette plateforme.", 501)

    async def create_partition_table(self, disk: DiskInfo) -> None:
        raise DeviceError("unsupported", "Le formatage n'est pas possible sur cette plateforme.", 501)

    async def create_partition_and_format(self, disk: DiskInfo, spec: FormatSpec) -> str:
        """Crée la partition alignée et son système de fichiers ; renvoie le chemin du nouveau périphérique."""
        raise DeviceError("unsupported", "Le formatage n'est pas possible sur cette plateforme.", 501)

    async def wipe_disk(self, disk: DiskInfo) -> None:
        """Retire les signatures (table de partitions comprise) : retour à un support vierge après un échec."""
        raise DeviceError("unsupported", "Le formatage n'est pas possible sur cette plateforme.", 501)

    async def portable_status(self) -> dict[str, Any]:
        return {"supported": False, "reason": "Les appareils portables ne sont pas pris en charge sur cette plateforme.", "devices": []}

    async def portable_mount(self, device_id: str) -> dict[str, Any]:
        raise DeviceError("unsupported", "Les appareils portables ne sont pas pris en charge sur cette plateforme.", 501)

    async def portable_unmount(self, device_id: str) -> None:
        raise DeviceError("unsupported", "Les appareils portables ne sont pas pris en charge sur cette plateforme.", 501)

    def portable_root(self, device_id: str) -> str | None:
        """Racine lisible (point FUSE) d'un appareil portable monté, sinon None."""
        return None


class NullStorageDriver(StorageDriver):
    """Plateforme dont le pilote n'est pas encore livré : tout est « non disponible », avec la raison."""

    name = "none"

    def __init__(self, reason: str = "Le stockage externe n'est pas encore disponible sur cette plateforme.") -> None:
        super().__init__()
        self.reason = reason

    async def capabilities(self) -> dict[str, dict[str, Any]]:
        return {key: {"supported": False, "reason": self.reason} for key in CAPABILITY_KEYS}

    async def inventory(self, protected_paths: list[str]) -> Inventory:
        return Inventory()

    async def portable_status(self) -> dict[str, Any]:
        return {"supported": False, "reason": self.reason, "devices": []}
