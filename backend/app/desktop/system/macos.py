import logging
import os
import plistlib
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from .common import first_existing
from .other import BACKEND_CREATIONFLAGS, FIREWALL_HINT

__all__ = [
    "BACKEND_CREATIONFLAGS", "FIREWALL_HINT", "SOURCE_LABEL", "ensure_desktop_shortcut", "ensure_launch_agent",
    "find_kiosk_browser", "find_native_projector", "keep_awake_while", "launch_kiosk", "list_monitors",
    "set_display_always_on",
]

logger = logging.getLogger(__name__)

SOURCE_LABEL = "macos"
LAUNCH_AGENT_LABEL = "com.bobine.app"
_KIOSK_APPS = (("Google Chrome", "Google Chrome"), ("Chromium", "Chromium"))


def set_display_always_on(enabled: bool) -> None:
    return None


def keep_awake_while(process) -> None:
    if shutil.which("caffeinate"):
        subprocess.Popen(["caffeinate", "-d", "-i", "-w", str(process.pid)])


def _caffeinate_after_launch(process_name: str, timeout_seconds: float = 5.0) -> None:
    import psutil

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        for proc in psutil.process_iter(["pid", "name"]):
            if proc.info.get("name") == process_name:
                subprocess.Popen(["caffeinate", "-d", "-i", "-w", str(proc.info["pid"])])
                return
        time.sleep(0.3)
    logger.warning(f"caffeinate non attaché : process '{process_name}' introuvable après {timeout_seconds}s")


def launch_kiosk(target_url: str, kiosk_args: list[str]) -> bool:
    for app_name, process_name in _KIOSK_APPS:
        app_path = Path("/Applications") / f"{app_name}.app"
        if app_path.exists():
            subprocess.Popen(["open", "-na", str(app_path), "--args", *kiosk_args])
            threading.Thread(target=_caffeinate_after_launch, args=(process_name,), daemon=True).start()
            return True
    return False


def list_monitors() -> list:
    from app.desktop.monitors import parse_macos_displays

    result = subprocess.run(
        ["system_profiler", "SPDisplaysDataType", "-json"], capture_output=True, text=True, timeout=15, check=False,
    )
    return parse_macos_displays(result.stdout)


def find_kiosk_browser(which, exists, environ) -> str | None:
    return None


def find_native_projector(executable: str, exists) -> str | None:
    exe_dir = Path(executable).parent
    return first_existing((exe_dir / "bobine-projector", exe_dir.parent / "Resources" / "bobine-projector"), exists)


def _launch_agent_is_current(agent_path: Path, tray_exe: str) -> bool:
    if not agent_path.exists():
        return False
    try:
        with open(agent_path, "rb") as f:
            existing = plistlib.load(f)
        if existing.get("ProgramArguments") == [tray_exe]:
            return True
        logger.info(f"LaunchAgent obsolète (chemin enregistré différent de {tray_exe}) — réparation.")
    except Exception:
        logger.warning("LaunchAgent illisible/corrompu — réécriture.")
    return False


def _write_launch_agent(agent_path: Path, tray_exe: str) -> None:
    log_dir = Path.home() / "Library" / "Logs" / "Bobine"
    log_dir.mkdir(parents=True, exist_ok=True)
    agent_path.parent.mkdir(parents=True, exist_ok=True)
    with open(agent_path, "wb") as f:
        plistlib.dump(
            {
                "Label": LAUNCH_AGENT_LABEL,
                "ProgramArguments": [tray_exe],
                "RunAtLoad": True,
                "KeepAlive": {"SuccessfulExit": False},
                "ProcessType": "Interactive",
                "StandardOutPath": str(log_dir / "BobineTray.out.log"),
                "StandardErrorPath": str(log_dir / "BobineTray.err.log"),
            },
            f,
        )


def ensure_launch_agent() -> None:
    if not getattr(sys, "frozen", False):
        return
    tray_exe = str(Path(sys.executable).resolve())
    agent_path = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"
    if _launch_agent_is_current(agent_path, tray_exe):
        return
    try:
        _write_launch_agent(agent_path, tray_exe)
        for command in (
            ["launchctl", "bootout", f"gui/{os.getuid()}/{LAUNCH_AGENT_LABEL}"],
            ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(agent_path)],
        ):
            subprocess.run(command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        logger.info(f"LaunchAgent installé et activé : {agent_path} -> {tray_exe}")
    except Exception as e:
        logger.warning(f"Échec de l'installation du LaunchAgent macOS (lancement automatique désactivé) : {e!r}")


def ensure_desktop_shortcut() -> None:
    if not getattr(sys, "frozen", False):
        return
    app_path = Path(sys.executable).resolve().parent.parent
    if app_path.suffix != ".app":
        return
    desktop_dir = Path.home() / "Desktop"
    if not desktop_dir.is_dir():
        return
    dest = desktop_dir / app_path.name
    if dest.exists():
        return
    try:
        os.symlink(str(app_path), str(dest))
        logger.info(f"Raccourci Bureau macOS créé : {dest} -> {app_path}")
    except Exception as exc:
        logger.debug("_ensure_desktop_shortcut : %s", exc)
