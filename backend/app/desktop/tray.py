"""Point d'entrée du plateau de Bobine (bureau Windows, macOS, Linux)."""

from __future__ import annotations

import logging
import sys
import threading
import webbrowser

import pystray

from .tray_display import _open_initial_displays, _start_displays
from .tray_icon import _load_icon_image
from .tray_install import _ensure_desktop_shortcut, _ensure_launch_agent_macos
from .tray_menu import _build_menu
from .tray_supervisor import BackendSupervisor, _acquire_single_instance_lock, _backend_command, is_backend_running
from .tray_updates import _port_fallback_notice, _update_poll_loop, _update_status_poll_loop
from .tray_urls import _admin_url

logger = logging.getLogger(__name__)


def _background(target, name: str, *args) -> None:
    threading.Thread(target=target, args=args, daemon=True, name=name).start()


def run() -> None:
    """Point d'entrée — `python -m app.desktop.tray` en développement, et l'exécutable `BobineTray.exe` une fois empaqueté."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if is_backend_running():
        logger.info("Bobine est déjà actif en arrière-plan. Ouverture de l'interface web.")
        webbrowser.open(_admin_url())
        return
    if not _acquire_single_instance_lock():
        logger.info("Une autre instance de BobineTray supervise déjà le démarrage du backend "
                    "— ouverture de l'interface web sans lancer de doublon.")
        webbrowser.open(_admin_url())
        return
    _ensure_launch_agent_macos()
    _ensure_desktop_shortcut()
    supervisor = BackendSupervisor(_backend_command())
    supervisor.start()
    if "--startup" not in sys.argv and "--minimized" not in sys.argv:
        _background(_open_initial_displays, "bobine-open-displays")
    _background(_update_poll_loop, "bobine-tray-update-check")
    orchestrator, watcher = _start_displays()
    icon = pystray.Icon("bobine", _load_icon_image(), "Bobine", menu=_build_menu(supervisor, orchestrator, watcher))
    _background(_port_fallback_notice, "bobine-tray-port-notice", icon)
    _background(_update_status_poll_loop, "bobine-tray-update-status", icon)
    icon.run()


if __name__ == "__main__":
    run()
