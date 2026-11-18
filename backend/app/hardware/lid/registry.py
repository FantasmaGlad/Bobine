from types import ModuleType

from ..platforms import detected
from . import linux, macos, windows


def _implementation() -> ModuleType:
    platforms = detected()
    if "windows" in platforms:
        return windows
    if "macos" in platforms:
        return macos
    return linux


def has_lid() -> bool:
    return _implementation().has_lid()


def prevent_sleep() -> bool:
    return _implementation().prevent_sleep()


def set_prevent_sleep(prevent: bool) -> bool:
    return _implementation().set_prevent_sleep(prevent)
