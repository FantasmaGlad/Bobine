"""BobineTray — icône de zone de notification + supervision du backend, pour les profils « app de bureau » (Windows, Linux de bureau et macOS)."""

import json
import logging
import os
import platform
import plistlib
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

import pystray
from PIL import Image

from app.desktop import channel_icon, tray_actions
from app.desktop.displays import (
    REPORT_REFRESH_SECONDS,
    DisplayOrchestrator,
    DisplayWatcher,
    ProjectorWindow,
    external_monitors,
    list_monitors,
)

from app.utils.port import DEFAULT_PORT, read_runtime

logger = logging.getLogger(__name__)


def _admin_port() -> int:
    try:
        from app.utils.port import current_port
        return int(current_port())
    except Exception:
        return DEFAULT_PORT


def _admin_url() -> str:
    return f"http://127.0.0.1:{_admin_port()}"


def _kiosk_url() -> str:
    return f"{_admin_url()}/kiosk"


def _grid_url() -> str:
    return f"{_admin_url()}/grid"


def _cinema_url() -> str:
    return f"{_admin_url()}/cinema"


def _health_url() -> str:
    return f"{_admin_url()}/api/health"


def _display_state_url() -> str:
    return f"{_admin_url()}/api/display/state"


def _projector_url() -> str:
    return f"{_admin_url()}/cinema/?channel=cable"


def _updates_check_url() -> str:
    return f"{_admin_url()}/api/updates/check"


def _updates_status_url() -> str:
    return f"{_admin_url()}/api/updates/status"


HEALTH_POLL_INTERVAL_SECONDS = 30
HEALTH_FAILURES_BEFORE_RESTART = 3

UPDATE_POLL_INTERVAL_SECONDS = 6 * 60 * 60

UPDATE_STATUS_POLL_INTERVAL_SECONDS = 15


def _backend_command() -> list[str]:
    exe_dir = Path(sys.executable).resolve().parent
    for name in ("BobineBackend.exe", "BobineBackend"):
        candidate = exe_dir / name
        if candidate.exists():
            return [str(candidate)]
    return [sys.executable, str(Path(__file__).resolve().parents[2] / "run_backend.py")]


class BackendSupervisor:
    """Démarre BobineBackend et le relance s'il s'arrête de lui-même ou sur demande explicite (cf."""

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

    def is_running(self) -> bool:
        with self._lock:
            return self._process is not None and self._process.poll() is None

    def _supervise_loop(self) -> None:
        while not self._stop_requested:
            creationflags = 0
            if platform.system() == "Windows":
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            with self._lock:
                self._process = subprocess.Popen(
                    self._backend_command,
                    creationflags=creationflags,
                )
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
                with urllib.request.urlopen(_health_url(), timeout=5) as resp:
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
    kiosk_args = ["--kiosk", "--autoplay-policy=no-user-gesture-required", target_url]

    if system == "Windows":
        edge = shutil.which("msedge")
        if edge:
            _set_display_always_on(True)
            subprocess.Popen([edge, *kiosk_args])
            return

    elif system == "Linux":
        for candidate in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "brave-browser", "msedge"):
            browser_bin = shutil.which(candidate)
            if browser_bin:
                _set_display_always_on(True)
                subprocess.Popen([browser_bin, *kiosk_args])
                return

        firefox = shutil.which("firefox")
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


def _fetch_settings() -> dict | None:
    request = urllib.request.Request(f"{_admin_url()}/api/settings", headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=1.0) as response:
        return json.loads(response.read().decode())


def _detect_current_channel() -> str:
    return channel_icon.detect_channel(_fetch_settings)


def _load_icon_image(channel: str | None = None) -> Image.Image:
    if channel is None:
        channel = _detect_current_channel()
    exe_dir = Path(sys.executable).resolve().parent
    images_dir = Path(__file__).resolve().parent.parent.parent.parent / "Assets" / "Images"
    return channel_icon.load_tray_image(channel, channel_icon.icon_candidates(channel, exe_dir, images_dir))


