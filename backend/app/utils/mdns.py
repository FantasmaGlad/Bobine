"""Répondeur mDNS embarqué (bibliothèque `zeroconf`), publiant `bobine.local` sur le réseau local."""

import logging
import platform
import socket
import threading
from pathlib import Path
from typing import Any

from app.utils.android_runtime import is_android
from app.utils.network import primary_lan_ip

logger = logging.getLogger(__name__)

MDNS_HOSTNAME = "bobine"

_REANNOUNCE_INTERVAL_SECONDS = 5 * 60
_RETRY_DELAYS_SECONDS = (2.0, 5.0, 10.0, 30.0, 60.0)
_AVAHI_SOCKET_PATH = Path("/var/run/avahi-daemon/socket")

_zeroconf = None
_service_info = None
_last_announced_ip: str | None = None
_state_lock = threading.Lock()
_stop_event = threading.Event()
_thread: threading.Thread | None = None
_status: dict[str, Any] = {"state": "pending", "detail": None}


def _set_status(state: str, detail: str | None = None) -> None:
    with _state_lock:
        _status["state"] = state
        _status["detail"] = detail


def get_status() -> dict[str, Any]:
    """État courant du répondeur mDNS — consommé par `GET /api/settings`."""
    with _state_lock:
        return dict(_status)


def _avahi_daemon_active() -> bool:
    try:
        return _AVAHI_SOCKET_PATH.exists()
    except OSError:
        return False


def _should_self_publish() -> bool:
    from app.utils.deployment import get_deployment_profile

    profile = get_deployment_profile()
    if profile == "linux-headless":
        return False
    if profile == "linux-desktop" and _avahi_daemon_active():
        return False
    return True


def _local_ip() -> str | None:
    return primary_lan_ip()


def _register_or_update(zc: Any, port: int) -> str:
    global _service_info, _last_announced_ip
    from zeroconf import ServiceInfo

    local_ip = _local_ip()
    if not local_ip:
        raise RuntimeError("aucune adresse IP locale résolvable pour le moment")

    with _state_lock:
        already_registered = _service_info is not None
        unchanged = already_registered and local_ip == _last_announced_ip

    if unchanged:
        return local_ip

    info = ServiceInfo(
        "_http._tcp.local.",
        "Bobine._http._tcp.local.",
        addresses=[socket.inet_aton(local_ip)],
        port=port,
        server=f"{MDNS_HOSTNAME}.local.",
    )
    if already_registered:
        zc.update_service(info)
    else:
        zc.register_service(info)
    with _state_lock:
        _service_info = info
        _last_announced_ip = local_ip
    return local_ip


def _run_loop(port: int) -> None:
    global _zeroconf

    try:
        from zeroconf import Zeroconf
    except ImportError:
        logger.warning("Bibliothèque 'zeroconf' absente — bobine.local ne sera pas publié par le backend.")
        _set_status("unavailable", "bibliothèque zeroconf absente")
        return

    zc = Zeroconf()
    with _state_lock:
        _zeroconf = zc

    attempt = 0
    while not _stop_event.is_set():
        try:
            announced_ip = _register_or_update(zc, port)
            platform_label = "Android" if is_android() else platform.system()
            if _status.get("state") != "ok":
                logger.info(f"mDNS : '{MDNS_HOSTNAME}.local' publié ({announced_ip}:{port}, profil {platform_label}).")
            _set_status("ok")
            attempt = 0
            if _stop_event.wait(_REANNOUNCE_INTERVAL_SECONDS):
                break
        except Exception as e:
            _set_status("failed", str(e))
            delay = _RETRY_DELAYS_SECONDS[min(attempt, len(_RETRY_DELAYS_SECONDS) - 1)]
            logger.warning(
                f"Échec de la publication mDNS (tentative {attempt + 1}) : {e!r} — nouvel essai dans {delay:.0f}s."
            )
            attempt += 1
            if _stop_event.wait(delay):
                break


def start_mdns_responder(port: int) -> None:
    """À appeler une fois au démarrage du backend (lifespan)."""
    global _thread
    if not _should_self_publish():
        from app.utils.deployment import get_deployment_profile

        state = "disabled" if get_deployment_profile() == "linux-headless" else "external"
        _set_status(state)
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_run_loop, args=(port,), daemon=True, name="bobine-mdns")
    _thread.start()


def stop_mdns_responder() -> None:
    global _zeroconf, _service_info, _last_announced_ip, _thread
    _stop_event.set()
    with _state_lock:
        zc, info = _zeroconf, _service_info
        _zeroconf, _service_info, _last_announced_ip = None, None, None
    if zc is not None:
        try:
            if info is not None:
                zc.unregister_service(info)
            zc.close()
        except Exception as e:
            logger.warning(f"Échec de l'arrêt propre du répondeur mDNS : {e!r}")
    _thread = None
