"""Recherche de mise à jour par Tor : réglage, session vers un proxy existant ou lancé, vérification."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from typing import Any

from app.utils import tor_daemon
from app.utils.tor_socks import TorUnavailable, build_opener, parse_proxy, proxy_answers

SETTING_ENABLED = "update_tor"


SETTING_PROXY = "update_tor_proxy"


DEFAULT_PROXY = "127.0.0.1:9050"


TOR_BROWSER_PROXY = "127.0.0.1:9150"


CHECK_URL = "https://check.torproject.org/api/ip"


_config_lock = threading.Lock()


_enabled = False


_proxy_setting = DEFAULT_PROXY


def configure(enabled: bool, proxy: str | None) -> None:
    """Reflète les réglages persistés (démarrage et chaque écriture)."""
    global _enabled, _proxy_setting
    with _config_lock:
        _enabled, _proxy_setting = enabled, (proxy or DEFAULT_PROXY)
    if not enabled:
        tor_daemon.on_demand.stop()


def load_from_database(db) -> None:
    from app.models import Setting

    rows = {row.key: row.value for row in db.query(Setting).filter(Setting.key.in_([SETTING_ENABLED, SETTING_PROXY]))}
    configure(rows.get(SETTING_ENABLED) == "true", rows.get(SETTING_PROXY))


def is_enabled() -> bool:
    with _config_lock:
        return _enabled


def shutdown() -> None:
    tor_daemon.on_demand.stop()


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
            if proxy_answers(candidate):
                self.proxy = candidate
                self.source = "existing"
                return
        binary = tor_daemon.find_tor_binary()
        if binary is None:
            raise TorUnavailable(
                f"aucun proxy Tor ne répond sur {configured} et le programme tor n'est pas installé "
                "(installez tor, ouvrez Tor Browser, ou Orbot sur Android)"
            )
        self.proxy = tor_daemon.on_demand.acquire(binary)
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
            tor_daemon.on_demand.release()

    def __enter__(self) -> "TorSession":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class _Response:

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
