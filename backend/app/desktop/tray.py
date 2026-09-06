"""BobineTray — icône de zone de notification + supervision du backend,
pour les profils « app de bureau » (Windows Lot 1, puis Linux de bureau /
macOS aux Lots 2-3).

Point d'entrée SÉPARÉ de l'API FastAPI (`app.main`) : ce module est
empaqueté par PyInstaller comme un second exécutable (`BobineTray.exe`),
lancé au démarrage de session (raccourci posé par l'installeur Inno
Setup), qui démarre et surveille `BobineBackend.exe` comme process enfant
— aucun Service Windows ni canal de communication dédié n'est nécessaire
(cf. CDC §5.3 : « app de bureau lancée par un utilisateur connecté »,
pas une « boîte noire »).

Référence : docs/cahier-des-charges-multi-os.md §5.3/§5.4,
docs/plan-implementation-portabilite-crossplatformx.md §2.
"""

import logging
import platform
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

import pystray
from PIL import Image

logger = logging.getLogger(__name__)

ADMIN_URL = "http://127.0.0.1:8000"
KIOSK_URL = f"{ADMIN_URL}/kiosk"
HEALTH_URL = f"{ADMIN_URL}/api/health"

# Supervision "logique" (process vivant mais /api/health en échec de façon
# répétée) — complète la supervision "process mort" de BackendSupervisor,
# même principe que scripts/watchdog.sh pour l'appliance headless (cf. plan
# §2, portée précisée par rapport à ce script).
HEALTH_POLL_INTERVAL_SECONDS = 30
HEALTH_FAILURES_BEFORE_RESTART = 3


def _backend_command() -> list[str]:
    """Commande pour lancer BobineBackend. Une fois empaqueté (PyInstaller),
    cherche l'exécutable frère `BobineBackend(.exe)` à côté de celui-ci. En
    développement (ni l'un ni l'autre trouvé), retombe sur `uvicorn` via
    l'interpréteur courant — ce qui rend ce module directement testable
    sans packaging, y compris hors Windows."""
    exe_dir = Path(sys.executable).resolve().parent
    for name in ("BobineBackend.exe", "BobineBackend"):
        candidate = exe_dir / name
        if candidate.exists():
            return [str(candidate)]
    return [
        sys.executable, "-m", "uvicorn", "app.main:app",
        "--host", "0.0.0.0", "--port", "8000", "--workers", "1",
    ]


class BackendSupervisor:
    """Démarre BobineBackend et le relance s'il s'arrête de lui-même ou sur
    demande explicite (cf. `WindowsHandler.restart_services()`, qui se
    contente de quitter le process courant en confiance qu'il sera relancé
    ici — aucun canal de communication dédié n'est nécessaire)."""

    def __init__(self, backend_command: list[str]):
        self._backend_command = backend_command
        self._process: subprocess.Popen | None = None
        self._stop_requested = False
        self._lock = threading.Lock()

    def start(self) -> None:
        self._stop_requested = False
        threading.Thread(target=self._supervise_loop, daemon=True, name="bobine-tray-supervisor").start()
        threading.Thread(target=self._health_poll_loop, daemon=True, name="bobine-tray-health").start()

    def stop(self) -> None:
        self._stop_requested = True
        with self._lock:
            if self._process is not None:
                self._process.terminate()

    def restart_now(self) -> None:
        with self._lock:
            if self._process is not None:
                self._process.terminate()
        # La boucle de supervision relance automatiquement (cf.
        # _supervise_loop, `self._process.wait()` qui revient dès la
        # terminaison) — aucun autre code nécessaire ici.

    def is_running(self) -> bool:
        with self._lock:
            return self._process is not None and self._process.poll() is None

    def _supervise_loop(self) -> None:
        while not self._stop_requested:
            with self._lock:
                self._process = subprocess.Popen(self._backend_command)
            logger.info(f"BobineBackend démarré (pid={self._process.pid})")
            self._process.wait()
            if self._stop_requested:
                return
            logger.warning("BobineBackend s'est arrêté — relance dans 2s")
            time.sleep(2)

    def _health_poll_loop(self) -> None:
        consecutive_failures = 0
        while not self._stop_requested:
            time.sleep(HEALTH_POLL_INTERVAL_SECONDS)
            if not self.is_running():
                consecutive_failures = 0
                continue
            try:
                with urllib.request.urlopen(HEALTH_URL, timeout=5) as resp:
                    ok = resp.status == 200
            except Exception:
                ok = False
            consecutive_failures = 0 if ok else consecutive_failures + 1
            if consecutive_failures >= HEALTH_FAILURES_BEFORE_RESTART:
                logger.warning(
                    f"/api/health en échec {consecutive_failures} fois de suite — redémarrage forcé du backend"
                )
                consecutive_failures = 0
                self.restart_now()


