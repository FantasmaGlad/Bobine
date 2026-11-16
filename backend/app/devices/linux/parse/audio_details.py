"""Analyse pure du détail d'une sortie PipeWire : canaux, balance, profils, son de test."""

from __future__ import annotations

import math
from typing import Any

from app.api.contract import AUDIO_TEST_CHANNELS

from .audio import _props


def _cbrt(value: float) -> float:
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


def _latency_ms(props: dict[str, Any]) -> float | None:
    raw = str(props.get("node.latency") or props.get("node.max-latency") or "")
    if "/" not in raw:
        return None
    try:
        frames, hz = raw.split("/", 1)
        return round(1000.0 * int(frames) / int(hz), 1)
    except (ValueError, ZeroDivisionError):
        return None


def _profiles(device_params: dict[str, Any]) -> list[dict[str, Any]]:
    active = _first(device_params, "Profile")
    return [
        {
            "index": p.get("index"),
            "name": str(p.get("description") or p.get("name") or ""),
            "available": p.get("available") != "no",
            "active": p.get("index") == active.get("index"),
        }
        for p in device_params.get("EnumProfile", [])
        if isinstance(p, dict) and p.get("index") is not None and p.get("name") != "off"
    ]


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
    profiles = _profiles(device_params)
    channel_map = [str(c) for c in node_props.get("channelMap", [])] or _position_list(props.get("audio.position"))
    return {
        "id": device_id,
        "name": str(props.get("node.description") or props.get("node.nick") or device_id),
        "state": str((node.get("info") or {}).get("state") or "unknown"),
        "channels": int(props.get("audio.channels") or len(channel_map) or 0) or None,
        "channel_map": channel_map,
        "sample_rate": int(rate) if rate else None,
        "format": str(fmt.get("format")) if fmt.get("format") else None,
        "latency_ms": _latency_ms(props),
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
    """Tonalité de test stéréo (sinus avec fondu d'entrée et de sortie), un seul canal non silencieux au besoin."""
    import io
    import struct
    import wave

    if channel not in AUDIO_TEST_CHANNELS:
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
