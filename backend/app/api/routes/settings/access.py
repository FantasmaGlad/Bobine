"""Adresses d'accès annoncées à l'utilisateur : nom mDNS, adresse locale, liens exacts par interface."""

import socket
import time

from app.utils import port80
from app.utils.deployment import (
    get_profile_handler,
)
from app.utils.mdns import get_status as get_mdns_status
from app.utils.network import access_addresses, primary_lan_ip
from app.utils.port import active_port


def _port80_redirect() -> bool:
    return get_profile_handler().has_system_port80_redirect() or port80.is_active()


def _mdns_host() -> str:
    if get_mdns_status().get("state") == "external":
        return f"{socket.gethostname().split('.')[0].lower()}.local"
    return "bobine.local"


def _mdns_url() -> str:
    return f"http://{_mdns_host()}" if _port80_redirect() else f"http://{_mdns_host()}:{active_port()}"


def _access_links() -> list[dict[str, str]]:
    port = active_port()
    links = [{"kind": "loopback", "interface": "", "url": f"http://127.0.0.1:{port}"}]
    links += [{"kind": item["kind"], "interface": item["interface"], "url": f"http://{item['ip']}:{port}"} for item in access_addresses()]
    links.append({"kind": "mdns", "interface": "", "url": _mdns_url()})
    return links


_cached_local_ip: str | None = None
_cached_local_ip_time: float = 0.0
_LOCAL_IP_CACHE_TTL = 15.0


def _get_local_ip() -> str | None:
    global _cached_local_ip, _cached_local_ip_time
    now = time.time()
    if _cached_local_ip is not None and (now - _cached_local_ip_time) < _LOCAL_IP_CACHE_TTL:
        return _cached_local_ip

    detected = primary_lan_ip()
    if detected is not None:
        _cached_local_ip = detected
        _cached_local_ip_time = now
    else:
        _cached_local_ip = None
        _cached_local_ip_time = now - (_LOCAL_IP_CACHE_TTL - 3.0)
    return _cached_local_ip
