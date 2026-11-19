import logging
import shutil
import subprocess
from pathlib import Path

from .other import (
    BACKEND_CREATIONFLAGS,
    FIREWALL_HINT,
    ensure_launch_agent,
    find_native_projector,
)

__all__ = [
    "BACKEND_CREATIONFLAGS", "FIREWALL_HINT", "SOURCE_LABEL", "ensure_desktop_shortcut", "ensure_launch_agent",
    "find_kiosk_browser", "find_native_projector", "keep_awake_while", "launch_kiosk", "list_monitors",
    "set_display_always_on",
]

logger = logging.getLogger(__name__)

SOURCE_LABEL = "linux"
_KIOSK_BROWSERS = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "brave-browser", "msedge")


def set_display_always_on(enabled: bool) -> None:
    if not shutil.which("xset"):
        return
    arguments = ["s", "off", "-dpms"] if enabled else ["s", "default", "+dpms"]
    try:
        subprocess.run(["xset", *arguments], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
    except Exception as exc:
        logger.debug("_set_display_always_on : %s", exc)


def keep_awake_while(process) -> None:
    set_display_always_on(True)


def launch_kiosk(target_url: str, kiosk_args: list[str]) -> bool:
    browser = find_kiosk_browser(shutil.which, None, None)
    if browser:
        set_display_always_on(True)
        subprocess.Popen([browser, *kiosk_args])
        return True
    firefox = shutil.which("firefox")
    if firefox:
        set_display_always_on(True)
        subprocess.Popen([firefox, "--kiosk", target_url])
        return True
    return False


def list_monitors() -> list:
    from app.desktop.monitors import parse_xrandr_listmonitors

    xrandr = shutil.which("xrandr")
    if not xrandr:
        return []
    result = subprocess.run([xrandr, "--listmonitors"], capture_output=True, text=True, timeout=5, check=False)
    return parse_xrandr_listmonitors(result.stdout)


def find_kiosk_browser(which, exists, environ) -> str | None:
    for candidate in _KIOSK_BROWSERS:
        found = which(candidate)
        if found:
            return found
    return None


def ensure_desktop_shortcut() -> None:
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
