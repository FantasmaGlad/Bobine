"""Choix du pilote de périphériques selon le profil de déploiement."""

from __future__ import annotations

import logging

from app.utils.deployment import get_deployment_profile

from .base import DeviceDriver, NullDriver

logger = logging.getLogger(__name__)


def build_driver(profile: str | None = None) -> DeviceDriver:
    """Linux (bureau et appliance) → D-Bus/PipeWire/NetworkManager ; Windows/macOS → sidecar Rust ;
    Android → pont Kotlin. Un profil dont le pilote est indisponible reçoit un `NullDriver` explicite."""
    profile = profile or get_deployment_profile()
    try:
        if profile in ("linux-desktop", "linux-headless"):
            from .linux import LinuxDriver

            return LinuxDriver()
        if profile in ("windows", "macos"):
            from .sidecar import SidecarDriver

            return SidecarDriver(profile)
        if profile == "android":
            from .android import AndroidDriver

            return AndroidDriver()
    except Exception as exc:  # un pilote défaillant ne doit jamais empêcher l'application de démarrer
        logger.warning("Pilote de périphériques indisponible (%s) : %s", profile, exc)
        return NullDriver(f"Le pilote de périphériques de ce profil ({profile}) n'a pas pu démarrer.")
    return NullDriver()
