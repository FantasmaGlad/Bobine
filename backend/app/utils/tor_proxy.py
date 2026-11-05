"""Mises à jour par Tor : recherche et téléchargement passent par un proxy SOCKS5, jamais en direct.

Tor tourne le moins possible. Un proxy déjà présent (service tor, Tor Browser, Orbot) est utilisé tel quel. Sinon, si
le programme `tor` est installé, Bobine le lance comme simple client (sa propre configuration, jamais celle du
système : il ne devient pas un relais) le temps des requêtes, puis l'arrête après quelques minutes sans usage. Son
cache d'annuaire est gardé dans les données de Bobine : le démarrage suivant est plus court et télécharge moins.

`urllib` ne parle pas SOCKS et Bobine n'ajoute pas de dépendance pour si peu : la connexion SOCKS5 est ouverte ici, le
nom d'hôte transmis tel quel au proxy (ATYP 3) pour que la résolution DNS se fasse dans Tor, pas sur le réseau local.
Option activée et Tor indisponible : la requête échoue, elle ne part jamais en direct.
"""
from __future__ import annotations

import http.client
import ipaddress
import json
import logging
import os
import re
import shutil
import socket
import ssl
import struct
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SETTING_ENABLED = "update_tor"
SETTING_PROXY = "update_tor_proxy"
DEFAULT_PROXY = "127.0.0.1:9050"
TOR_BROWSER_PROXY = "127.0.0.1:9150"
CHECK_URL = "https://check.torproject.org/api/ip"
IDLE_STOP_SECONDS = 300.0
BOOTSTRAP_TIMEOUT_SECONDS = 120.0
_PROBE_TIMEOUT = 2.0
_CONNECT_TIMEOUT = 30.0
_REPLY_ERRORS = {
    1: "défaillance générale", 2: "connexion interdite", 3: "réseau injoignable", 4: "hôte injoignable",
    5: "connexion refusée", 6: "durée de vie expirée", 7: "commande non prise en charge", 8: "type d'adresse refusé",
}
_LISTENER_RE = re.compile(r"Opened Socks listener connection \(ready\) on 127\.0\.0\.1:(\d+)")


class TorUnavailable(urllib.error.URLError):
    """Tor est activé mais aucun proxy ne répond et aucun programme `tor` ne peut être lancé, ou il a échoué."""


def parse_proxy(value: str) -> tuple[str, int]:
    """`hôte:port` (IPv6 entre crochets) ; lève ValueError si l'adresse est invalide."""
    host, sep, port_text = value.strip().rpartition(":")
    host = host.strip("[]")
    if not sep or not host or not port_text.isdigit() or not 1 <= int(port_text) <= 65535:
        raise ValueError("adresse du proxy Tor invalide (attendu hôte:port, par exemple 127.0.0.1:9050)")
    return host, int(port_text)


# --- SOCKS5 --------------------------------------------------------------------------------------------------------

