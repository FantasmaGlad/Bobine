"""Analyse pure des sorties nmcli en mode terse."""

from __future__ import annotations

import re
from typing import Any


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
            continue
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
