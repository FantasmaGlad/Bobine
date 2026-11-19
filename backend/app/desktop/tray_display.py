"""Écrans au lancement : kiosque, projecteur, mise en veille empêchée pendant la projection."""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request
import webbrowser

from app.desktop import system
from app.desktop.chromium import OFFLINE_FLAGS
from app.desktop.displays import REPORT_REFRESH_SECONDS, DisplayOrchestrator, DisplayWatcher
from app.desktop.monitors import external_monitors, list_monitors
from app.desktop.projector import ProjectorWindow

from .tray_supervisor import is_backend_running
from .tray_urls import _admin_url, _display_state_url, _grid_url, _kiosk_url, _projector_url

logger = logging.getLogger(__name__)


def launch_kiosk_browser(url: str | None = None) -> None:
    """Lance le navigateur en mode kiosque optionnel."""
    target_url = url or _kiosk_url()
    kiosk_args = ["--kiosk", "--autoplay-policy=no-user-gesture-required", *OFFLINE_FLAGS, target_url]
    if not system.current().launch_kiosk(target_url, kiosk_args):
        webbrowser.open(target_url)


def _get_wired_display_mode() -> str:
    try:
        req = urllib.request.Request(f"{_admin_url()}/api/settings", headers={"User-Agent": "BobineTray"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("wired_display_mode", "headless")
    except Exception as exc:
        logger.debug("Mode des écrans filaires illisible, sans écran retenu : %s", exc)
        return "headless"


def _open_initial_displays(timeout_seconds: float = 20.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if is_backend_running():
            has_external = bool(external_monitors(list_monitors()))
            mode = _get_wired_display_mode()
            logger.info(
                f"Backend prêt — mode d'affichage câblé : {mode}, écran externe détecté : {has_external}"
            )
            if has_external or mode == "dual_screen":
                webbrowser.open(_grid_url() if mode == "dual_screen" else _admin_url())
                if not has_external and mode == "dual_screen":
                    logger.info("Mode double écran sans écran externe : en attente d'un projecteur")
            else:
                logger.info("Mode autonome (aucun écran externe) : Administration + Kiosque")
                webbrowser.open(_admin_url())
                launch_kiosk_browser(_kiosk_url())
            return
        time.sleep(0.5)
    logger.warning("Délai d'attente du backend dépassé — ouverture par défaut")
    webbrowser.open(_admin_url())
    launch_kiosk_browser(_kiosk_url())


def _keep_awake_while_projecting(process) -> None:
    system.current().keep_awake_while(process)


def _start_displays() -> tuple[DisplayOrchestrator, DisplayWatcher]:
    orchestrator = DisplayOrchestrator(
        _display_state_url,
        ProjectorWindow(_projector_url, after_launch=_keep_awake_while_projecting),
        ready_check=is_backend_running,
    )
    watcher = DisplayWatcher(orchestrator.handle_change)
    watcher.start()

    def refresh_loop() -> None:
        while True:
            time.sleep(REPORT_REFRESH_SECONDS)
            orchestrator.refresh_report()

    threading.Thread(target=refresh_loop, daemon=True, name="bobine-display-refresh").start()
    return orchestrator, watcher
