"""Système hôte : clé d'OS, ouverture de dossier, console, ressources figées, noms de fichiers réservés."""
from .registry import (
    bundle_resources,
    display_name,
    open_folder,
    os_key,
    platform_id,
    prepare_console,
    rejects_windows_names,
)

__all__ = [
    "bundle_resources", "display_name", "open_folder", "os_key", "platform_id", "prepare_console", "rejects_windows_names",
]
