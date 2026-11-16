"""Analyse pure des objets BlueZ (GetManagedObjects) et des adresses Bluetooth."""

from __future__ import annotations

import re
from typing import Any


_BT_ICON_KIND = {
    "audio-headset": "headset",
    "audio-headphones": "headphones",
    "audio-card": "speaker",
    "audio-speakers": "speaker",
    "input-keyboard": "keyboard",
    "input-mouse": "mouse",
    "input-gaming": "gamepad",
    "phone": "phone",
    "computer": "computer",
}


_A2DP_SINK = "0000110b"


_HANDSFREE = "0000111e"


_HEADSET = "00001108"


def bluetooth_profiles(uuids: list[str]) -> list[str]:
    found: list[str] = []
    lowered = [u.lower() for u in uuids or []]
    if any(u.startswith(_A2DP_SINK) for u in lowered):
        found.append("A2DP")
    if any(u.startswith(_HANDSFREE) or u.startswith(_HEADSET) for u in lowered):
        found.append("HFP")
    return found


def parse_bluez_objects(objects: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    """`GetManagedObjects` (valeurs natives) → adaptateur + appareils."""
    adapter_path: str | None = None
    adapter: dict[str, Any] = {}
    for path, ifaces in sorted(objects.items()):
        if "org.bluez.Adapter1" in ifaces:
            adapter_path, adapter = path, ifaces["org.bluez.Adapter1"]
            break
    devices: list[dict[str, Any]] = []
    for path, ifaces in objects.items():
        dev = ifaces.get("org.bluez.Device1")
        if dev is None or (adapter_path and dev.get("Adapter") != adapter_path):
            continue
        battery = (ifaces.get("org.bluez.Battery1") or {}).get("Percentage")
        address = str(dev.get("Address", ""))
        devices.append(
            {
                "address": address,
                "name": str(dev.get("Alias") or dev.get("Name") or address),
                "paired": bool(dev.get("Paired", False)),
                "connected": bool(dev.get("Connected", False)),
                "trusted": bool(dev.get("Trusted", False)),
                "rssi": dev.get("RSSI"),
                "kind": _BT_ICON_KIND.get(str(dev.get("Icon", "")), "other"),
                "profiles": bluetooth_profiles(list(dev.get("UUIDs") or [])),
                "battery": int(battery) if battery is not None else None,
                "path": path,
            }
        )
    devices.sort(key=lambda d: (not d["connected"], not d["paired"], d["name"].lower()))
    return {
        "adapter_path": adapter_path,
        "powered": bool(adapter.get("Powered", False)),
        "discovering": bool(adapter.get("Discovering", False)),
        "adapter_name": str(adapter.get("Alias") or adapter.get("Name") or ""),
        "devices": devices,
    }


def bluez_device_path(adapter_path: str, address: str) -> str:
    return f"{adapter_path}/dev_{address.upper().replace(':', '_')}"


_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


def is_valid_mac(address: str) -> bool:
    return bool(_MAC_RE.fullmatch(address or ""))
