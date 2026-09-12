"""Résolution universelle multi-OS du binaire ffmpeg/ffprobe à invoquer.

Prise en charge déterministe pour l'ensemble des 5 profils d'exécution :
1. Android ARM64 (Chaquopy) : variables d'environnement explicites
   `BOBINE_FFMPEG_BIN` / `BOBINE_FFPROBE_BIN` pointant vers `libffmpeg.so`
   et `libffprobe.so` dans le dossier natif `nativeLibraryDir`.
2. Windows Desktop (.exe, PyInstaller) : recherche prioritaire des binaires
   `ffmpeg.exe` et `ffprobe.exe` bundlés directement à côté de `BobineBackend.exe`.
3. macOS Desktop (.dmg, Apple Silicon / Intel) : résolution de `PATH` avec replis
   explicites sur `/opt/homebrew/bin` et `/usr/local/bin` (indispensable pour les
   applications lancées via Finder / launchd sans variable PATH shell).
4. Linux Bureau (.deb) & Appliance Headless (Wyse 5070) : résolution standard via
   `shutil.which` et repli sur `/usr/bin`.
"""

import os
import shutil
import sys
from pathlib import Path


def _resolve_binary(env_var: str, binary_name: str) -> str:
    # 1. Variable d'environnement explicite (Android Chaquopy, conteneurs)
    env_val = os.environ.get(env_var, "").strip()
    if env_val and os.path.exists(env_val):
        return env_val

    # 2. Présence dans le dossier de l'exécutable (Windows PyInstaller bundle)
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        for candidate in (exe_dir / binary_name, exe_dir / f"{binary_name}.exe"):
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)

    # 3. Résolution dynamique via le PATH système
    which_path = shutil.which(binary_name)
    if which_path:
        return which_path

    # 4. Chemins standards d'installation multi-OS (Homebrew macOS, Linux système)
    system_candidates = [
        Path("/opt/homebrew/bin") / binary_name,
        Path("/usr/local/bin") / binary_name,
        Path("/usr/bin") / binary_name,
    ]
    for sc in system_candidates:
        if sc.is_file() and os.access(sc, os.X_OK):
            return str(sc)

    # 5. Repli par défaut sur le nom nu
    return binary_name


FFMPEG_BIN = _resolve_binary("BOBINE_FFMPEG_BIN", "ffmpeg")
FFPROBE_BIN = _resolve_binary("BOBINE_FFPROBE_BIN", "ffprobe")
