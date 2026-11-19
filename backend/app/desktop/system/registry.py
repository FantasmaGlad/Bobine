import platform
from types import ModuleType

from . import linux, macos, other, windows

_BY_NAME = {"Linux": linux, "Windows": windows, "Darwin": macos}


def system_name() -> str:
    return platform.system()


def for_name(name: str) -> ModuleType:
    """Implémentation du bureau pour un nom de `platform.system()` ; repli sans effet pour un système inconnu."""
    return _BY_NAME.get(name, other)


def current() -> ModuleType:
    return for_name(system_name())
