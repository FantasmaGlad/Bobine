"""Choix de l'adresse IPv4 à présenter pour joindre Bobine depuis le réseau local."""
import logging

import ipaddress
import os
import socket
from dataclasses import dataclass

logger = logging.getLogger(__name__)

LAN_IP_ENV = "BOBINE_LAN_IP"

_VIRTUAL_MARKERS = (
    "loopback", "tun", "tap", "wg", "ppp", "utun", "ipsec", "wireguard", "openvpn",
    "vpn", "proton", "nord", "mullvad", "tailscale", "zerotier", "zt", "hamachi",
    "docker", "veth", "br-", "virbr", "vmnet", "vboxnet", "vethernet", "hyper-v",
    "vmware", "virtualbox", "wsl", "bluetooth", "awdl", "llw", "anpi", "bridge",
    "gif", "stf", "dummy", "rmnet", "ccmni", "p2p", "lxc", "cni", "flannel",
)
_WIFI_PREFIXES = ("wlan", "wlp", "wlx", "wl", "wi-fi", "wifi", "en0", "wireless")
_WIRED_PREFIXES = ("eth", "eno", "ens", "enp", "enx", "en", "ethernet", "local area connection")

_CGNAT = ipaddress.ip_network("100.64.0.0/10")


@dataclass(frozen=True)
class LanAddress:
    ip: str
    interface: str
    score: int


def is_virtual_interface(name: str) -> bool:
    lowered = name.lower()
    for marker in _VIRTUAL_MARKERS:
        if len(marker) <= 3:
            if lowered.startswith(marker):
                return True
        elif marker in lowered:
            return True
    return False


def _score(name: str, ip: str) -> int:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return -1
    if address.is_loopback or address.is_link_local or address.is_unspecified or address.is_multicast:
        return -1
    if is_virtual_interface(name):
        return -1
    lowered = name.lower()
    if address in _CGNAT:
        base = 10
    elif address.is_private:
        base = 60
    else:
        base = 20
    if lowered.startswith(_WIFI_PREFIXES):
        base += 30
    elif lowered.startswith(_WIRED_PREFIXES):
        base += 40
    return base


def _enumerate_ipv4() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    try:
        import psutil

        stats = psutil.net_if_stats()
        for name, addrs in psutil.net_if_addrs().items():
            info = stats.get(name)
            if info is not None and not info.isup:
                continue
            for addr in addrs:
                if addr.family == socket.AF_INET and addr.address:
                    pairs.append((name, addr.address))
        return pairs
    except Exception as exc:
        logger.debug("_enumerate_ipv4 : %s", exc)
    try:
        import fcntl
        import struct

        for _index, name in socket.if_nameindex():
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                packed = fcntl.ioctl(probe.fileno(), 0x8915, struct.pack("256s", name[:15].encode()))
                pairs.append((name, socket.inet_ntoa(packed[20:24])))
            except OSError:
                continue
            finally:
                probe.close()
    except Exception as exc:
        logger.debug("_enumerate_ipv4 : %s", exc)
    return pairs


def lan_addresses() -> list[LanAddress]:
    """Adresses candidates, de la plus probable à la moins probable."""
    forced = os.environ.get(LAN_IP_ENV, "").strip()
    found: list[LanAddress] = []
    if forced:
        found.append(LanAddress(ip=forced, interface="native", score=1000))
    for name, ip in _enumerate_ipv4():
        score = _score(name, ip)
        if score >= 0 and all(ip != item.ip for item in found):
            found.append(LanAddress(ip=ip, interface=name, score=score))
    found.sort(key=lambda item: item.score, reverse=True)
    return found


_VPN_MARKERS = ("tailscale", "wg", "wireguard", "zerotier", "zt", "tun", "utun", "openvpn", "vpn", "nord", "proton", "mullvad", "hamachi")


def _is_vpn_interface(name: str) -> bool:
    lowered = name.lower()
    return any(lowered.startswith(marker) if len(marker) <= 3 else marker in lowered for marker in _VPN_MARKERS)


def access_addresses() -> list[dict[str, str]]:
    """Adresses par lesquelles un autre appareil peut joindre Bobine : réseau local (Wi-Fi, Ethernet) puis VPN."""
    found = [{"ip": item.ip, "interface": item.interface, "kind": "lan"} for item in lan_addresses()]
    known = {item["ip"] for item in found}
    for name, ip in _enumerate_ipv4():
        try:
            address = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if ip in known or address.is_loopback or address.is_link_local or not _is_vpn_interface(name):
            continue
        known.add(ip)
        found.append({"ip": ip, "interface": name, "kind": "vpn"})
    return found


def _route_ip() -> str | None:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    probe.settimeout(0.2)
    try:
        probe.connect(("192.0.2.1", 9))  # RFC 5737 : recherche de route, aucun paquet émis
        return probe.getsockname()[0]
    except OSError:
        return None
    finally:
        probe.close()


def primary_lan_ip() -> str | None:
    """Adresse à annoncer et à afficher, ou None sans réseau."""
    candidates = lan_addresses()
    if candidates:
        return candidates[0].ip
    return _route_ip()
