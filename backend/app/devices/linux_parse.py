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


# ---------------------------------------------------------------------------
# Flux de lecture des applications (phase 2 : routage de la radio vers une sortie)
# ---------------------------------------------------------------------------

# Navigateurs susceptibles de jouer le lecteur /radio. PipeWire ne donne ni l'onglet ni l'URL : seule l'application
# est identifiable, d'où la prudence de `choose_browser_stream`.
_BROWSER_RE = re.compile(r"(chrom|firefox|brave|vivaldi|opera|msedge|microsoft-edge|epiphany|librewolf|waterfox|falkon|qutebrowser)", re.I)


def parse_output_streams(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flux de lecture (`Stream/Output/Audio`) d'un `pw-dump` : identifiant, application, état et sortie à laquelle
    chacun est relié (`sink`, nom de nœud PipeWire, ou None s'il n'est relié à aucune)."""
    names = {obj["id"]: _props(obj).get("node.name") for obj in data if str(obj.get("type", "")).endswith("Interface:Node")}
    linked: dict[int, int] = {}
    for obj in data:
        if str(obj.get("type", "")).endswith("Interface:Link"):
            props = _props(obj)
            out, inp = props.get("link.output.node"), props.get("link.input.node")
            if isinstance(out, int) and isinstance(inp, int):
                linked[out] = inp
    streams: list[dict[str, Any]] = []
    for obj in data:
        if not str(obj.get("type", "")).endswith("Interface:Node"):
            continue
        props = _props(obj)
        if props.get("media.class") != "Stream/Output/Audio":
            continue
        app = str(props.get("application.name") or "")
        binary = str(props.get("application.process.binary") or "")
        streams.append(
            {
                "id": obj["id"],
                "name": str(props.get("node.name") or ""),
                "app": app,
                "binary": binary,
                "browser": bool(_BROWSER_RE.search(f"{binary} {app}")),
                "state": str((obj.get("info") or {}).get("state") or ""),
                "sink": names.get(linked.get(obj["id"])),
            }
        )
    return streams


def choose_browser_stream(streams: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
    """Le flux du navigateur qui joue la radio : `("one", flux)` s'il y a EXACTEMENT un flux de navigateur en lecture,
    `("none", None)` s'il n'y en a aucun, `("ambiguous", None)` sinon. Jamais de devinette : déplacer le flux d'un
    autre onglet (vidéo, autre radio) serait pire que ne rien déplacer."""
    running = [s for s in streams if s["browser"] and s["state"] == "running"]
    if not running:
        return "none", None
    if len(running) > 1:
        return "ambiguous", None
    return "one", running[0]


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


# ---------------------------------------------------------------------------
# Détail d'une sortie audio (analyse, balance, profils)
# ---------------------------------------------------------------------------

import math  # noqa: E402


def _cbrt(value: float) -> float:
    """PipeWire stocke les volumes de canal en échelle cubique : le niveau affiché (wpctl) en est la racine cubique."""
    return math.copysign(abs(value) ** (1.0 / 3.0), value)


def _first(params: dict[str, Any], key: str) -> dict[str, Any]:
    items = (params or {}).get(key) or []
    return items[0] if items and isinstance(items[0], dict) else {}


def _position_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        return [part.strip() for part in value.strip("[] ").split(",") if part.strip()]
    return []


def balance_from_channel_volumes(volumes: list[float]) -> float | None:
    """Balance de -1 (gauche) à +1 (droite) depuis les volumes de canal cubiques ; seulement pour 2 canaux."""
    if len(volumes) != 2:
        return None
    left, right = (max(0.0, _cbrt(v)) for v in volumes)
    top = max(left, right)
    if top <= 0:
        return 0.0
    return round((right - left) / top, 3)


def channel_volumes_for_balance(volumes: list[float], balance: float) -> list[float]:
    """Nouveaux volumes de canal (cubiques) pour la balance demandée, niveau maître conservé."""
    level = max((max(0.0, _cbrt(v)) for v in volumes), default=0.0)
    balance = max(-1.0, min(1.0, balance))
    gain_left, gain_right = min(1.0, 1.0 - balance), min(1.0, 1.0 + balance)
    return [round((level * gain_left) ** 3, 6), round((level * gain_right) ** 3, 6)]


def find_sink_node(data: list[dict[str, Any]], device_id: str) -> dict[str, Any] | None:
    for obj in data:
        if str(obj.get("type", "")).endswith("Interface:Node") and _props(obj).get("node.name") == device_id:
            if _props(obj).get("media.class") == "Audio/Sink":
                return obj
    return None


def parse_audio_details(data: list[dict[str, Any]], device_id: str) -> dict[str, Any] | None:
    """Analyse complète d'une sortie depuis `pw-dump` (nœud + carte) ; None si la sortie a disparu."""
    node = find_sink_node(data, device_id)
    if node is None:
        return None
    props = _props(node)
    params = (node.get("info") or {}).get("params") or {}
    device_obj = next((o for o in data if o.get("id") == props.get("device.id")), None)
    device_props = _props(device_obj) if device_obj else {}
    device_params = ((device_obj or {}).get("info") or {}).get("params") or {}

    node_props = next((p for p in params.get("Props", []) if "channelVolumes" in p), {})
    volumes = [float(v) for v in node_props.get("channelVolumes", [])]
    fmt = _first(params, "Format")
    rate = fmt.get("rate") or props.get("audio.rate")
    latency_ms: float | None = None
    raw_latency = str(props.get("node.latency") or props.get("node.max-latency") or "")
    if "/" in raw_latency:
        try:
            frames, hz = raw_latency.split("/", 1)
            latency_ms = round(1000.0 * int(frames) / int(hz), 1)
        except (ValueError, ZeroDivisionError):
            latency_ms = None
    active = _first(device_params, "Profile")
    profiles = [
        {
            "index": p.get("index"),
            "name": str(p.get("description") or p.get("name") or ""),
            "available": p.get("available") != "no",
            "active": p.get("index") == active.get("index"),
        }
        for p in device_params.get("EnumProfile", [])
        if isinstance(p, dict) and p.get("index") is not None and p.get("name") != "off"
    ]
    channel_map = [str(c) for c in node_props.get("channelMap", [])] or _position_list(props.get("audio.position"))
    return {
        "id": device_id,
        "name": str(props.get("node.description") or props.get("node.nick") or device_id),
        "state": str((node.get("info") or {}).get("state") or "unknown"),
        "channels": int(props.get("audio.channels") or len(channel_map) or 0) or None,
        "channel_map": channel_map,
        "sample_rate": int(rate) if rate else None,
        "format": str(fmt.get("format")) if fmt.get("format") else None,
        "latency_ms": latency_ms,
        "card": str(props.get("api.alsa.card.name") or device_props.get("device.description") or ""),
        "bus": str(device_props.get("device.bus") or props.get("device.bus") or ""),
        "api": str(device_props.get("device.api") or props.get("device.api") or ""),
        "codec": str(props.get("api.bluez5.codec") or device_props.get("api.bluez5.codec") or "") or None,
        "profile": next((p for p in profiles if p["active"]), None),
        "profiles": profiles,
        "balance": balance_from_channel_volumes(volumes),
        "level": round(max((_cbrt(v) for v in volumes), default=0.0), 3) if volumes else None,
        "muted": node_props.get("mute"),
        "device_pw_id": props.get("device.id"),
        "node_pw_id": node.get("id"),
        "channel_volumes": volumes,
    }


def tone_wav_bytes(channel: str, seconds: float = 1.5, frequency: float = 440.0, rate: int = 48000, amplitude: float = 0.22) -> bytes:
    """Tonalité de test stéréo (sinus avec fondu d'entrée et de sortie), un seul canal non silencieux au besoin.
    Niveau volontairement bas (≈ -13 dBFS) ; le lecteur applique en plus son propre volume."""
    import io
    import struct
    import wave

    if channel not in ("left", "right", "both"):
        raise ValueError("canal inconnu")
    frames = int(seconds * rate)
    fade = int(0.08 * rate)
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        buffer = bytearray()
        for i in range(frames):
            envelope = min(1.0, i / fade, (frames - i) / fade)
            sample = int(32767 * amplitude * envelope * math.sin(2.0 * math.pi * frequency * i / rate))
            left = sample if channel in ("left", "both") else 0
            right = sample if channel in ("right", "both") else 0
            buffer += struct.pack("<hh", left, right)
        wav.writeframes(bytes(buffer))
    return out.getvalue()
