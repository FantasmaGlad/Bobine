import os
import platform
import sys
from pathlib import Path
from types import ModuleType

from app.utils.android_runtime import is_android

from . import linux, macos, other, windows


def platform_id() -> str:
    """Identifiant brut du système (`sys.platform`), pour les tables indexées par système."""
    return sys.platform


def _current() -> ModuleType:
    if sys.platform.startswith("linux"):
        return linux
    if sys.platform == "darwin":
        return macos
    if sys.platform.startswith("win"):
        return windows
    return other


def os_key() -> str:
    """« android », « macos », « windows » ou « linux », la clé des messages d'aide."""
    return "android" if is_android() else _current().KEY


def display_name() -> str:
    return "Android" if is_android() else platform.system()


def open_folder(path: str) -> None:
    """Ouvre un dossier dans le gestionnaire de fichiers du bureau ; sans effet sur un système inconnu."""
    _current().open_folder(path)


def prepare_console() -> None:
    _current().prepare_console()


def bundle_resources(executable: Path) -> Path:
    """Dossier des ressources d'une application figée (`Contents/Resources` d'un paquet macOS)."""
    return _current().bundle_resources(executable)


def rejects_windows_names() -> bool:
    return os.name == "nt"