_LAUNCH_AGENT_LABEL = "com.bobine.app"


def _ensure_launch_agent_macos() -> None:
    if platform.system() != "Darwin" or not getattr(sys, "frozen", False):
        return

    tray_exe = str(Path(sys.executable).resolve())
    agent_path = Path.home() / "Library" / "LaunchAgents" / f"{_LAUNCH_AGENT_LABEL}.plist"

    if agent_path.exists():
        try:
            with open(agent_path, "rb") as f:
                existing = plistlib.load(f)
            if existing.get("ProgramArguments") == [tray_exe]:
                return
            logger.info(f"LaunchAgent obsolète (chemin enregistré différent de {tray_exe}) — réparation.")
        except Exception:
            logger.warning("LaunchAgent illisible/corrompu — réécriture.")

    try:
        log_dir = Path.home() / "Library" / "Logs" / "Bobine"
        log_dir.mkdir(parents=True, exist_ok=True)

        agent_path.parent.mkdir(parents=True, exist_ok=True)
        with open(agent_path, "wb") as f:
            plistlib.dump(
                {
                    "Label": _LAUNCH_AGENT_LABEL,
                    "ProgramArguments": [tray_exe],
                    "RunAtLoad": True,
                    "KeepAlive": {"SuccessfulExit": False},
                    "ProcessType": "Interactive",
                    "StandardOutPath": str(log_dir / "BobineTray.out.log"),
                    "StandardErrorPath": str(log_dir / "BobineTray.err.log"),
                },
                f,
            )

        subprocess.run(
            ["launchctl", "bootout", f"gui/{os.getuid()}/{_LAUNCH_AGENT_LABEL}"],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(agent_path)],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        logger.info(f"LaunchAgent installé et activé : {agent_path} -> {tray_exe}")
    except Exception as e:
        logger.warning(f"Échec de l'installation du LaunchAgent macOS (lancement automatique désactivé) : {e!r}")


def _ensure_desktop_shortcut() -> None:
    system = platform.system()
    try:
        if system == "Linux":
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
                                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            )
                        logger.info(f"Raccourci Bureau Linux créé : {dest}")
                    break
        elif system == "Darwin" and getattr(sys, "frozen", False):
            app_path = Path(sys.executable).resolve().parent.parent
            if app_path.suffix == ".app":
                desktop_dir = Path.home() / "Desktop"
                if desktop_dir.is_dir():
                    dest = desktop_dir / app_path.name
                    if not dest.exists():
                        try:
                            os.symlink(str(app_path), str(dest))
                            logger.info(f"Raccourci Bureau macOS créé : {dest} -> {app_path}")
                        except Exception:
                            pass
    except Exception as e:
        logger.debug(f"Vérification du raccourci Bureau ignorée : {e!r}")


def is_backend_running() -> bool:
    """Vérifie si une instance du backend Bobine répond déjà sur /api/health."""
    try:
        req = urllib.request.Request(_health_url(), headers={"User-Agent": "BobineTray"})
        with urllib.request.urlopen(req, timeout=1) as resp:
            return resp.status == 200
    except Exception:
        return False


_SINGLE_INSTANCE_LOCK_PORT = 47_821
_single_instance_socket: socket.socket | None = None


def _acquire_single_instance_lock() -> bool:
    global _single_instance_socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", _SINGLE_INSTANCE_LOCK_PORT))
    except OSError:
        sock.close()
        return False
    _single_instance_socket = sock
    return True


_update_lock = threading.Lock()
_update_state: dict = {"has_update": False, "latest_version": None, "download_url": None}


