"""Écrans branchés, par système : xrandr (Linux), API Windows, system_profiler (macOS)."""

from __future__ import annotations

import json
import logging
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Sequence


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


def _list_monitors_linux() -> list[Monitor]:
    xrandr = shutil.which("xrandr")
    if not xrandr:
        return []
    result = subprocess.run(
        [xrandr, "--listmonitors"], capture_output=True, text=True, timeout=5, check=False
    )
    return parse_xrandr_listmonitors(result.stdout)


def _list_monitors_windows() -> list[Monitor]:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    try:
        user32.SetProcessDPIAware()
    except Exception as exc:
        logger.debug("_list_monitors_windows : %s", exc)

    class RECT(ctypes.Structure):
        _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
            ("szDevice", wintypes.WCHAR * 32),
        ]

    MONITORINFOF_PRIMARY = 1
    found: list[Monitor] = []
    enum_proc_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HANDLE, wintypes.HDC, ctypes.POINTER(RECT), wintypes.LPARAM
    )

    def _callback(hmonitor, _hdc, _rect, _lparam):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            rect = info.rcMonitor
            found.append(
                Monitor(
                    name=str(info.szDevice),
                    x=int(rect.left),
                    y=int(rect.top),
                    width=int(rect.right - rect.left),
                    height=int(rect.bottom - rect.top),
                    primary=bool(info.dwFlags & MONITORINFOF_PRIMARY),
                )
            )
        return True

    user32.EnumDisplayMonitors(None, None, enum_proc_type(_callback), 0)
    return found


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


def _list_monitors_macos() -> list[Monitor]:
    result = subprocess.run(
        ["system_profiler", "SPDisplaysDataType", "-json"],
        capture_output=True, text=True, timeout=15, check=False,
    )
    return parse_macos_displays(result.stdout)


def list_monitors() -> list[Monitor]:
    """Moniteurs connectés ; liste vide si l'énumération est impossible (ne lève jamais)."""
    system = platform.system()
    try:
        if system == "Linux":
            return _list_monitors_linux()
        if system == "Windows":
            return _list_monitors_windows()
        if system == "Darwin":
            return _list_monitors_macos()
    except Exception as exc:  # pragma: no cover - dépend de l'OS
        logger.warning(f"Énumération des moniteurs impossible ({system}) : {exc}")
    return []


def external_monitors(monitors: Sequence[Monitor]) -> list[Monitor]:
    """Moniteurs EXTERNES = tous sauf le principal."""
    if len(monitors) <= 1:
        return []
    primary = next((m for m in monitors if m.primary), monitors[0])
    return [m for m in monitors if m is not primary and m != primary]
