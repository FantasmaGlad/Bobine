"""Carte des périphériques : graphe « système solaire » (machine au centre) construit depuis l'état déjà
connu — sorties audio, appareils Bluetooth, Wi-Fi, Ethernet, écrans et télécommandes Bobine connectés.

`build_topology` est PUR (testable sans matériel). Les adresses IP des clients n'apparaissent que dans cette
réponse, protégée comme tout `/api/devices/*` (PIN).
"""

from __future__ import annotations

import ipaddress
import re
import socket
from typing import Any

# Interfaces virtuelles ou de tunnel : jamais présentées comme « le câble Ethernet » de la machine.
_VIRTUAL_IFACE = re.compile(r"^(lo|docker|veth|br-|virbr|lxc|lxd|tun|tap|wg|proton|ipv6leak|tailscale|zt|vmnet|vboxnet|utun|awdl|llw|bridge|anpi|ap\d)", re.I)

# Pages qui PILOTENT un canal (télécommandes) plutôt que de l'afficher.
REMOTE_PAGES = frozenset({"dashboard", "coach"})
# Pages exécutées sur l'écran de la machine elle-même quand l'adresse du client est locale.
RING_NETWORK, RING_DEVICES, RING_SCREENS = 1, 2, 3


def ethernet_interfaces(wifi_interface: str | None = None) -> list[dict[str, Any]]:
    """Interfaces filaires actives (hors Wi-Fi, boucle locale et interfaces virtuelles) avec adresse IPv4."""
    try:
        import psutil

        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()
    except Exception:
        return []
    found: list[dict[str, Any]] = []
    for name, stat in sorted(stats.items()):
        if not stat.isup or name == wifi_interface or _VIRTUAL_IFACE.match(name):
            continue
        if re.match(r"^(wl|wlan|wifi|wi-fi)", name, re.I):
            continue
        ipv4 = next((a for a in addrs.get(name, []) if a.family == socket.AF_INET and a.address), None)
        if ipv4 is None:
            continue
        subnet = None
        try:
            subnet = str(ipaddress.ip_interface(f"{ipv4.address}/{ipv4.netmask}").network) if ipv4.netmask else None
        except ValueError:
            subnet = None
        found.append({"name": name, "ip": ipv4.address, "subnet": subnet, "speed": stat.speed or None})
    return found


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def _in_subnet(ip: str, subnet: str | None) -> bool:
    if not subnet:
        return False
    try:
        return ipaddress.ip_address(ip.split("%")[0]) in ipaddress.ip_network(subnet)
    except ValueError:
        return False


def client_medium(ip: str, own_ips: frozenset[str], wifi_subnet: str | None, ethernet_subnets: list[str]) -> str:
    """Comment un client atteint la machine : `local` (même machine), `wifi`, `wired` ou `lan` (inconnu)."""
    if not ip or ip in own_ips or ip.startswith("127.") or ip in ("::1",):
        return "local"
    if _in_subnet(ip, wifi_subnet):
        return "wifi"
    if any(_in_subnet(ip, s) for s in ethernet_subnets):
        return "wired"
    return "lan"