def _set_display_always_on(enabled: bool) -> None:
    """Anti-veille activée UNIQUEMENT pendant la session kiosque (CDC §5.4/§6.3)
    — jamais globalement : contrairement à l'appliance headless,
    l'utilisateur qui installe Bobine sur son PC personnel veut
    probablement garder son comportement de veille habituel le reste du
    temps. Windows : SetThreadExecutionState ; Linux (X11) : xset."""
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
                    subprocess.run(["xset", "s", "off", "-dpms"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    subprocess.run(["xset", "s", "default", "+dpms"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass


def launch_kiosk_browser() -> None:
    """Lance le navigateur en mode kiosque optionnel (décision #1 du CDC).
    - Windows : préfère Edge (Chromium).
    - Linux : cherche chromium, google-chrome ou firefox en mode --kiosk.
    - Repli universel : navigateur par défaut."""
    system = platform.system()
    kiosk_args = ["--kiosk", "--autoplay-policy=no-user-gesture-required", KIOSK_URL]

    if system == "Windows":
        edge = shutil.which("msedge")
        if edge:
            _set_display_always_on(True)
            subprocess.Popen([edge, *kiosk_args])
            return

    elif system == "Linux":
        # Recherche d'un navigateur Chromium sous Linux
        for candidate in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "brave-browser", "msedge"):
            browser_bin = shutil.which(candidate)
            if browser_bin:
                _set_display_always_on(True)
                subprocess.Popen([browser_bin, *kiosk_args])
                return

        # Repli Firefox
        firefox = shutil.which("firefox")
        if firefox:
            _set_display_always_on(True)
            subprocess.Popen([firefox, "--kiosk", KIOSK_URL])
            return

    webbrowser.open(KIOSK_URL)


_ICON_FILENAME = "logo_bobine_icon.png"


def _load_icon_image() -> Image.Image:
    """Cherche l'asset d'icône à côté de l'exécutable une fois empaqueté
    (PyInstaller, cf. `packaging/windows/bobine.spec` — `contents_directory
    = "."` y garantit une arborescence plate, sans sous-dossier
    `_internal`), avec repli sur le chemin du dépôt en développement, puis
    un repli minimal généré si aucun des deux n'est trouvé."""
    candidates = [
        Path(sys.executable).resolve().parent / _ICON_FILENAME,
        Path(__file__).resolve().parent.parent.parent.parent / "Assets" / "Images" / _ICON_FILENAME,
    ]
    for path in candidates:
        if path and path.exists():
            return Image.open(path).convert("RGBA").resize((64, 64))
    return Image.new("RGBA", (64, 64), (15, 110, 116, 255))


def run() -> None:
    """Point d'entrée — `python -m app.desktop.tray` en développement, et
    l'exécutable `BobineTray.exe` une fois empaqueté."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    supervisor = BackendSupervisor(_backend_command())
    supervisor.start()

    def on_open_admin(icon, item):
        webbrowser.open(ADMIN_URL)

    def on_open_kiosk(icon, item):
        launch_kiosk_browser()

    def on_restart(icon, item):
        supervisor.restart_now()

    def on_quit(icon, item):
        supervisor.stop()
        icon.stop()

    def status_text(item):
        return "État : en ligne" if supervisor.is_running() else "État : hors ligne"

    menu = pystray.Menu(
        pystray.MenuItem(status_text, None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Ouvrir l'administration", on_open_admin, default=True),
        pystray.MenuItem("Ouvrir en mode kiosque", on_open_kiosk),
        pystray.MenuItem("Redémarrer", on_restart),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quitter", on_quit),
    )

    icon = pystray.Icon("bobine", _load_icon_image(), "Bobine", menu=menu)
    icon.run()


if __name__ == "__main__":
    run()
