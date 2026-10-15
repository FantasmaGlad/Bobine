"""Détection des écrans externes et fenêtre « projecteur » des profils desktop
(Windows, Linux de bureau ; macOS : voir plus bas).

Pourquoi : jusqu'ici le tray n'ouvrait ses interfaces qu'UNE fois au démarrage
(`tray._open_initial_displays`), sans jamais énumérer les moniteurs ni
positionner le navigateur kiosque : en bureau ÉTENDU, la fenêtre s'ouvrait sur
l'écran principal (ou était absorbée par une instance de navigateur déjà
ouverte, qui ignore `--kiosk`) et le projecteur restait noir. Brancher un
projecteur après le démarrage n'avait aucun effet.

Ce module apporte :
  * `list_monitors()` — énumération native par OS, défensive (jamais d'exception) ;
  * `DisplayWatcher` — surveillance du branchement/débranchement (sondage court
    + stabilisation : un moniteur qui « clignote » pendant une renégociation de
    mode n'est pas pris pour un débranchement) ;
  * `ProjectorWindow` — navigateur kiosque DÉDIÉ (profil jetable → instance
    garantie distincte, donc `--kiosk` honoré) positionné sur le moniteur externe ;
  * `report_display_state()` — rapport rejouable au backend (`PUT
    /api/display/state`), d'où le mode d'affichage effectif est dérivé.

Aucun import de `pystray`/GUI ici : tout est testable sans affichage
(`backend/tests/test_desktop_displays.py`). Les appels d'OS sont enveloppés
(repli élégant, jamais d'échec fatal).
"""

from __future__ import annotations

import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Callable, Sequence

logger = logging.getLogger(__name__)

# Sondage de la topologie : une exécution de `xrandr`/`EnumDisplayMonitors`
# coûte quelques ms, 2 s donnent un branchement perçu comme instantané.
POLL_INTERVAL_SECONDS = 2.0
# Une topologie doit être lue à l'identique N fois de suite avant d'être prise
# en compte : pendant la renégociation de mode d'un projecteur, un moniteur
# peut disparaître/réapparaître brièvement.
STABLE_POLLS_REQUIRED = 2
# Ré-émission périodique de l'état au backend (le rapport y est gardé en
# mémoire : un redémarrage du backend l'efface).
REPORT_REFRESH_SECONDS = 60.0


@dataclass(frozen=True)
class Monitor:
    name: str
    x: int
    y: int
    width: int
    height: int
    primary: bool = False

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"


# ----------------------------------------------------------------------
# Énumération des moniteurs
# ----------------------------------------------------------------------

_XRANDR_MONITOR_RE = re.compile(
    # `flags` = « + » (moniteur issu d'une sortie RandR) et/ou « * » (principal) ;
    # absents pour un moniteur défini à la main (`xrandr --setmonitor`), cas
    # constaté sur une vraie session XWayland.
    r"^\s*\d+:\s+(?P<flags>[+*]*)(?P<name>\S+)\s+(?P<w>\d+)/\d+x(?P<h>\d+)/\d+\+(?P<x>-?\d+)\+(?P<y>-?\d+)"
)


def parse_xrandr_listmonitors(output: str) -> list[Monitor]:
    """Analyse la sortie de `xrandr --listmonitors` (pur, testable)."""
    monitors: list[Monitor] = []
    for line in output.splitlines():
        match = _XRANDR_MONITOR_RE.match(line)
        if not match:
            continue
        monitors.append(
            Monitor(
                name=match.group("name"),
                x=int(match.group("x")),
                y=int(match.group("y")),
                width=int(match.group("w")),
                height=int(match.group("h")),
                primary="*" in match.group("flags"),
            )
        )
    return monitors


def _list_monitors_linux() -> list[Monitor]:
    # X11 natif, ou XWayland sous Wayland (GNOME/KDE y exposent leurs moniteurs
    # via RandR) — positionnement « meilleur effort » sous Wayland.
    xrandr = shutil.which("xrandr")
    if not xrandr:
        return []
    result = subprocess.run(
        [xrandr, "--listmonitors"], capture_output=True, text=True, timeout=5, check=False
    )
    return parse_xrandr_listmonitors(result.stdout)


