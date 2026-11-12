"""Résolution universelle multi-OS du binaire ffmpeg/ffprobe à invoquer."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from app.utils.android_runtime import is_android


def _resolve_binary(env_var: str, binary_name: str) -> str:
    env_val = os.environ.get(env_var, "").strip()
    if env_val and os.path.exists(env_val):
        return env_val

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        for candidate in (exe_dir / binary_name, exe_dir / f"{binary_name}.exe"):
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)

    which_path = shutil.which(binary_name)
    if which_path:
        return which_path

    system_candidates = [
        Path("/opt/homebrew/bin") / binary_name,
        Path("/usr/local/bin") / binary_name,
        Path("/usr/bin") / binary_name,
    ]
    for sc in system_candidates:
        if sc.is_file() and os.access(sc, os.X_OK):
            return str(sc)

    return binary_name


FFMPEG_BIN = _resolve_binary("BOBINE_FFMPEG_BIN", "ffmpeg")
FFPROBE_BIN = _resolve_binary("BOBINE_FFPROBE_BIN", "ffprobe")


def os_key() -> str:
    """Système courant sous l'une des quatre clés utilisées par les messages d'aide : « macos », « windows », « linux », « android »."""
    if is_android():
        return "android"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("win"):
        return "windows"
    return "linux"


def with_nostdin(cmd: list[str]) -> list[str]:
    """`cmd` (ffmpeg) avec `-nostdin` juste après le binaire ; idempotent."""
    if len(cmd) > 1 and cmd[1] == "-nostdin":
        return list(cmd)
    return [cmd[0], "-nostdin", *cmd[1:]]


def media_subprocess_env() -> dict[str, str] | None:
    """Environnement des sous-processus ffmpeg/ffprobe."""
    if not getattr(sys, "frozen", False):
        return None
    from app.updates.orchestrator import clean_subprocess_env

    return clean_subprocess_env()


def media_subprocess_kwargs() -> dict:
    """Arguments `subprocess` communs à tous les appels ffmpeg/ffprobe : entrée standard fermée (jamais de lecture bloquante sur le terminal du parent) et environnement assaini dans un build figé."""
    kwargs: dict = {"stdin": subprocess.DEVNULL}
    env = media_subprocess_env()
    if env is not None:
        kwargs["env"] = env
    return kwargs


_INSTALL_HINTS = {
    "macos": "Installez-le avec Homebrew (brew install ffmpeg), puis relancez Bobine.",
    "windows": "Réinstallez Bobine : ffmpeg est normalement fourni avec l'application.",
    "linux": "Installez-le avec votre gestionnaire de paquets (sudo apt install ffmpeg), puis relancez Bobine.",
    "android": "Ce composant est fourni avec l'application : réinstallez Bobine.",
}

_MISSING_TOOL_RE = re.compile(r"^(ffmpeg|ffprobe) est introuvable")


class MediaToolMissingError(ValueError):
    """ffmpeg ou ffprobe est introuvable ou non exécutable."""

    def __init__(self, tool: str, detail: str = ""):
        self.tool = tool
        self.os_key = os_key()
        message = (
            f"{tool} est introuvable : Bobine en a besoin pour analyser et convertir les vidéos. "
            f"{_INSTALL_HINTS[self.os_key]}"
        )
        if detail:
            message += f" ({detail})"
        super().__init__(message)


def is_missing_tool_error(err: BaseException) -> bool:
    """Vrai pour l'échec de LANCEMENT d'un binaire (absent, non exécutable) ; faux pour un binaire qui démarre puis échoue (fichier corrompu, etc.)."""
    return isinstance(err, (FileNotFoundError, PermissionError))


def missing_tool_error(tool: str, err: BaseException | None = None) -> MediaToolMissingError:
    detail = f"{type(err).__name__}: {err}" if err is not None else ""
    return MediaToolMissingError(tool, detail)


def classify_error(message: str | None) -> tuple[str, dict] | None:
    """(code, paramètres) d'un message d'erreur d'import reconnu, ou None."""
    match = _MISSING_TOOL_RE.match(message or "")
    if match:
        return "media_tool_missing", {"tool": match.group(1), "os": os_key()}
    return None


def probe_tool(bin_path: str) -> dict:
    """État d'un binaire pour le diagnostic : chemin résolu, présence, exécutabilité, version."""
    info: dict = {"path": bin_path, "found": False, "executable": False, "version": None, "error": None}
    try:
        resolved = bin_path if os.path.isabs(bin_path) else shutil.which(bin_path)
        if not resolved or not os.path.exists(resolved):
            info["error"] = "introuvable"
            return info
        info["path"] = resolved
        info["found"] = True
        info["executable"] = os.access(resolved, os.X_OK)
        if not info["executable"]:
            info["error"] = "non exécutable"
            return info
        kwargs = media_subprocess_kwargs()
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        res = subprocess.run([resolved, "-version"], capture_output=True, text=True, timeout=5, **kwargs)
        first = (res.stdout or "").splitlines()[0] if res.stdout else ""
        info["version"] = first[:120] or None
        if res.returncode != 0:
            info["error"] = f"code de sortie {res.returncode}"
    except subprocess.TimeoutExpired:
        info["error"] = "délai dépassé (5 s)"
    except Exception as e:  # noqa: BLE001 — diagnostic : jamais d'exception vers l'API
        info["error"] = f"{type(e).__name__}: {e}"
    return info
