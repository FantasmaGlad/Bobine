"""Écrans branchés, par système : xrandr (Linux), API Windows, system_profiler (macOS)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Sequence

from app.desktop import system


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Monitor:
    name: str
    x: int
    y: int
    width: int
    height: int
    primary: bool = False

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"


_XRANDR_MONITOR_RE = re.compile(
    r"^\s*\d+:\s+(?P<flags>[+*]*)(?P<name>\S+)\s+(?P<w>\d+)/\d+x(?P<h>\d+)/\d+\+(?P<x>-?\d+)\+(?P<y>-?\d+)"
)


def parse_xrandr_listmonitors(output: str) -> list[Monitor]:
    """Analyse la sortie de `xrandr --listmonitors` (pur, testable)."""
    monitors: list[Monitor] = []
    for line in output.splitlines():
        match = _XRANDR_MONITOR_RE.match(line)
        if not match:
            continue
        monitors.append(
            Monitor(
                name=match.group("name"),
                x=int(match.group("x")),
                y=int(match.group("y")),
                width=int(match.group("w")),
                height=int(match.group("h")),
                primary="*" in match.group("flags"),
            )
        )
    return monitors


_RESOLUTION_RE = re.compile(r"(\d+)\s*x\s*(\d+)")


def parse_macos_displays(profiler_json: str) -> list[Monitor]:
    """Analyse `system_profiler SPDisplaysDataType -json` (pur, testable)."""
    try:
        data = json.loads(profiler_json)
    except (ValueError, TypeError):
        return []
    monitors: list[Monitor] = []
    for gpu in data.get("SPDisplaysDataType", []) or []:
        for index, display in enumerate(gpu.get("spdisplays_ndrvs", []) or []):
            match = _RESOLUTION_RE.search(str(display.get("_spdisplays_resolution", "")))
            width, height = (int(match.group(1)), int(match.group(2))) if match else (0, 0)
            monitors.append(
                Monitor(
                    name=str(display.get("_name", f"display-{len(monitors)}")),
                    x=0,
                    y=0,
                    width=width,
                    height=height,
                    primary=str(display.get("spdisplays_main", "")).endswith("yes"),
                )
            )
    return monitors


def list_monitors() -> list[Monitor]:
    """Moniteurs connectés ; liste vide si l'énumération est impossible (ne lève jamais)."""
    try:
        return system.current().list_monitors()
    except Exception as exc:  # pragma: no cover - dépend de l'OS
        logger.warning(f"Énumération des moniteurs impossible ({system.system_name()}) : {exc}")
    return []


def external_monitors(monitors: Sequence[Monitor]) -> list[Monitor]:
    """Moniteurs EXTERNES = tous sauf le principal."""
    if len(monitors) <= 1:
        return []
    primary = next((m for m in monitors if m.primary), monitors[0])
    return [m for m in monitors if m is not primary and m != primary]