def _list_monitors_windows() -> list[Monitor]:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    try:
        # Coordonnées PHYSIQUES (sinon virtualisées par la mise à l'échelle).
        user32.SetProcessDPIAware()
    except Exception:
        pass

    class RECT(ctypes.Structure):
        _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
            ("szDevice", wintypes.WCHAR * 32),
        ]

    MONITORINFOF_PRIMARY = 1
    found: list[Monitor] = []
    enum_proc_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HANDLE, wintypes.HDC, ctypes.POINTER(RECT), wintypes.LPARAM
    )

    def _callback(hmonitor, _hdc, _rect, _lparam):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            rect = info.rcMonitor
            found.append(
                Monitor(
                    name=str(info.szDevice),
                    x=int(rect.left),
                    y=int(rect.top),
                    width=int(rect.right - rect.left),
                    height=int(rect.bottom - rect.top),
                    primary=bool(info.dwFlags & MONITORINFOF_PRIMARY),
                )
            )
        return True

    user32.EnumDisplayMonitors(None, None, enum_proc_type(_callback), 0)
    return found


_RESOLUTION_RE = re.compile(r"(\d+)\s*x\s*(\d+)")


def parse_macos_displays(profiler_json: str) -> list[Monitor]:
    """Analyse `system_profiler SPDisplaysDataType -json` (pur, testable). Les
    positions ne sont pas exposées par cet outil : seuls le nombre d'écrans,
    leur résolution et l'écran principal sont fiables — suffisant pour dériver
    le mode ; le placement de fenêtre macOS passe par la fenêtre native."""
    try:
        data = json.loads(profiler_json)
    except (ValueError, TypeError):
        return []
    monitors: list[Monitor] = []
    for gpu in data.get("SPDisplaysDataType", []) or []:
        for index, display in enumerate(gpu.get("spdisplays_ndrvs", []) or []):
            match = _RESOLUTION_RE.search(str(display.get("_spdisplays_resolution", "")))
            width, height = (int(match.group(1)), int(match.group(2))) if match else (0, 0)
            monitors.append(
                Monitor(
                    name=str(display.get("_name", f"display-{len(monitors)}")),
                    x=0,
                    y=0,
                    width=width,
                    height=height,
                    primary=str(display.get("spdisplays_main", "")).endswith("yes"),
                )
            )
    return monitors


def _list_monitors_macos() -> list[Monitor]:
    result = subprocess.run(
        ["system_profiler", "SPDisplaysDataType", "-json"],
        capture_output=True, text=True, timeout=15, check=False,
    )
    return parse_macos_displays(result.stdout)


def list_monitors() -> list[Monitor]:
    """Moniteurs connectés ; liste vide si l'énumération est impossible (ne
    lève jamais)."""
    system = platform.system()
    try:
        if system == "Linux":
            return _list_monitors_linux()
        if system == "Windows":
            return _list_monitors_windows()
        if system == "Darwin":
            return _list_monitors_macos()
    except Exception as exc:  # pragma: no cover - dépend de l'OS
        logger.warning(f"Énumération des moniteurs impossible ({system}) : {exc}")
    return []


def external_monitors(monitors: Sequence[Monitor]) -> list[Monitor]:
    """Moniteurs EXTERNES = tous sauf le principal. Sans moniteur marqué
    principal (certains OS/sessions), le premier fait office de principal."""
    if len(monitors) <= 1:
        return []
    primary = next((m for m in monitors if m.primary), monitors[0])
    return [m for m in monitors if m is not primary and m != primary]


# ----------------------------------------------------------------------
# Rapport au backend
# ----------------------------------------------------------------------

_report_generation = 0
_report_lock = threading.Lock()


def _source_label() -> str:
    return {"Linux": "linux", "Windows": "windows", "Darwin": "macos"}.get(platform.system(), "linux")


