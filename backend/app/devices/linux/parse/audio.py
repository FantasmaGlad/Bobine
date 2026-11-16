"""Analyse pure des sorties PipeWire (pw-dump, wpctl) : sorties audio et flux."""

from __future__ import annotations

import re
from typing import Any


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


_BROWSER_RE = re.compile(r"(chrom|firefox|brave|vivaldi|opera|msedge|microsoft-edge|epiphany|librewolf|waterfox|falkon|qutebrowser)", re.I)


def parse_output_streams(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flux de lecture (`Stream/Output/Audio`) d'un `pw-dump` : identifiant, application, état et sortie à laquelle chacun est relié (`sink`, nom de nœud PipeWire, ou None s'il n'est relié à aucune)."""
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
    """Le flux du navigateur qui joue la radio : `("one", flux)` s'il y a EXACTEMENT un flux de navigateur en lecture, `("none", None)` s'il n'y en a aucun, `("ambiguous", None)` sinon."""
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