def build_topology(
    *,
    machine: dict[str, Any],
    audio: dict[str, Any] | None,
    bluetooth: dict[str, Any] | None,
    wifi: dict[str, Any] | None,
    wifi_subnet: str | None,
    ethernets: list[dict[str, Any]],
    clients: list[dict[str, Any]],
    own_ips: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = [{
        "id": "machine", "kind": "machine", "label": machine.get("name") or "Bobine", "sub": machine.get("platform", ""),
        "state": "active", "ring": 0, "tab": None, "ref": None, "meta": {},
    }]
    links: list[dict[str, Any]] = []

    def add(node: dict[str, Any], link_from: str, medium: str, state: str, quality: float | None = None) -> None:
        nodes.append(node)
        links.append({"id": f"{link_from}>{node['id']}", "from": link_from, "to": node["id"], "medium": medium, "state": state, "quality": quality})

    # --- réseau -------------------------------------------------------
    wifi_node_id: str | None = None
    current = (wifi or {}).get("current") if (wifi or {}).get("supported") else None
    if current:
        wifi_node_id = "wifi"
        add({"id": "wifi", "kind": "wifi", "label": current.get("ssid") or "Wi-Fi", "sub": current.get("ip") or "", "state": "active",
             "ring": RING_NETWORK, "tab": "wifi", "ref": current.get("ssid"),
             "meta": {"signal": current.get("signal"), "band": current.get("band"), "security": current.get("security"), "ip": current.get("ip")}},
            "machine", "wifi", "active", (current.get("signal") or 0) / 100)
    eth_ids: list[tuple[str, str | None]] = []
    for eth in ethernets:
        node_id = f"eth:{eth['name']}"
        eth_ids.append((node_id, eth.get("subnet")))
        add({"id": node_id, "kind": "ethernet", "label": "Ethernet", "sub": eth.get("ip") or "", "state": "active", "ring": RING_NETWORK, "tab": None,
             "ref": None, "meta": {"interface": eth["name"], "ip": eth.get("ip"), "speed": eth.get("speed")}},
            "machine", "wired", "active")

    # --- appareils Bluetooth, puis sorties audio ------------------------
    bt_devices = [d for d in (bluetooth or {}).get("devices", []) if d.get("paired")] if (bluetooth or {}).get("supported") else []
    bt_names = {_normalize(d.get("name", "")): d["address"] for d in bt_devices}
    for d in bt_devices[:14]:
        connected = bool(d.get("connected"))
        add({"id": f"bt:{d['address']}", "kind": "bluetooth", "label": d.get("name") or d["address"], "sub": d.get("kind", ""), "state": "active" if connected else "idle",
             "ring": RING_DEVICES, "tab": "bluetooth", "ref": d["address"],
             "meta": {"address": d["address"], "profiles": d.get("profiles", []), "battery": d.get("battery"), "paired": True, "connected": connected, "device_kind": d.get("kind")}},
            "machine", "bluetooth", "active" if connected else "idle", None)
    for dev in ((audio or {}).get("devices", []) if (audio or {}).get("supported") else []):
        if dev.get("hidden"):
            continue
        if dev.get("kind") == "bluetooth":
            twin = bt_names.get(_normalize(dev.get("name", "")))
            if twin:  # le casque est déjà sur la carte : on note simplement qu'il est aussi une sortie audio
                for n in nodes:
                    if n["id"] == f"bt:{twin}":
                        n["meta"]["audio_id"] = dev["id"]
                        n["meta"]["audio_default"] = bool(dev.get("is_default"))
                continue
        medium = "bluetooth" if dev.get("kind") == "bluetooth" else ("internal" if dev.get("kind") in ("internal", "virtual") else "wired")
        add({"id": f"audio:{dev['id']}", "kind": "audio", "label": dev.get("alias") or dev.get("name") or dev["id"], "sub": dev.get("kind", ""),
             "state": "active" if dev.get("is_default") else "idle", "ring": RING_DEVICES, "tab": "audio", "ref": dev["id"],
             "meta": {"device_kind": dev.get("kind"), "default": bool(dev.get("is_default")), "volume": dev.get("volume"), "muted": dev.get("muted")}},
            "machine", medium, "active" if dev.get("is_default") else "idle")

    # --- écrans et télécommandes Bobine ---------------------------------
    eth_subnets = [s for _, s in eth_ids if s]
    for c in clients:
        page = str(c.get("page") or "viewer")
        channel = str(c.get("channel") or "")
        ip = str(c.get("ip") or "")
        medium = client_medium(ip, own_ips, wifi_subnet, eth_subnets)
        kind = "remote" if page in REMOTE_PAGES else "screen"
        node_id = f"client:{channel}:{page}:{ip}:{c.get('role')}"
        anchor = "machine"
        if medium == "wifi" and wifi_node_id:
            anchor = wifi_node_id
        elif medium == "wired" and eth_ids:
            anchor = eth_ids[0][0]
        link_medium = "wired" if medium == "local" else medium
        add({"id": node_id, "kind": kind, "label": page, "sub": ip or "local", "state": "active", "ring": RING_SCREENS, "tab": None, "ref": None,
             "meta": {"channel": channel, "page": page, "role": c.get("role"), "ip": ip, "count": c.get("count", 1), "medium": medium}},
            anchor, link_medium, "active")
    return {"nodes": nodes, "links": links, "counts": {"audio": sum(1 for n in nodes if n["kind"] == "audio"), "bluetooth": sum(1 for n in nodes if n["kind"] == "bluetooth"),
                                                       "screens": sum(1 for n in nodes if n["kind"] in ("screen", "remote"))}}