def report_display_state(
    state_url: str,
    count: int,
    resolution: str | None = None,
    *,
    source: str | None = None,
    sleep: Callable[[float], None] = time.sleep,
    urlopen=urllib.request.urlopen,
    max_attempts: int = 60,
) -> bool:
    """`PUT /api/display/state` avec nouvelles tentatives (backend pas encore
    prêt au démarrage). Un rapport plus récent annule les tentatives du
    précédent (génération) pour ne jamais écraser un état récent par un ancien.
    Retourne True si le rapport a été accepté."""
    global _report_generation
    with _report_lock:
        _report_generation += 1
        generation = _report_generation
    body = {"external_count": int(count), "source": source or _source_label()}
    if resolution:
        body["resolution"] = resolution
    payload = json.dumps(body).encode("utf-8")
    for attempt in range(max_attempts):
        if generation != _report_generation:
            return False
        try:
            request = urllib.request.Request(
                state_url, data=payload, method="PUT",
                headers={"Content-Type": "application/json", "User-Agent": "BobineTray"},
            )
            with urlopen(request, timeout=5) as response:
                if 200 <= response.status < 300:
                    return True
        except Exception as exc:
            logger.debug(f"Rapport d'état des écrans en échec (tentative {attempt + 1}) : {exc}")
        sleep(min(1.0 * (attempt + 1), 10.0))
    return False


# ----------------------------------------------------------------------
# Fenêtre projecteur
# ----------------------------------------------------------------------

def find_kiosk_browser(
    system: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
    exists: Callable[[str], bool] = os.path.exists,
    environ: dict | None = None,
) -> str | None:
    """Navigateur Chromium utilisable en kiosque (pur, testable). macOS : None —
    le projecteur y passe par une fenêtre native."""
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
    """Fenêtre native `bobine-projector` :
    Remplace le navigateur piloté (WKWebView sur macOS, WebView2 sur Windows,
    WebKitGTK sur Linux) pour éliminer les conflits de positionnement multi-écrans.
    Cherchée via BOBINE_PROJECTOR_BIN, puis à côté de l'exécutable du tray
    ou dans le dossier target/release du crate projector. Pur et testable."""
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
        # Linux & Windows : à côté de l'exécutable, ou dans target/release/ en environnement dev
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
    """Ligne de commande de la fenêtre native : elle choisit elle-même l'écran
    externe (les positions ne sont pas exposées par `system_profiler`)."""
    return [binary, "--url", url, "--monitor", monitor]


def build_projector_command(
    browser: str,
    url: str,
    monitor: Monitor,
    profile_dir: str,
    *,
    wayland: bool = False,
) -> list[str]:
    """Ligne de commande du navigateur kiosque positionné sur `monitor` (pur).
    `--user-data-dir` dédié : sans lui, un navigateur déjà ouvert récupère l'URL
    et ignore `--kiosk`/`--window-position`. Sous Wayland, Chromium ignore le
    positionnement : on le force via XWayland (meilleur effort)."""
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
    ]
    if wayland:
        command.append("--ozone-platform=x11")
    command.append(url)
    return command