def _recv_exact(sock: socket.socket, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise TorUnavailable("le proxy Tor a fermé la connexion")
        data += chunk
    return data


def open_socks_connection(proxy: tuple[str, int], host: str, port: int, timeout: float | None) -> socket.socket:
    try:
        sock = socket.create_connection(proxy, timeout=min(timeout or _CONNECT_TIMEOUT, _CONNECT_TIMEOUT))
    except OSError as exc:
        raise TorUnavailable(f"proxy Tor injoignable sur {proxy[0]}:{proxy[1]} ({exc})") from exc
    try:
        sock.settimeout(timeout)
        sock.sendall(b"\x05\x01\x00")
        if _recv_exact(sock, 2) != b"\x05\x00":
            raise TorUnavailable("le proxy n'accepte pas une connexion SOCKS5 sans authentification")
        try:
            address = ipaddress.ip_address(host)
            target = (b"\x01" if address.version == 4 else b"\x04") + address.packed
        except ValueError:
            encoded = host.encode("idna")
            target = b"\x03" + bytes([len(encoded)]) + encoded
        sock.sendall(b"\x05\x01\x00" + target + struct.pack(">H", port))
        _, status, _, atyp = _recv_exact(sock, 4)
        if status != 0:
            raise TorUnavailable(f"le proxy Tor refuse la connexion à {host} : {_REPLY_ERRORS.get(status, status)}")
        _recv_exact(sock, {1: 4, 4: 16}.get(atyp) or _recv_exact(sock, 1)[0])
        _recv_exact(sock, 2)
        return sock
    except BaseException:
        sock.close()
        raise


class _SocksHTTPConnection(http.client.HTTPConnection):
    def __init__(self, *args: Any, proxy: tuple[str, int], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._socks_proxy = proxy

    def connect(self) -> None:
        self.sock = open_socks_connection(self._socks_proxy, self.host, self.port, self.timeout)


class _SocksHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *args: Any, proxy: tuple[str, int], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._socks_proxy = proxy

    def connect(self) -> None:
        sock = open_socks_connection(self._socks_proxy, self.host, self.port, self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class _SocksHTTPHandler(urllib.request.HTTPHandler):
    def __init__(self, proxy: tuple[str, int]) -> None:
        super().__init__()
        self._proxy = proxy

    def http_open(self, req: urllib.request.Request):
        return self.do_open(lambda host, **kw: _SocksHTTPConnection(host, proxy=self._proxy, **kw), req)


class _SocksHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, proxy: tuple[str, int]) -> None:
        super().__init__(context=ssl.create_default_context())
        self._proxy = proxy

    def https_open(self, req: urllib.request.Request):
        return self.do_open(
            lambda host, **kw: _SocksHTTPSConnection(host, proxy=self._proxy, **kw), req, context=self._context,
        )


def build_opener(proxy: tuple[str, int]) -> urllib.request.OpenerDirector:
    # ProxyHandler vide : un proxy HTTP des variables d'environnement ne doit pas court-circuiter Tor.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _SocksHTTPHandler(proxy), _SocksHTTPSHandler(proxy))


def _proxy_answers(proxy: tuple[str, int]) -> bool:
    try:
        with socket.create_connection(proxy, timeout=_PROBE_TIMEOUT) as sock:
            sock.settimeout(_PROBE_TIMEOUT)
            sock.sendall(b"\x05\x01\x00")
            return sock.recv(2) == b"\x05\x00"
    except OSError:
        return False


# --- Tor lancé à la demande ----------------------------------------------------------------------------------------

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
    """Le Tor lancé par Bobine ne survit pas à Bobine, même après un arrêt brutal."""
    import ctypes
    import signal

    ctypes.CDLL(None).prctl(1, signal.SIGTERM)  # PR_SET_PDEATHSIG


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


_on_demand = _OnDemandTor()


# --- Réglage et sessions -------------------------------------------------------------------------------------------

_config_lock = threading.Lock()
_enabled = False
_proxy_setting = DEFAULT_PROXY


def configure(enabled: bool, proxy: str | None) -> None:
    """Reflète les réglages persistés (démarrage et chaque écriture)."""
    global _enabled, _proxy_setting
    with _config_lock:
        _enabled, _proxy_setting = enabled, (proxy or DEFAULT_PROXY)
    if not enabled:
        _on_demand.stop()


def load_from_database(db) -> None:
    from app.models import Setting

    rows = {row.key: row.value for row in db.query(Setting).filter(Setting.key.in_([SETTING_ENABLED, SETTING_PROXY]))}
    configure(rows.get(SETTING_ENABLED) == "true", rows.get(SETTING_PROXY))


def is_enabled() -> bool:
    with _config_lock:
        return _enabled


def shutdown() -> None:
    _on_demand.stop()


class TorSession:
    """Proxy à utiliser pour une suite de requêtes ; le Tor lancé à la demande vit au moins jusqu'à `close()`."""

    def __init__(self, proxy_setting: str | None = None) -> None:
        with _config_lock:
            configured = proxy_setting or _proxy_setting
        self._owns_tor = False
        candidates = [parse_proxy(configured)]
        if configured == DEFAULT_PROXY:
            candidates.append(parse_proxy(TOR_BROWSER_PROXY))
        for candidate in candidates:
            if _proxy_answers(candidate):
                self.proxy = candidate
                self.source = "existing"
                return
        binary = find_tor_binary()
        if binary is None:
            raise TorUnavailable(
                f"aucun proxy Tor ne répond sur {configured} et le programme tor n'est pas installé "
                "(installez tor, ouvrez Tor Browser, ou Orbot sur Android)"
            )
        self.proxy = _on_demand.acquire(binary)
        self.source = "on_demand"
        self._owns_tor = True

    @property
    def address(self) -> str:
        return f"{self.proxy[0]}:{self.proxy[1]}"

    def open(self, req: urllib.request.Request | str, timeout: float):
        return build_opener(self.proxy).open(req, timeout=timeout)

    def close(self) -> None:
        if self._owns_tor:
            self._owns_tor = False
            _on_demand.release()

    def __enter__(self) -> "TorSession":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class _Response:
    """Réponse dont la fermeture rend la session Tor qui l'a produite."""

    def __init__(self, response: Any, session: TorSession) -> None:
        self._response, self._session = response, session

    def __getattr__(self, name: str) -> Any:
        return getattr(self._response, name)

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        try:
            self._response.close()
        finally:
            self._session.close()


def urlopen(req: urllib.request.Request | str, timeout: float):
    """`urllib.request.urlopen`, par Tor quand l'option est active (sans repli direct)."""
    if not is_enabled():
        return urllib.request.urlopen(req, timeout=timeout)
    session = TorSession()
    try:
        return _Response(session.open(req, timeout=timeout), session)
    except BaseException:
        session.close()
        raise


def request_timeout(direct: float) -> float:
    """Délai d'une requête : un circuit Tor est plus lent qu'une connexion directe."""
    return max(direct, 60.0) if is_enabled() else direct


def check(proxy_setting: str | None = None, timeout: float = 60.0) -> dict[str, Any]:
    """Vérifie par le service de Tor que la sortie utilisée est bien un relais Tor."""
    try:
        with TorSession(proxy_setting) as session:
            req = urllib.request.Request(CHECK_URL, headers={"User-Agent": "Bobine-Updater/2.0 (+https://bobine.fit)"})
            with session.open(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return {"ok": bool(data.get("IsTor")), "is_tor": bool(data.get("IsTor")), "proxy": session.address,
                    "source": session.source}
    except (OSError, ValueError) as exc:
        return {"ok": False, "is_tor": False, "error": str(getattr(exc, "reason", exc))}
