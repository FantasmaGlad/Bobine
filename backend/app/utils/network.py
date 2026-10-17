"""Choix de l'adresse IPv4 à présenter pour joindre Bobine depuis le réseau local.

L'astuce « connecter une socket UDP vers 8.8.8.8 » renvoie l'interface de la
route par défaut. Dès qu'un VPN (WireGuard, OpenVPN, Tailscale...), un réseau
mobile ou un pont de conteneurs prend cette route, l'adresse affichée n'est
plus celle du Wi-Fi ou de l'Ethernet et ni le bandeau, ni les Réglages, ni
l'annonce mDNS ne sont joignables depuis un autre appareil. Ce module
énumère les interfaces actives, écarte les interfaces virtuelles et choisit
l'adresse privée d'une interface physique.

Module feuille : aucun import de `app.*`.
"""

import ipaddress
import os
import socket
from dataclasses import dataclass

# Adresse fournie par la couche native (Android : réseau Wi-Fi ou Ethernet lu
# via ConnectivityManager). Prioritaire : Python n'y énumère pas toujours les
# interfaces.
LAN_IP_ENV = "BOBINE_LAN_IP"

# Sous-chaînes (minuscules) de noms d'interface qui ne sont jamais le réseau
# local : bouclage, tunnels, VPN, conteneurs, machines virtuelles, réseau mobile.
_VIRTUAL_MARKERS = (
    "loopback", "tun", "tap", "wg", "ppp", "utun", "ipsec", "wireguard", "openvpn",
    "vpn", "proton", "nord", "mullvad", "tailscale", "zerotier", "zt", "hamachi",
    "docker", "veth", "br-", "virbr", "vmnet", "vboxnet", "vethernet", "hyper-v",
    "vmware", "virtualbox", "wsl", "bluetooth", "awdl", "llw", "anpi", "bridge",
    "gif", "stf", "dummy", "rmnet", "ccmni", "p2p", "lxc", "cni", "flannel",
)
# Préfixes d'interfaces physiques : Wi-Fi puis Ethernet, par ordre de préférence.
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
    # `wl*` (wlan0, wlp3s0) commence par "w" mais ne doit pas être pris pour
    # `wg*` : on teste les marqueurs sur le début du nom pour les préfixes
    # courts, et en sous-chaîne pour les noms longs.
    for marker in _VIRTUAL_MARKERS:
        if len(marker) <= 3:
            if lowered.startswith(marker):
                return True
        elif marker in lowered:
            return True
    return False


def _score(name: str, ip: str) -> int:
    """Plus le score est haut, plus l'adresse a de chances d'être celle du LAN."""
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
    """(interface, adresse) des interfaces IPv4 actives."""
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
    except Exception:
        pass
    # Sans psutil (profil Android) : ioctl SIOCGIFADDR sur Linux.
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
    except Exception:
        pass
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


def _route_ip() -> str | None:
    """Dernier recours : interface de la route par défaut (peut être un VPN)."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    probe.settimeout(0.2)
    try:
        probe.connect(("8.8.8.8", 80))
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
