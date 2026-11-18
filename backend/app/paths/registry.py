import platform
import sys
from pathlib import Path

from app.utils.android_runtime import is_android

from . import android, linux, macos, windows

_SYSTEMS = {"Windows": "windows", "Darwin": "macos", "Linux": "linux"}


def _system() -> str:
    return _SYSTEMS.get(platform.system(), "other")


def install_root(source_dir: Path) -> Path:
    """Dossier des ressources : à côté de l'exécutable figé (`Resources` du paquet macOS), sinon le dossier du backend."""
    if not getattr(sys, "frozen", False):
        return source_dir
    executable_dir = Path(sys.executable).resolve().parent
    return macos.bundle_root(executable_dir) if _system() == "macos" else executable_dir


def data_root(root_dir: Path) -> Path:
    """Dossier des données de la plateforme, sinon le dossier d'installation."""
    if is_android():
        return android.data_root() or root_dir
    system = _system()
    if system == "linux":
        return linux.data_root(root_dir) or root_dir
    implementation = {"windows": windows, "macos": macos}.get(system)
    return (implementation.data_root() if implementation else None) or root_dir


def global_config_path() -> Path:
    """Fichier de configuration globale de la plateforme, sinon `/etc/bobine/config.toml`."""
    system = _system()
    if system == "linux" and is_android():
        system = "android"
    implementation = {"windows": windows, "macos": macos, "linux": linux, "android": android}.get(system)
    return (implementation.global_config_path() if implementation else None) or Path("/etc/bobine/config.toml")
