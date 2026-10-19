"""Analyse pure des sorties d'outils Linux (PipeWire, BlueZ, NetworkManager) — testable sans matériel."""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Audio (pw-dump + wpctl)
# ---------------------------------------------------------------------------


def _props(obj: dict[str, Any]) -> dict[str, Any]:
    return (obj.get("info") or {}).get("props") or {}


def audio_kind(node: dict[str, Any], device: dict[str, Any]) -> str:
    """Type de sortie : bluetooth | hdmi | usb | jack | internal | virtual | other."""
    haystack = " ".join(
        str(v).lower()
        for v in (
            node.get("node.name"),
            node.get("node.description"),
            node.get("api.alsa.pcm.id"),
            node.get("device.profile.name"),
            device.get("device.profile.name"),
            device.get("device.description"),
        )
        if v
    )
    api = str(device.get("device.api") or node.get("device.api") or "").lower()
    bus = str(device.get("device.bus") or node.get("device.bus") or "").lower()
    form = str(device.get("device.form-factor") or node.get("device.form-factor") or "").lower()
    if "bluez" in api or bus == "bluetooth" or str(node.get("node.name", "")).startswith("bluez_"):
        return "bluetooth"
    if "hdmi" in haystack or "displayport" in haystack:
        return "hdmi"
    if bus == "usb":
        return "usb"
    if form in ("headphone", "headphones", "headset", "handset", "hands-free"):
        return "jack"
    if "analog" in haystack and form not in ("internal", "speaker", "computer", "laptop"):
        return "jack"
    if form in ("internal", "speaker", "computer", "laptop", "") and api in ("alsa", "", "alsa-pcm"):
        return "internal" if bus in ("pci", "") or form == "internal" else "other"
    if "null" in haystack or api == "":
        return "virtual"
    return "other"


def parse_pw_dump(data: list[dict[str, Any]]) -> dict[str, Any]:
    """Sorties audio (sinks) d'un `pw-dump`, avec l'identifiant numérique PipeWire (pour wpctl)."""
    devices = {obj["id"]: _props(obj) for obj in data if str(obj.get("type", "")).endswith("Interface:Device")}
    default_name: str | None = None
    for obj in data:
        if not str(obj.get("type", "")).endswith("Interface:Metadata"):
            continue
        for entry in obj.get("metadata") or []:
            if entry.get("key") in ("default.audio.sink", "default.configured.audio.sink"):
                value = entry.get("value")
                name = value.get("name") if isinstance(value, dict) else value
                if isinstance(name, str) and (default_name is None or entry.get("key") == "default.audio.sink"):
                    default_name = name
    sinks: list[dict[str, Any]] = []
    for obj in data:
        if not str(obj.get("type", "")).endswith("Interface:Node"):
            continue
        props = _props(obj)
        if props.get("media.class") != "Audio/Sink":
            continue
        device = devices.get(props.get("device.id"), {})
        name = str(props.get("node.name") or obj["id"])
        description = str(props.get("node.description") or props.get("node.nick") or name)
        sinks.append(
            {
                "id": name,
                "pw_id": obj["id"],
                "name": description,
                "description": str(device.get("device.description") or device.get("device.product.name") or ""),
                "manufacturer": str(device.get("device.vendor.name") or ""),
                "kind": audio_kind(props, device),
                "is_default": name == default_name,
                "available": True,
            }
        )
    return {"sinks": sinks, "default_id": default_name}


_VOLUME_RE = re.compile(r"Volume:\s*([0-9.]+)(?:\s*\[(MUTED)\])?")


def parse_wpctl_volume(text: str) -> tuple[float | None, bool | None]:
    """`Volume: 0.40 [MUTED]` → (0.4, True)."""
    match = _VOLUME_RE.search(text or "")
    if not match:
        return None, None
    return float(match.group(1)), match.group(2) == "MUTED"


# ---------------------------------------------------------------------------
# Bluetooth (BlueZ ObjectManager, valeurs déjà « dévariantées »)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Wi-Fi (nmcli -t)
# ---------------------------------------------------------------------------


def split_terse(line: str) -> list[str]:
    """Découpe une ligne `nmcli -t` : `:` séparateur, `\\:` et `\\\\` échappés."""
    fields: list[str] = []
    current: list[str] = []
    escaped = False
    for ch in line:
        if escaped:
            current.append(ch)
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(ch)
    fields.append("".join(current))
    return fields


def wifi_band(freq_text: str) -> str:
    match = re.search(r"\d+", freq_text or "")
    if not match:
        return ""
    freq = int(match.group(0))
    if freq >= 5925:
        return "6 GHz"
    if freq >= 4900:
        return "5 GHz"
    return "2.4 GHz"


def parse_wifi_list(output: str, known_ssids: set[str]) -> list[dict[str, Any]]:
    """`nmcli -t -f IN-USE,SSID,SIGNAL,SECURITY,FREQ dev wifi list` → réseaux dédoublonnés par SSID."""
    best: dict[str, dict[str, Any]] = {}
    for line in (output or "").splitlines():
        fields = split_terse(line)
        if len(fields) < 5:
            continue
        in_use, ssid, signal, security, freq = (f.strip() for f in fields[:5])
        if not ssid:
            continue  # réseau masqué : non listé
        try:
            level = int(signal)
        except ValueError:
            level = 0
        entry = {
            "ssid": ssid,
            "signal": level,
            "security": security if security and security != "--" else "",
            "band": wifi_band(freq),
            "known": ssid in known_ssids,
            "in_use": in_use == "*",
        }
        previous = best.get(ssid)
        if previous is None:
            best[ssid] = entry
        else:
            winner = entry if level > previous["signal"] else previous
            best[ssid] = {**winner, "in_use": entry["in_use"] or previous["in_use"]}
    return sorted(best.values(), key=lambda n: (not n["in_use"], -n["signal"], n["ssid"].lower()))


def parse_known_wifi(output: str) -> list[dict[str, str]]:
    """`nmcli -t -f NAME,UUID,TYPE connection show` → connexions Wi-Fi enregistrées."""
    known: list[dict[str, str]] = []
    for line in (output or "").splitlines():
        fields = split_terse(line)
        if len(fields) >= 3 and fields[2].strip() in ("802-11-wireless", "wifi"):
            known.append({"name": fields[0], "uuid": fields[1]})
    return known


def parse_wifi_device(output: str) -> dict[str, str] | None:
    """`nmcli -t -f DEVICE,TYPE,STATE,CONNECTION dev status` → premier adaptateur Wi-Fi."""
    for line in (output or "").splitlines():
        fields = split_terse(line)
        if len(fields) >= 4 and fields[1] == "wifi":
            return {"device": fields[0], "state": fields[2], "connection": fields[3]}
    return None