class ProjectorWindow:
    """Cycle de vie de la fenêtre kiosque sur le moniteur externe."""

    def __init__(
        self,
        url: str,
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
        """Ouvre (ou déplace) la fenêtre sur `monitor`. Sans changement de
        moniteur et si la fenêtre vit encore, ne fait rien (idempotent)."""
        if self.is_open and self._monitor == monitor:
            return True
        self.close()
        profile_dir: str | None = None
        native = self._native_finder()
        if native:
            # Fenêtre native (macOS) : pas de navigateur, pas de profil.
            command = build_native_projector_command(native, self._url)
        else:
            browser = self._browser_finder()
            if not browser:
                logger.warning("Aucune fenêtre native ni navigateur Chromium trouvé : fenêtre projecteur impossible")
                return False
            profile_dir = self._profile_factory()
            wayland = os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
            command = build_projector_command(browser, self._url, monitor, profile_dir, wayland=wayland)
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
                except Exception:
                    pass
        if self._profile_dir:
            shutil.rmtree(self._profile_dir, ignore_errors=True)
            self._profile_dir = None


# ----------------------------------------------------------------------
# Surveillance et orchestration
# ----------------------------------------------------------------------

class DisplayWatcher(threading.Thread):
    """Interroge la topologie des moniteurs et appelle `on_change(monitors)` à
    la première lecture stable puis à chaque changement stable."""

    def __init__(
        self,
        on_change: Callable[[tuple[Monitor, ...]], None],
        list_fn: Callable[[], Sequence[Monitor]] = list_monitors,
        interval: float = POLL_INTERVAL_SECONDS,
        stable_polls: int = STABLE_POLLS_REQUIRED,
    ) -> None:
        super().__init__(daemon=True, name="bobine-display-watcher")
        self._on_change = on_change
        self._list_fn = list_fn
        self._interval = interval
        self._stable_polls = max(1, stable_polls)
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def poll_once(self, state: dict) -> None:
        """Un tour de sondage (séparé de `run` pour être testable)."""
        try:
            current = tuple(self._list_fn())
        except Exception as exc:
            logger.warning(f"Sondage des moniteurs en échec : {exc}")
            return
        if current == state.get("candidate"):
            state["count"] = state.get("count", 0) + 1
        else:
            state["candidate"] = current
            state["count"] = 1
        if state["count"] >= self._stable_polls and current != state.get("confirmed"):
            state["confirmed"] = current
            self._on_change(current)

    def run(self) -> None:
        state: dict = {}
        while not self._stop_event.is_set():
            self.poll_once(state)
            self._stop_event.wait(self._interval)


class DisplayOrchestrator:
    """Relie surveillance, rapport au backend et fenêtre projecteur."""

    # Attente maximale du backend avant d'ouvrir la fenêtre : ouvrir un
    # navigateur sur un serveur qui n'écoute pas encore affiche une page
    # d'erreur « connexion refusée » qui resterait à l'écran.
    BACKEND_WAIT_SECONDS = 60.0

    def __init__(
        self,
        state_url: str,
        projector: ProjectorWindow,
        reporter: Callable[..., bool] = report_display_state,
        ready_check: Callable[[], bool] = lambda: True,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._state_url = state_url
        self._projector = projector
        self._reporter = reporter
        self._ready_check = ready_check
        self._sleep = sleep
        self._last_externals: tuple[Monitor, ...] = ()
        self._generation = 0
        self._lock = threading.Lock()
        self._threads: list[threading.Thread] = []

    @property
    def last_externals(self) -> tuple[Monitor, ...]:
        return self._last_externals

    def _spawn(self, target, *args, name: str) -> None:
        thread = threading.Thread(target=target, args=args, daemon=True, name=name)
        self._threads = [t for t in self._threads if t.is_alive()] + [thread]
        thread.start()

    def join(self, timeout: float = 5.0) -> None:
        """Attend la fin des tâches en cours (tests)."""
        for thread in list(self._threads):
            thread.join(timeout)

    def handle_change(self, monitors: Sequence[Monitor]) -> None:
        externals = tuple(external_monitors(monitors))
        self._last_externals = externals
        self._generation += 1
        logger.info(f"Topologie des écrans : {len(monitors)} moniteur(s), {len(externals)} externe(s)")
        resolution = externals[0].resolution if externals else None
        # Rapport et ouverture de fenêtre hors du thread de sondage : ils
        # peuvent attendre un backend pas encore prêt.
        self._spawn(self._reporter, self._state_url, len(externals), resolution, name="bobine-display-report")
        self._spawn(self._apply, self._generation, externals, name="bobine-display-apply")

    def _apply(self, generation: int, externals: tuple[Monitor, ...]) -> None:
        if externals:
            waited = 0.0
            while not self._ready_check():
                if generation != self._generation or waited >= self.BACKEND_WAIT_SECONDS:
                    return
                self._sleep(0.5)
                waited += 0.5
        with self._lock:
            if generation != self._generation:
                return  # une topologie plus récente a pris le relais
            if externals:
                self._projector.show_on(externals[0])
            else:
                self._projector.close()

    def reopen_projector(self) -> bool:
        """Rouvre la fenêtre projecteur (menu du tray) si un écran externe existe."""
        externals = self._last_externals
        if not externals:
            return False
        with self._lock:
            return self._projector.show_on(externals[0])

    def refresh_report(self) -> None:
        """Ré-émet l'état courant (le backend le garde en mémoire seulement)."""
        externals = self._last_externals
        self._spawn(
            self._reporter, self._state_url, len(externals),
            externals[0].resolution if externals else None,
            name="bobine-display-report-refresh",
        )

    def shutdown(self) -> None:
        self._generation += 1
        self._projector.close()
