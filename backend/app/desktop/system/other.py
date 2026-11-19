from pathlib import Path

from .common import first_existing, projector_candidates

SOURCE_LABEL = "linux"
FIREWALL_HINT = True
BACKEND_CREATIONFLAGS = 0
PROJECTOR_BINARY = "bobine-projector"


def set_display_always_on(enabled: bool) -> None:
    return None


def keep_awake_while(process) -> None:
    return None


def launch_kiosk(target_url: str, kiosk_args: list[str]) -> bool:
    return False


def list_monitors() -> list:
    return []


def find_kiosk_browser(which, exists, environ) -> str | None:
    return None


def find_native_projector(executable: str, exists) -> str | None:
    exe_dir = Path(executable).parent
    return first_existing(projector_candidates(exe_dir, PROJECTOR_BINARY), exists)


def ensure_launch_agent() -> None:
    return None


def ensure_desktop_shortcut() -> None:
    return None
