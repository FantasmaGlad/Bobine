"""Écrans au lancement : kiosque, projecteur, mise en veille empêchée pendant la projection."""

from __future__ import annotations

import json
import logging
import platform
import shutil
import subprocess
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from app.desktop.chromium import OFFLINE_FLAGS
from app.desktop.displays import REPORT_REFRESH_SECONDS, DisplayOrchestrator, DisplayWatcher
from app.desktop.monitors import external_monitors, list_monitors
from app.desktop.projector import ProjectorWindow, find_kiosk_browser

from .tray_supervisor import is_backend_running
from .tray_urls import _admin_url, _display_state_url, _grid_url, _kiosk_url, _projector_url

logger = logging.getLogger(__name__)


def _set_display_always_on(enabled: bool) -> None:
    system = platform.system()
    if system == "Windows":
        import ctypes
        ES_CONTINUOUS = 0x80000000
        ES_DISPLAY_REQUIRED = 0x00000002
        ES_SYSTEM_REQUIRED = 0x00000001
        flags = ES_CONTINUOUS | (ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED if enabled else 0)
        ctypes.windll.kernel32.SetThreadExecutionState(flags)  # type: ignore[attr-defined]
    elif system == "Linux":
        if shutil.which("xset"):
            try:
                if enabled:
                    subprocess.run(["xset", "s", "off", "-dpms"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                else:
                    subprocess.run(["xset", "s", "default", "+dpms"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            except Exception as exc:
                logger.debug("_set_display_always_on : %s", exc)


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


def launch_kiosk_browser(url: str | None = None) -> None:
    """Lance le navigateur en mode kiosque optionnel."""
    target_url = url or _kiosk_url()
    system = platform.system()
    kiosk_args = ["--kiosk", "--autoplay-policy=no-user-gesture-required", *OFFLINE_FLAGS, target_url]

    if system in ("Windows", "Linux"):
        browser = find_kiosk_browser(system)
        if browser:
            _set_display_always_on(True)
            subprocess.Popen([browser, *kiosk_args])
            return
        firefox = shutil.which("firefox") if system == "Linux" else None
        if firefox:
            _set_display_always_on(True)
            subprocess.Popen([firefox, "--kiosk", target_url])
            return

    elif system == "Darwin":
        for app_name, process_name in (
            ("Google Chrome", "Google Chrome"),
            ("Chromium", "Chromium"),
        ):
            app_path = Path("/Applications") / f"{app_name}.app"
            if app_path.exists():
                subprocess.Popen(["open", "-na", str(app_path), "--args", *kiosk_args])
                threading.Thread(
                    target=_caffeinate_after_launch, args=(process_name,), daemon=True,
                ).start()
                return

    webbrowser.open(target_url)


def _get_wired_display_mode() -> str:
    try:
        req = urllib.request.Request(f"{_admin_url()}/api/settings", headers={"User-Agent": "BobineTray"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("wired_display_mode", "headless")
    except Exception:
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
    if platform.system() == "Darwin" and shutil.which("caffeinate"):
        subprocess.Popen(["caffeinate", "-d", "-i", "-w", str(process.pid)])
    elif platform.system() in ("Windows", "Linux"):
        _set_display_always_on(True)


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
