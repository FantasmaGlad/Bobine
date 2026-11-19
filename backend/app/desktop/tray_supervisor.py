"""Supervision du backend par le plateau : lancement, redémarrage sur santé dégradée, instance unique."""

from __future__ import annotations

import logging
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from app.desktop import system

from .tray_urls import HEALTH_FAILURES_BEFORE_RESTART, HEALTH_POLL_INTERVAL_SECONDS, _health_url

logger = logging.getLogger(__name__)


def _backend_command() -> list[str]:
    exe_dir = Path(sys.executable).resolve().parent
    for name in ("BobineBackend.exe", "BobineBackend"):
        candidate = exe_dir / name
        if candidate.exists():
            return [str(candidate)]
    return [sys.executable, str(Path(__file__).resolve().parents[2] / "run_backend.py")]


class BackendSupervisor:
    """Démarre BobineBackend et le relance s'il s'arrête de lui-même ou sur demande explicite."""

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
            creationflags = system.current().BACKEND_CREATIONFLAGS
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