def _check_for_update_once() -> None:
    try:
        req = urllib.request.Request(_updates_check_url(), headers={"User-Agent": "BobineTray"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        with _update_lock:
            _update_state["has_update"] = bool(data.get("has_update"))
            _update_state["latest_version"] = data.get("latest_version")
            _update_state["download_url"] = data.get("download_url") or data.get("html_url")
        if _update_state["has_update"]:
            logger.info(f"Mise à jour disponible : {_update_state['latest_version']}")
    except Exception as e:
        logger.info(f"Vérification de mise à jour indisponible : {e}")


def _update_poll_loop() -> None:
    deadline = time.time() + 30.0
    while time.time() < deadline and not is_backend_running():
        time.sleep(0.5)
    while True:
        _check_for_update_once()
        time.sleep(UPDATE_POLL_INTERVAL_SECONDS)


def _notify_best_effort(icon: "pystray.Icon", title: str, message: str) -> None:
    try:
        icon.notify(message, title)
    except Exception as e:
        logger.debug(f"Notification native indisponible ({title!r}) : {e}")


def _port_fallback_notice(icon: "pystray.Icon", wait_seconds: float = 120.0) -> None:
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        info = read_runtime()
        if info:
            if info.get("fallback"):
                port, preferred = info["port"], info.get("preferred", DEFAULT_PORT)
                logger.warning("Backend sur le port de repli %s (port %s occupé)", port, preferred)
                _notify_best_effort(
                    icon,
                    "Bobine — port de repli",
                    f"Le port {preferred} est occupé : Bobine écoute sur le port {port}. "
                    f"Autres appareils : http://<adresse>:{port}."
                    + ("" if platform.system() == "Windows" else f" Si un pare-feu est actif, ouvrez ce port (firewalld : {DEFAULT_PORT} seulement)."),
                )
            return
        time.sleep(1.0)


def _update_status_poll_loop(icon: "pystray.Icon") -> None:
    last_notified_started_at = None
    current_channel = _detect_current_channel()
    while True:
        time.sleep(UPDATE_STATUS_POLL_INTERVAL_SECONDS)
        detected_channel = _detect_current_channel()
        if detected_channel != current_channel:
            current_channel = detected_channel
            try:
                icon.icon = _load_icon_image(detected_channel)
            except Exception as e:
                logger.debug(f"Mise à jour icône tray ({detected_channel}): {e}")

        try:
            req = urllib.request.Request(_updates_status_url(), headers={"User-Agent": "BobineTray"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                status = json.loads(resp.read().decode("utf-8"))
        except Exception:
            continue

        step = status.get("step")
        started_at = status.get("started_at")
        if not tray_actions.should_notify_update_outcome(status, last_notified_started_at):
            if step in ("done", "failed"):
                last_notified_started_at = started_at
            continue
        last_notified_started_at = started_at

        if step == "done":
            _notify_best_effort(icon, "Bobine — Mise à jour installée", status.get("message") or "Mise à jour terminée avec succès.")
        else:
            _notify_best_effort(icon, "Bobine — Échec de la mise à jour", status.get("error") or status.get("message") or "La mise à jour a échoué.")


def run() -> None:
    """Point d'entrée — `python -m app.desktop.tray` en développement, et l'exécutable `BobineTray.exe` une fois empaqueté."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if is_backend_running():
        logger.info("Bobine est déjà actif en arrière-plan. Ouverture de l'interface web.")
        webbrowser.open(_admin_url())
        return

    if not _acquire_single_instance_lock():
        logger.info(
            "Une autre instance de BobineTray supervise déjà le démarrage du backend "
            "— ouverture de l'interface web sans lancer de doublon."
        )
        webbrowser.open(_admin_url())
        return

    _ensure_launch_agent_macos()
    _ensure_desktop_shortcut()

    supervisor = BackendSupervisor(_backend_command())
    supervisor.start()

    if "--startup" not in sys.argv and "--minimized" not in sys.argv:
        threading.Thread(
            target=_open_initial_displays,
            daemon=True,
            name="bobine-open-displays",
        ).start()

    threading.Thread(target=_update_poll_loop, daemon=True, name="bobine-tray-update-check").start()

    def _keep_awake_while_projecting(process) -> None:
        if platform.system() == "Darwin" and shutil.which("caffeinate"):
            subprocess.Popen(["caffeinate", "-d", "-i", "-w", str(process.pid)])
        elif platform.system() in ("Windows", "Linux"):
            _set_display_always_on(True)

    display_orchestrator = DisplayOrchestrator(
        _display_state_url,
        ProjectorWindow(_projector_url, after_launch=_keep_awake_while_projecting),
        ready_check=is_backend_running,
    )
    display_watcher = DisplayWatcher(display_orchestrator.handle_change)
    display_watcher.start()

    def _refresh_display_report_loop() -> None:
        while True:
            time.sleep(REPORT_REFRESH_SECONDS)
            display_orchestrator.refresh_report()

    threading.Thread(target=_refresh_display_report_loop, daemon=True, name="bobine-display-refresh").start()

    def on_open_admin(icon, item):
        webbrowser.open(_admin_url())

    def on_open_grid(icon, item):
        webbrowser.open(_grid_url())

    def on_open_cinema(icon, item):
        webbrowser.open(_cinema_url())

    def on_open_kiosk(icon, item):
        launch_kiosk_browser()

    def on_check_update(icon, item):
        with _update_lock:
            has_update = _update_state["has_update"]
            download_url = _update_state["download_url"]
        if has_update and download_url:
            webbrowser.open(download_url)
        else:
            threading.Thread(target=_check_for_update_once, daemon=True, name="bobine-tray-update-check-now").start()

    def on_restart(icon, item):
        supervisor.restart_now()

    def on_reopen_projector(icon, item):
        if not display_orchestrator.reopen_projector():
            _notify_best_effort(icon, "Bobine", "Aucun écran externe détecté.")

    controls = tray_actions.Controls(_admin_url)

    def output_item(kind: str, target: str, name: str) -> "pystray.MenuItem":
        def on_click(icon, item):
            if not controls.toggle(kind, target):
                _notify_best_effort(icon, "Bobine", f"{name} : rien à mettre en pause ni à reprendre.")

        return pystray.MenuItem(
            lambda item: controls.label(kind, target, name), on_click,
            enabled=lambda item: controls.next_action(controls.states().get((kind, target))) is not None,
        )

    def on_stop_all(icon, item):
        accepted = controls.stop_all()
        if accepted < len(tray_actions.OUTPUTS):
            _notify_best_effort(icon, "Bobine", f"Diffusion arrêtée sur {accepted} sortie(s) sur {len(tray_actions.OUTPUTS)}.")

    def on_quit(icon, item):
        display_watcher.stop()
        display_orchestrator.shutdown()
        supervisor.stop()
        icon.stop()

    def status_text(item):
        return "État : en ligne" if supervisor.is_running() else "État : hors ligne"

    def update_text(item):
        with _update_lock:
            if _update_state["has_update"]:
                return f"Mise à jour disponible ({_update_state['latest_version']}) — Télécharger"
            return "Aucune mise à jour disponible (cliquer pour vérifier)"

    menu = pystray.Menu(
        pystray.MenuItem(status_text, None, enabled=False),
        pystray.Menu.SEPARATOR,
        *[output_item(kind, target, name) for kind, target, name in tray_actions.OUTPUTS],
        pystray.MenuItem("Couper la diffusion", on_stop_all),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Ouvrir l'administration", on_open_admin, default=True),
        pystray.MenuItem("Ouvrir le pupitre tactile (/grid)", on_open_grid),
        pystray.MenuItem("Ouvrir l'écran cinéma (/cinema)", on_open_cinema),
        pystray.MenuItem("Ouvrir en mode kiosque", on_open_kiosk),
        pystray.MenuItem("Rouvrir l'écran projecteur", on_reopen_projector),
        pystray.MenuItem(update_text, on_check_update),
        pystray.MenuItem("Redémarrer", on_restart),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quitter", on_quit),
    )

    icon = pystray.Icon("bobine", _load_icon_image(), "Bobine", menu=menu)
    threading.Thread(target=_port_fallback_notice, args=(icon,), daemon=True, name="bobine-tray-port-notice").start()
    threading.Thread(
        target=_update_status_poll_loop, args=(icon,), daemon=True, name="bobine-tray-update-status",
    ).start()
    icon.run()


if __name__ == "__main__":
    run()
