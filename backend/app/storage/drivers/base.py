"""Interface commune des pilotes de stockage externe.

Un pilote par plateforme (Linux : `linux.py` ; Windows, macOS, Android : `NullStorageDriver` explicite
tant que leur phase n'est pas livrée). Le service (`app/storage/service.py`) et le routeur ne connaissent
que cette interface. Règles d'or, identiques à celles des périphériques :

* un pilote DÉCLARE ses capacités : l'interface n'affiche que ce que l'OS permet ;
* aucune erreur d'OS ne remonte en exception brute : `DeviceError` (code stable + message lisible) ou
  rapport `unavailable(...)`, jamais une 500 ;
* le pilote ne reçoit que des `Volume` issus de SON inventaire courant : jamais de chemin du client.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

from app.devices.base import DeviceError  # même forme d'erreur structurée que l'API des périphériques
from app.storage.health import unavailable
from app.storage.types import Inventory, Volume

ChangeCallback = Callable[[str], None]

CAPABILITY_KEYS = (
    "inventory",     # lister les supports branchés
    "push_events",   # évènements poussés (sinon interrogation périodique)
    "mount",         # monter sans privilèges
    "eject",         # retrait sûr (sync + démontage + extinction)
    "smart",         # santé SMART
    "trim",          # TRIM déclenché par Bobine
    "standby",       # mise en veille des disques rotatifs
    "portable",      # téléphones, tablettes (MTP/PTP/AFC)
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
            except Exception:  # un abonné fautif ne casse jamais le pilote
                pass

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
        """Éteint le support après démontage. Faux si non applicable (image disque, carte SD sans alimentation pilotable)."""
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

    # --- appareils portables (téléphones, tablettes) -------------------------------------------------------
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
