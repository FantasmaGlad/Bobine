"""Fenêtre projecteur plein écran : navigateur de kiosque ou projecteur natif sur un écran donné."""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PureWindowsPath
from typing import Callable
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
    system = system or platform.system()
    environ = os.environ if environ is None else environ
    if system == "Windows":
        found = which("msedge")
        if found:
            return found
        for base_var in ("ProgramFiles(x86)", "ProgramFiles", "LocalAppData"):
            base = environ.get(base_var)
            if not base:
                continue
            for relative in (
                r"Microsoft\Edge\Application\msedge.exe",
                r"Google\Chrome\Application\chrome.exe",
            ):
                candidate = str(Path(base) / relative)
                if exists(candidate):
                    return candidate
        return which("chrome")
    if system == "Linux":
        for candidate in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "brave-browser", "msedge"):
            found = which(candidate)
            if found:
                return found
    return None


def find_native_projector(
    system: str | None = None,
    environ: dict | None = None,
    executable: str | None = None,
    exists: Callable[[str], bool] = os.path.exists,
) -> str | None:
    """Fenêtre native `bobine-projector` : Remplace le navigateur piloté (WKWebView sur macOS, WebView2 sur Windows, WebKitGTK sur Linux) pour éliminer les conflits de positionnement multi-écrans."""
    system = system or platform.system()
    environ = os.environ if environ is None else environ
    override = environ.get("BOBINE_PROJECTOR_BIN")
    if override and exists(override):
        return override

    executable = executable or sys.executable
    path_cls = PureWindowsPath if system == "Windows" else Path
    exe_path = path_cls(executable)
    exe_dir = exe_path.parent

    bin_name = "bobine-projector.exe" if system == "Windows" else "bobine-projector"

    if system == "Darwin":
        for candidate in (exe_dir / "bobine-projector", exe_dir.parent / "Resources" / "bobine-projector"):
            if exists(str(candidate)):
                return str(candidate)
    else:
        candidates = [
            exe_dir / bin_name,
            exe_dir / "projector" / "target" / "release" / bin_name,
            exe_dir.parent / "projector" / "target" / "release" / bin_name,
        ]
        for candidate in candidates:
            if exists(str(candidate)):
                return str(candidate)

    return None


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
