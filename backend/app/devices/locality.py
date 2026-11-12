"""Provenance d'une requête : la machine elle-même (écran physique) ou un autre appareil du réseau."""
from __future__ import annotations

import ipaddress
import logging
import time

import psutil

logger = logging.getLogger(__name__)

_own_ips_cache: tuple[float, frozenset[str]] = (0.0, frozenset())
_OWN_IPS_TTL = 30.0


def normalize_ip(host: str | None) -> str | None:
    if not host:
        return None
    try:
        addr = ipaddress.ip_address(host.split("%")[0])
    except ValueError:
        return None
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    return str(addr)


def own_ip_addresses() -> frozenset[str]:
    """Adresses de cette machine (boucle locale + interfaces) : une requête qui en vient est locale, même quand le navigateur de l'écran physique passe par le nom d'hôte (bobine.local → IP du réseau)."""
    global _own_ips_cache
    now = time.monotonic()
    if now - _own_ips_cache[0] < _OWN_IPS_TTL and _own_ips_cache[1]:
        return _own_ips_cache[1]
    found: set[str] = {"127.0.0.1", "::1"}
    try:
        for addrs in psutil.net_if_addrs().values():
            for addr in addrs:
                normalized = normalize_ip(addr.address)
                if normalized:
                    found.add(normalized)
    except Exception as exc:
        logger.debug("Énumération des interfaces impossible : %s", exc)
    _own_ips_cache = (now, frozenset(found))
    return _own_ips_cache[1]


def is_local_client(host: str | None) -> bool:
    normalized = normalize_ip(host)
    if normalized is None:
        return False
    addr = ipaddress.ip_address(normalized)
    return addr.is_loopback or normalized in own_ip_addresses()
