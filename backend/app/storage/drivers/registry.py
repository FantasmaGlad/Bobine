"""Choix du pilote de stockage selon le profil de déploiement (même logique que `app/devices/registry.py`)."""

from __future__ import annotations

import logging

from app.utils.deployment import get_deployment_profile

from .base import NullStorageDriver, StorageDriver

logger = logging.getLogger(__name__)

_PLANNED = {
    "windows": "Le stockage externe sous Windows (lettres de lecteur, retrait sûr, appareils WPD) est prévu dans une phase ultérieure.",
    "macos": "Le stockage externe sous macOS (diskutil, /Volumes) est prévu dans une phase ultérieure.",
    "android": "Sous Android, le stockage externe (USB OTG, Storage Access Framework, lecture seule) est prévu dans une phase ultérieure.",
}


def build_storage_driver(profile: str | None = None) -> StorageDriver:
    """Linux (bureau et appliance) → lsblk + udisks2 ; les autres profils reçoivent un pilote nul explicite."""
    profile = profile or get_deployment_profile()
    try:
        if profile in ("linux-desktop", "linux-headless"):
            from .linux import LinuxStorageDriver

            return LinuxStorageDriver()
    except Exception as exc:  # un pilote défaillant n'empêche jamais le démarrage
        logger.warning("Pilote de stockage indisponible (%s) : %s", profile, exc)
        return NullStorageDriver(f"Le pilote de stockage de ce profil ({profile}) n'a pas pu démarrer.")
    return NullStorageDriver(_PLANNED.get(profile, "Le stockage externe n'est pas disponible sur cette plateforme."))
