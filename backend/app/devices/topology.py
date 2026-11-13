"""Carte des périphériques : graphe « système solaire »."""

from __future__ import annotations

import ipaddress
import re
import socket
from typing import Any

_VIRTUAL_IFACE = re.compile(r"^(lo|docker|veth|br-|virbr|lxc|lxd|tun|tap|wg|proton|ipv6leak|tailscale|zt|vmnet|vboxnet|utun|awdl|llw|bridge|anpi|ap\d)", re.I)

REMOTE_PAGES = frozenset({"dashboard", "coach"})
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


class _Graph:
    def __init__(self, machine: dict[str, Any]) -> None:
        self.nodes: list[dict[str, Any]] = [{
            "id": "machine", "kind": "machine", "label": machine.get("name") or "Bobine", "sub": machine.get("platform", ""),
            "state": "active", "ring": 0, "tab": None, "ref": None, "meta": {},
        }]
        self.links: list[dict[str, Any]] = []

    def add(self, node: dict[str, Any], link_from: str, medium: str, state: str, quality: float | None = None) -> None:
        self.nodes.append(node)
        self.links.append({"id": f"{link_from}>{node['id']}", "from": link_from, "to": node["id"], "medium": medium, "state": state, "quality": quality})

    def count(self, *kinds: str) -> int:
        return sum(1 for n in self.nodes if n["kind"] in kinds)


def _supported(probe: dict[str, Any] | None, key: str) -> list:
    return (probe or {}).get(key, []) if (probe or {}).get("supported") else []


def _add_wifi(graph: _Graph, wifi: dict[str, Any] | None) -> str | None:
    current = (wifi or {}).get("current") if (wifi or {}).get("supported") else None
    if not current:
        return None
    graph.add({"id": "wifi", "kind": "wifi", "label": current.get("ssid") or "Wi-Fi", "sub": current.get("ip") or "", "state": "active",
               "ring": RING_NETWORK, "tab": "wifi", "ref": current.get("ssid"),
               "meta": {"signal": current.get("signal"), "band": current.get("band"), "security": current.get("security"), "ip": current.get("ip")}},
              "machine", "wifi", "active", (current.get("signal") or 0) / 100)
    return "wifi"


def _add_ethernets(graph: _Graph, ethernets: list[dict[str, Any]]) -> list[tuple[str, str | None]]:
    ids = []
    for eth in ethernets:
        node_id = f"eth:{eth['name']}"
        ids.append((node_id, eth.get("subnet")))
        graph.add({"id": node_id, "kind": "ethernet", "label": "Ethernet", "sub": eth.get("ip") or "", "state": "active", "ring": RING_NETWORK,
                   "tab": None, "ref": None, "meta": {"interface": eth["name"], "ip": eth.get("ip"), "speed": eth.get("speed")}},
                  "machine", "wired", "active")
    return ids


def _add_bluetooth(graph: _Graph, bluetooth: dict[str, Any] | None) -> dict[str, str]:
    devices = [d for d in _supported(bluetooth, "devices") if d.get("paired")]
    for d in devices[:14]:
        state = "active" if d.get("connected") else "idle"
        graph.add({"id": f"bt:{d['address']}", "kind": "bluetooth", "label": d.get("name") or d["address"], "sub": d.get("kind", ""),
                   "state": state, "ring": RING_DEVICES, "tab": "bluetooth", "ref": d["address"],
                   "meta": {"address": d["address"], "profiles": d.get("profiles", []), "battery": d.get("battery"), "paired": True,
                            "connected": bool(d.get("connected")), "device_kind": d.get("kind")}},
                  "machine", "bluetooth", state, None)
    return {_normalize(d.get("name", "")): d["address"] for d in devices}


def _merge_bluetooth_audio(graph: _Graph, dev: dict[str, Any], bt_names: dict[str, str]) -> bool:
    twin = bt_names.get(_normalize(dev.get("name", ""))) if dev.get("kind") == "bluetooth" else None
    if not twin:
        return False
    for node in graph.nodes:
        if node["id"] == f"bt:{twin}":
            node["meta"]["audio_id"] = dev["id"]
            node["meta"]["audio_default"] = bool(dev.get("is_default"))
    return True


def _add_audio(graph: _Graph, audio: dict[str, Any] | None, bt_names: dict[str, str]) -> None:
    for dev in _supported(audio, "devices"):
        if dev.get("hidden") or _merge_bluetooth_audio(graph, dev, bt_names):
            continue
        kind = dev.get("kind")
        medium = "bluetooth" if kind == "bluetooth" else ("internal" if kind in ("internal", "virtual") else "wired")
        state = "active" if dev.get("is_default") else "idle"
        graph.add({"id": f"audio:{dev['id']}", "kind": "audio", "label": dev.get("alias") or dev.get("name") or dev["id"], "sub": dev.get("kind", ""),
                   "state": state, "ring": RING_DEVICES, "tab": "audio", "ref": dev["id"],
                   "meta": {"device_kind": kind, "default": bool(dev.get("is_default")), "volume": dev.get("volume"), "muted": dev.get("muted")}},
                  "machine", medium, state)


def _add_clients(graph: _Graph, clients: list[dict[str, Any]], own_ips: frozenset[str], wifi_subnet: str | None,
                 wifi_node: str | None, eth_ids: list[tuple[str, str | None]]) -> None:
    eth_subnets = [s for _, s in eth_ids if s]
    for c in clients:
        page, channel, ip = str(c.get("page") or "viewer"), str(c.get("channel") or ""), str(c.get("ip") or "")
        medium = client_medium(ip, own_ips, wifi_subnet, eth_subnets)
        anchor = "machine"
        if medium == "wifi" and wifi_node:
            anchor = wifi_node
        elif medium == "wired" and eth_ids:
            anchor = eth_ids[0][0]
        graph.add({"id": f"client:{channel}:{page}:{ip}:{c.get('role')}", "kind": "remote" if page in REMOTE_PAGES else "screen",
                   "label": page, "sub": ip or "local", "state": "active", "ring": RING_SCREENS, "tab": None, "ref": None,
                   "meta": {"channel": channel, "page": page, "role": c.get("role"), "ip": ip, "count": c.get("count", 1), "medium": medium}},
                  anchor, "wired" if medium == "local" else medium, "active")


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
    graph = _Graph(machine)
    wifi_node = _add_wifi(graph, wifi)
    eth_ids = _add_ethernets(graph, ethernets)
    bt_names = _add_bluetooth(graph, bluetooth)
    _add_audio(graph, audio, bt_names)
    _add_clients(graph, clients, own_ips, wifi_subnet, wifi_node, eth_ids)
    return {"nodes": graph.nodes, "links": graph.links,
            "counts": {"audio": graph.count("audio"), "bluetooth": graph.count("bluetooth"), "screens": graph.count("screen", "remote")}}
