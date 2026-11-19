"""Fenêtre projecteur plein écran : navigateur de kiosque ou projecteur natif sur un écran donné."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Callable
from app.desktop import system as desktop_system
from app.desktop.chromium import OFFLINE_FLAGS
from .display_report import _resolve_url
from .monitors import Monitor

logger = logging.getLogger(__name__)


def find_kiosk_browser(
    system: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
    exists: Callable[[str], bool] = os.path.exists,
    environ: dict | None = None,
) -> str | None:
    """Navigateur Chromium utilisable en kiosque (pur, testable)."""
    environ = os.environ if environ is None else environ
    return desktop_system.for_name(system or desktop_system.system_name()).find_kiosk_browser(which, exists, environ)


def find_native_projector(
    system: str | None = None,
    environ: dict | None = None,
    executable: str | None = None,
    exists: Callable[[str], bool] = os.path.exists,
) -> str | None:
    """Fenêtre native `bobine-projector` : Remplace le navigateur piloté (WKWebView sur macOS, WebView2 sur Windows, WebKitGTK sur Linux) pour éliminer les conflits de positionnement multi-écrans."""
    environ = os.environ if environ is None else environ
    override = environ.get("BOBINE_PROJECTOR_BIN")
    if override and exists(override):
        return override
    implementation = desktop_system.for_name(system or desktop_system.system_name())
    return implementation.find_native_projector(executable or sys.executable, exists)


def build_native_projector_command(binary: str, url: str, monitor: str = "external") -> list[str]:
    """Ligne de commande de la fenêtre native : elle choisit elle-même l'écran externe (les positions ne sont pas exposées par `system_profiler`)."""
    return [binary, "--url", url, "--monitor", monitor]


def build_projector_command(
    browser: str,
    url: str,
    monitor: Monitor,
    profile_dir: str,
    *,
    wayland: bool = False,
) -> list[str]:
    """Ligne de commande du navigateur kiosque positionné sur `monitor` (pur)."""
    command = [
        browser,
        f"--user-data-dir={profile_dir}",
        "--new-window",
        f"--window-position={monitor.x},{monitor.y}",
        f"--window-size={monitor.width},{monitor.height}",
        "--start-fullscreen",
        "--kiosk",
        "--autoplay-policy=no-user-gesture-required",
        "--no-first-run",
        "--no-default-browser-check",
        "--noerrdialogs",
        "--disable-infobars",
        "--disable-session-crashed-bubble",
        "--disable-pinch",
        "--overscroll-history-navigation=0",
        "--check-for-update-interval=31536000",
        *OFFLINE_FLAGS,
    ]
    if wayland:
        command.append("--ozone-platform=x11")
    command.append(url)
    return command


class ProjectorWindow:
    """Cycle de vie de la fenêtre kiosque sur le moniteur externe."""

    def __init__(
        self,
        url: "str | Callable[[], str]",
        browser_finder: Callable[[], str | None] = find_kiosk_browser,
        popen: Callable[..., "subprocess.Popen"] = subprocess.Popen,
        profile_factory: Callable[[], str] = lambda: tempfile.mkdtemp(prefix="bobine-projector-"),
        native_finder: Callable[[], str | None] = find_native_projector,
        after_launch: Callable[["subprocess.Popen"], None] | None = None,
    ) -> None:
        self._url = url
        self._native_finder = native_finder
        self._after_launch = after_launch
        self._browser_finder = browser_finder
        self._popen = popen
        self._profile_factory = profile_factory
        self._process = None
        self._profile_dir: str | None = None
        self._monitor: Monitor | None = None

    @property
    def is_open(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def monitor(self) -> Monitor | None:
        return self._monitor

    def show_on(self, monitor: Monitor) -> bool:
        """Ouvre (ou déplace) la fenêtre sur `monitor`."""
        if self.is_open and self._monitor == monitor:
            return True
        self.close()
        profile_dir: str | None = None
        native = self._native_finder()
        url = _resolve_url(self._url)
        if native:
            command = build_native_projector_command(native, url)
        else:
            browser = self._browser_finder()
            if not browser:
                logger.warning("Aucune fenêtre native ni navigateur Chromium trouvé : fenêtre projecteur impossible")
                return False
            profile_dir = self._profile_factory()
            wayland = os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
            command = build_projector_command(browser, url, monitor, profile_dir, wayland=wayland)
        try:
            self._process = self._popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            logger.warning(f"Lancement de la fenêtre projecteur impossible : {exc}")
            if profile_dir:
                shutil.rmtree(profile_dir, ignore_errors=True)
            return False
        self._profile_dir = profile_dir
        self._monitor = monitor
        if self._after_launch:
            try:
                self._after_launch(self._process)
            except Exception as exc:
                logger.debug(f"after_launch ignoré : {exc}")
        logger.info(f"Fenêtre projecteur ouverte sur {monitor.name} ({monitor.resolution}+{monitor.x}+{monitor.y})")
        return True

    def close(self) -> None:
        process, self._process = self._process, None
        self._monitor = None
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                try:
                    process.kill()
                except Exception as exc:
                    logger.debug("close : %s", exc)
        if self._profile_dir:
            shutil.rmtree(self._profile_dir, ignore_errors=True)
            self._profile_dir = None
