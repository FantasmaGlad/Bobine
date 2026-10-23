"""Bonnes pratiques de longévité des supports, configurées automatiquement MAIS visibles et désactivables.

Chaque réglage est décrit par un état : `applied` (réellement actif), `inactive` (réglage activé, pas
encore applicable : support non monté...), `disabled` (désactivé par l'utilisateur), `unavailable` (la
plateforme, les droits ou le matériel ne le permettent pas ; la raison est fournie). Rien n'est
présenté comme appliqué s'il ne l'est pas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULTS: dict[str, Any] = {
    "read_only": True,        # usage extension : zéro écriture
    "noatime": True,          # pas d'écriture de date d'accès à chaque lecture
    "noexec": True,           # Bobine n'exécute jamais rien depuis un support
    "standby_minutes": 20,    # veille d'un disque rotatif après inactivité (0 = jamais) ; long, non agressif
    "smart_monitor": True,    # relevé de santé périodique quand le système le permet
    "auto_mount_library": True,  # remonte seul une bibliothèque enregistrée au rebranchement
}
BOOL_KEYS = ("read_only", "noatime", "noexec", "smart_monitor", "auto_mount_library")
STANDBY_MIN, STANDBY_MAX = 0, 240

# Options refusées par conception : jamais demandées (sync = écritures amplifiées, discard continu = usure).
FORBIDDEN_OPTIONS = frozenset({"sync", "dirsync", "discard", "flush"})


def normalize_settings(raw: dict[str, Any] | None, base: dict[str, Any] | None = None) -> dict[str, Any]:
    """Valide et complète les réglages : types stricts, bornes, clés inconnues ignorées."""
    out = dict(DEFAULTS)
    if base:
        out.update({k: v for k, v in base.items() if k in DEFAULTS})
    for key, value in (raw or {}).items():
        if key in BOOL_KEYS and isinstance(value, bool):
            out[key] = value
        elif key == "standby_minutes" and isinstance(value, int) and not isinstance(value, bool):
            out[key] = max(STANDBY_MIN, min(STANDBY_MAX, value))
    return out


def mount_options(settings: dict[str, Any], *, writable: bool) -> list[str]:
    """Options passées à `udisksctl mount -o` : lecture seule par défaut, aucune option interdite."""
    options = ["rw" if writable else "ro"]
    if settings.get("noatime", True):
        options += ["noatime", "nodiratime"]
    if settings.get("noexec", True):
        options.append("noexec")
    return [o for o in options if o not in FORBIDDEN_OPTIONS]


@dataclass(frozen=True)
class Facts:
    """Faits mesurés sur le support et la machine, fournis par le pilote (aucune E/S ici)."""

    mounted: bool
    mounted_read_only: bool | None
    mount_options: tuple[str, ...]
    rotational: bool | None
    discard_supported: bool
    is_root: bool
    fstrim_timer_enabled: bool | None
    standby_supported: bool
    smart_available: bool | None
    smart_reason: str | None


def report(settings: dict[str, Any], f: Facts) -> list[dict[str, Any]]:
    """État honnête de chaque réglage de longévité (voir l'en-tête du module)."""
    items: list[dict[str, Any]] = []

    def add(item_id: str, enabled: bool, status: str, reason: str | None = None) -> None:
        items.append({"id": item_id, "enabled": enabled, "status": status, "reason": reason})

    def simple(item_id: str, key: str, applied: bool) -> None:
        enabled = bool(settings.get(key))
        if not enabled:
            add(item_id, False, "disabled")
        elif not f.mounted:
            add(item_id, True, "inactive", "not_mounted")
        else:
            add(item_id, True, "applied" if applied else "inactive", None if applied else "mounted_without_option")

    simple("read_only", "read_only", f.mounted_read_only is True)
    simple("noatime", "noatime", "noatime" in f.mount_options)
    simple("noexec", "noexec", "noexec" in f.mount_options)

    # Arrêt propre : toujours appliqué par la procédure de retrait (non désactivable : c'est de la sécurité des données).
    add("safe_eject", True, "applied")

    # TRIM : exécuter fstrim exige root ; sans lui, on lit l'état du minuteur système.
    if not f.discard_supported:
        add("trim", False, "unavailable", "no_discard_support")
    elif f.is_root:
        add("trim", True, "applied", "manual_fstrim")
    elif f.fstrim_timer_enabled:
        add("trim", True, "applied", "system_timer")
    elif f.fstrim_timer_enabled is False:
        add("trim", False, "unavailable", "needs_root_timer_disabled")
    else:
        add("trim", False, "unavailable", "needs_root")

    # Veille : disques rotatifs seulement.
    minutes = int(settings.get("standby_minutes") or 0)
    if f.rotational is not True:
        add("standby", False, "unavailable", "not_rotational")
    elif not minutes:
        add("standby", False, "disabled")
    elif not f.standby_supported:
        add("standby", True, "unavailable", "standby_not_permitted")
    else:
        add("standby", True, "applied" if f.mounted else "inactive", None if f.mounted else "not_mounted")

    if not settings.get("smart_monitor"):
        add("smart", False, "disabled")
    elif f.smart_available:
        add("smart", True, "applied")
    else:
        add("smart", True, "unavailable", f.smart_reason or "no_smart")
    return items
