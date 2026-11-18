from typing import Any, Callable

from ..platforms import detected
from ..probe import _HARDWARE_CACHE, shutil_which
from . import android, dmidecode, linux, macos, windows
from .common import probe
from .fields import FIELDS, Found


def _incomplete(found: Found) -> bool:
    return not all(found.get(f) for f in FIELDS)


def _sources() -> list[tuple[Callable[[Found], bool], Callable[[], Found]]]:
    platforms = detected()
    return [
        (lambda found: "android" in platforms, android.read),
        (lambda found: not found.get("brand") and "linux" in platforms and bool(shutil_which("udevadm")), linux.read),
        (lambda found: _incomplete(found) and bool(shutil_which("dmidecode")), dmidecode.read),
        (lambda found: "windows" in platforms and _incomplete(found), windows.read),
        (lambda found: "macos" in platforms and _incomplete(found), macos.read),
    ]


def get_ram_info() -> dict[str, Any]:
    """Retourne les informations matérielles détaillées de la mémoire vive."""
    if _HARDWARE_CACHE.get("ram_info"):
        return _HARDWARE_CACHE["ram_info"]
    found: Found = {}
    for wanted, source in _sources():
        if wanted(found):
            extra = probe(source) or {}
            found = {**{k: v for k, v in extra.items() if v}, **{k: v for k, v in found.items() if v}}
    parts = [found[f] for f in FIELDS if found.get(f)]
    result = {
        "brand": found.get("brand") or None,
        "type": found.get("type") or None,
        "freq": found.get("freq") or None,
        "model_label": " ".join(parts) if parts else "RAM Système",
    }
    _HARDWARE_CACHE["ram_info"] = result
    return result
