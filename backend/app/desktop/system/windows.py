import logging
import shutil
import subprocess
from pathlib import Path, PureWindowsPath

from .common import first_existing, projector_candidates
from .other import ensure_desktop_shortcut, ensure_launch_agent

__all__ = [
    "BACKEND_CREATIONFLAGS", "FIREWALL_HINT", "SOURCE_LABEL", "ensure_desktop_shortcut", "ensure_launch_agent",
    "find_kiosk_browser", "find_native_projector", "keep_awake_while", "launch_kiosk", "list_monitors",
    "set_display_always_on",
]

logger = logging.getLogger(__name__)

SOURCE_LABEL = "windows"
FIREWALL_HINT = False
BACKEND_CREATIONFLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
ES_CONTINUOUS = 0x80000000
ES_DISPLAY_REQUIRED = 0x00000002
ES_SYSTEM_REQUIRED = 0x00000001
_BROWSER_PATHS = (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe")


def set_display_always_on(enabled: bool) -> None:
    import ctypes

    flags = ES_CONTINUOUS | (ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED if enabled else 0)
    ctypes.windll.kernel32.SetThreadExecutionState(flags)  # type: ignore[attr-defined]


def keep_awake_while(process) -> None:
    set_display_always_on(True)


def launch_kiosk(target_url: str, kiosk_args: list[str]) -> bool:
    import os

    browser = find_kiosk_browser(shutil.which, os.path.exists, os.environ)
    if not browser:
        return False
    set_display_always_on(True)
    subprocess.Popen([browser, *kiosk_args])
    return True


def list_monitors() -> list:
    from .windows_monitors import enumerate_monitors

    return enumerate_monitors()


def find_kiosk_browser(which, exists, environ) -> str | None:
    found = which("msedge")
    if found:
        return found
    for base_var in ("ProgramFiles(x86)", "ProgramFiles", "LocalAppData"):
        base = environ.get(base_var)
        if not base:
            continue
        for relative in _BROWSER_PATHS:
            candidate = str(Path(base) / relative)
            if exists(candidate):
                return candidate
    return which("chrome")


def find_native_projector(executable: str, exists) -> str | None:
    exe_dir = PureWindowsPath(executable).parent
    return first_existing(projector_candidates(exe_dir, "bobine-projector.exe"), exists)
