"""Démon Tor lancé à la demande par Bobine et arrêté après inactivité."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from app.utils.tor_socks import TorUnavailable

logger = logging.getLogger(__name__)


IDLE_STOP_SECONDS = 300.0


BOOTSTRAP_TIMEOUT_SECONDS = 120.0


_LISTENER_RE = re.compile(r"Opened Socks listener connection \(ready\) on 127\.0\.0\.1:(\d+)")


def find_tor_binary() -> str | None:
    found = shutil.which("tor")
    if found:
        return found
    for candidate in ("/opt/homebrew/bin/tor", "/usr/local/bin/tor", "/usr/sbin/tor"):
        if os.access(candidate, os.X_OK):
            return candidate
    return None


def _cache_dir() -> Path:
    from app.config import DATA_ROOT

    return Path(DATA_ROOT) / "tor"


def _linux_parent_death_signal() -> None:
    import ctypes
    import signal

    ctypes.CDLL(None).prctl(1, signal.SIGTERM)


class _OnDemandTor:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen | None = None
        self._port: int | None = None
        self._users = 0
        self._last_release = 0.0
        self._timer: threading.Timer | None = None

    def acquire(self, binary: str) -> tuple[str, int]:
        with self._lock:
            self._users += 1
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            try:
                if self._process is None or self._process.poll() is not None:
                    self._start(binary)
            except BaseException:
                self._users -= 1
                raise
            return "127.0.0.1", self._port  # type: ignore[return-value]

    def release(self) -> None:
        with self._lock:
            self._users = max(0, self._users - 1)
            if self._users == 0 and self._process is not None:
                self._timer = threading.Timer(IDLE_STOP_SECONDS, self._stop_if_idle)
                self._timer.daemon = True
                self._timer.start()

    def _stop_if_idle(self) -> None:
        with self._lock:
            if self._users == 0:
                self._stop_locked()

    def stop(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._stop_locked()

    def _stop_locked(self) -> None:
        process, self._process, self._port = self._process, None, None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        logger.info("Tor arrêté (plus aucune requête de mise à jour).")

    def _start(self, binary: str) -> None:
        data_dir = _cache_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(data_dir, 0o700)
        command = [
            binary, "-f", os.devnull, "--defaults-torrc", os.devnull, "--ignore-missing-torrc",
            "--DataDirectory", str(data_dir), "--SocksPort", "127.0.0.1:auto", "--ControlPort", "0",
            "--ClientOnly", "1", "--AvoidDiskWrites", "1", "--Log", "notice stdout",
        ]
        options: dict[str, Any] = {}
        if sys.platform.startswith("linux"):
            options["preexec_fn"] = _linux_parent_death_signal
        elif os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace", **options,
        )
        port: int | None = None
        deadline = time.monotonic() + BOOTSTRAP_TIMEOUT_SECONDS
        tail: list[str] = []
        assert process.stdout is not None
        while time.monotonic() < deadline:
            line = process.stdout.readline()
            if not line:
                break
            tail = (tail + [line.strip()])[-5:]
            match = _LISTENER_RE.search(line)
            if match:
                port = int(match.group(1))
            if "Bootstrapped 100%" in line and port is not None:
                self._process, self._port = process, port
                threading.Thread(target=_drain, args=(process,), daemon=True, name="tor-log").start()
                logger.info("Tor lancé pour les mises à jour (127.0.0.1:%s).", port)
                return
        process.kill()
        raise TorUnavailable(f"Tor n'a pas pu rejoindre le réseau ({' / '.join(tail) or 'aucune sortie'})")


def _drain(process: subprocess.Popen) -> None:
    assert process.stdout is not None
    for _ in process.stdout:
        pass


on_demand = _OnDemandTor()
