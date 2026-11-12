"""État matériel des écrans externes et mode d'affichage câblé EFFECTIF."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

VALID_DISPLAY_MODE_SETTINGS = ("auto", "dual_screen", "headless")
DEFAULT_DISPLAY_MODE_SETTING = "auto"
VALID_SOURCES = ("android", "windows", "macos", "linux", "wyse", "manual")


@dataclass
class DisplayHardwareState:
    """Dernier rapport matériel reçu (None = aucun rapport depuis le démarrage)."""

    external_count: int | None = None
    source: str | None = None
    resolution: str | None = None
    updated_at: float | None = field(default=None)


_state = DisplayHardwareState()


def get_hardware_state() -> DisplayHardwareState:
    return _state


def reset_hardware_state() -> None:
    """Remet à zéro le rapport (tests)."""
    global _state
    _state = DisplayHardwareState()


def effective_wired_display_mode(setting: str, external_count: int | None, default: str = "headless") -> str:
    """Mode d'affichage câblé effectif."""
    if setting in ("dual_screen", "headless"):
        return setting
    if external_count is None:
        return default
    return "dual_screen" if external_count > 0 else "headless"


def report_external_displays(count: int, source: str | None, resolution: str | None = None) -> bool:
    """Enregistre un rapport matériel."""
    global _state
    count = max(0, int(count))
    changed = _state.external_count != count
    _state = DisplayHardwareState(
        external_count=count,
        source=source if source in VALID_SOURCES else (source or None),
        resolution=resolution,
        updated_at=time.time(),
    )
    return changed
