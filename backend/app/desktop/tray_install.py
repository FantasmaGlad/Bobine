"""Intégration au système : agent de lancement macOS, raccourci de bureau."""

from __future__ import annotations

import logging
import os
import platform
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


_LAUNCH_AGENT_LABEL = "com.bobine.app"


def _ensure_launch_agent_macos() -> None:
    if platform.system() != "Darwin" or not getattr(sys, "frozen", False):
        return

    tray_exe = str(Path(sys.executable).resolve())
    agent_path = Path.home() / "Library" / "LaunchAgents" / f"{_LAUNCH_AGENT_LABEL}.plist"

    if agent_path.exists():
        try:
            with open(agent_path, "rb") as f:
                existing = plistlib.load(f)
            if existing.get("ProgramArguments") == [tray_exe]:
                return
            logger.info(f"LaunchAgent obsolète (chemin enregistré différent de {tray_exe}) — réparation.")
        except Exception:
            logger.warning("LaunchAgent illisible/corrompu — réécriture.")

    try:
        log_dir = Path.home() / "Library" / "Logs" / "Bobine"
        log_dir.mkdir(parents=True, exist_ok=True)

        agent_path.parent.mkdir(parents=True, exist_ok=True)
        with open(agent_path, "wb") as f:
            plistlib.dump(
                {
                    "Label": _LAUNCH_AGENT_LABEL,
                    "ProgramArguments": [tray_exe],
                    "RunAtLoad": True,
                    "KeepAlive": {"SuccessfulExit": False},
                    "ProcessType": "Interactive",
                    "StandardOutPath": str(log_dir / "BobineTray.out.log"),
                    "StandardErrorPath": str(log_dir / "BobineTray.err.log"),
                },
                f,
            )

        subprocess.run(
            ["launchctl", "bootout", f"gui/{os.getuid()}/{_LAUNCH_AGENT_LABEL}"],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
        )
        subprocess.run(
            ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(agent_path)],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
        )
        logger.info(f"LaunchAgent installé et activé : {agent_path} -> {tray_exe}")
    except Exception as e:
        logger.warning(f"Échec de l'installation du LaunchAgent macOS (lancement automatique désactivé) : {e!r}")


def _ensure_desktop_shortcut() -> None:
    system = platform.system()
    try:
        if system == "Linux":
            desktop_src = Path("/usr/share/applications/bobine.desktop")
            if not desktop_src.exists():
                return
            for dname in ("Desktop", "Bureau"):
                target_dir = Path.home() / dname
                if target_dir.is_dir():
                    dest = target_dir / "bobine.desktop"
                    if not dest.exists():
                        shutil.copyfile(desktop_src, dest)
                        dest.chmod(0o755)
                        if shutil.which("gio"):
                            subprocess.run(
                                ["gio", "set", str(dest), "metadata::trusted", "true"],
                                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
                            )
                        logger.info(f"Raccourci Bureau Linux créé : {dest}")
                    break
        elif system == "Darwin" and getattr(sys, "frozen", False):
            app_path = Path(sys.executable).resolve().parent.parent
            if app_path.suffix == ".app":
                desktop_dir = Path.home() / "Desktop"
                if desktop_dir.is_dir():
                    dest = desktop_dir / app_path.name
                    if not dest.exists():
                        try:
                            os.symlink(str(app_path), str(dest))
                            logger.info(f"Raccourci Bureau macOS créé : {dest} -> {app_path}")
                        except Exception as exc:
                            logger.debug("_ensure_desktop_shortcut : %s", exc)
    except Exception as e:
        logger.debug(f"Vérification du raccourci Bureau ignorée : {e!r}")
