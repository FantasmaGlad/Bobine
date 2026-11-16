"""Traduction des erreurs udisks2 et D-Bus en erreurs du pilote de stockage."""

from __future__ import annotations

import logging
from ..base import DeviceError


logger = logging.getLogger(__name__)


def _stderr(text: str) -> str:
    return text.strip().splitlines()[-1] if text.strip() else ""


def classify_udisks_error(message: str) -> tuple[str, int, str]:
    """(code stable, statut HTTP, message lisible) d'une erreur `udisksctl`."""
    low = message.lower()
    if "optionnotpermitted" in low or "is not allowed" in low:
        return "option_not_permitted", 400, "Le système refuse une option de montage demandée."
    if "notauthorized" in low or "not authorized" in low or "authentication" in low:
        return "not_authorized", 403, "Le système refuse cette opération (autorisation polkit manquante pour ce compte)."
    if "target is busy" in low or "device or resource busy" in low or "busy" in low:
        return "busy", 409, "Le support est en cours d'utilisation : arrêtez la lecture ou l'import, puis réessayez."
    if any(w in low for w in ("unclean", "hibernated", "dirty", "inconsistent", "wrong fs type", "bad superblock", "mount failed: unknown")):
        return "dirty", 409, "Le système de fichiers semble endommagé ou n'a pas été fermé proprement : réparez-le (fsck, ou le brancher sur Windows/macOS) avant de l'utiliser."
    if "not a mountable filesystem" in low or "unknown filesystem" in low or "no filesystem" in low:
        return "unsupported_fs", 400, "Ce système de fichiers n'est pas pris en charge par le système."
    if "notmounted" in low or "not mounted" in low:
        return "not_mounted", 409, "Le support n'est pas monté."
    if "no such" in low or "not found" in low or "no object" in low:
        return "device_removed", 404, "Le support a été retiré."
    return "mount_failed", 502, "Le système n'a pas pu exécuter cette opération."


def classify_dbus_error(name: str, message: str) -> DeviceError:
    """Erreur D-Bus de udisks2 -> erreur structurée (le texte brut, qui contient des chemins système, reste dans le journal)."""
    logger.info("udisks2 : %s %s", name, message)
    low = (name + " " + message).lower()
    if "notauthorized" in low or "not authorized" in low or "authentication" in low:
        return DeviceError("format_not_authorized", "Le système refuse cette opération (autorisation polkit manquante pour ce compte).", 403)
    if "devicebusy" in low or "busy" in low:
        return DeviceError("format_busy_mounted", "Le support est encore utilisé par un autre programme : fermez-le puis recommencez.", 409)
    if "notsupported" in low or "not supported" in low or "no such" in low and "program" in low:
        return DeviceError("format_tool_missing", "Un composant du système manque pour formater (outil de ce format).", 501)
    if "optionnotpermitted" in low:
        return DeviceError("option_not_permitted", "Le système refuse une option de formatage.", 400)
    return DeviceError("format_failed", "Le système n'a pas pu exécuter le formatage.", 502)
