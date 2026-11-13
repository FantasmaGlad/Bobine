"""Mémoire vive : marque, type, fréquence."""
import json
import logging

import subprocess
import sys
from typing import Any, Callable

from .probe import _HARDWARE_CACHE, _get_android_prop, is_android_system, shutil_which

logger = logging.getLogger(__name__)

_BLANK_BRANDS = ("not specified", "not available", "unknown", "n/a", "other", "none")
_BLANK_TYPES = ("unknown", "other", "none", "n/a")
_SMBIOS_TYPES = {24: "DDR3", 26: "DDR4", 30: "LPDDR4", 34: "DDR5", 35: "LPDDR5"}
_SOC_MEMORY = (
    (("SM8750", "SM8735", "SUN", "SM8650", "PINEAPPLE", "SM8635", "SM8550", "KALAMA"), "LPDDR5X", "8533 MT/s"),
    (("SM8475", "SM8450", "TARO", "CAPE"), "LPDDR5", "6400 MT/s"),
)
_FIELDS = ("brand", "type", "freq")

Found = dict[str, str]


def _brand(value: str) -> str:
    return value if value and value.lower() not in _BLANK_BRANDS else ""


def _kind(value: str) -> str:
    return value if value and value.lower() not in _BLANK_TYPES else ""


def _keep(found: Found, field: str, value: str) -> None:
    if value and field not in found:
        found[field] = value


def _android() -> Found:
    soc = _get_android_prop("ro.soc.model").upper()
    dram = _get_android_prop("ro.boot.dram_type") or _get_android_prop("ro.boot.ddr_type")
    found = {"type": dram.upper()} if dram else {}
    for socs, kind, freq in _SOC_MEMORY:
        if any(s in soc for s in socs):
            return {"type": kind, "freq": freq}
    return found


def _udev() -> Found:
    res = subprocess.run(["udevadm", "info", "-p", "/devices/virtual/dmi/id"], capture_output=True, text=True, timeout=2)
    found: Found = {}
    if res.returncode != 0:
        return found
    for line in res.stdout.splitlines():
        value = line.split("=", 1)[1].strip() if "=" in line else ""
        if "MANUFACTURER=" in line:
            _keep(found, "brand", _brand(value))
        if "TYPE=" in line and "TYPE_DETAIL=" not in line:
            _keep(found, "type", _kind(value))
        if ("SPEED_MTS=" in line or "CONFIGURED_SPEED_MTS=" in line) and value.isdigit() and int(value) > 0:
            _keep(found, "freq", f"{value} MHz")
    return found


def _dmidecode_lines(out: str) -> Found:
    found: Found = {}
    for line in (raw.strip() for raw in out.splitlines()):
        value = line.split(":", 1)[1].strip() if ":" in line else ""
        if line.startswith("Manufacturer:"):
            _keep(found, "brand", _brand(value))
        elif line.startswith("Type:") and "Type Detail" not in line:
            _keep(found, "type", _kind(value))
        elif line.startswith(("Speed:", "Configured Memory Speed:")) and value \
                and not any(k in value.lower() for k in ("unknown", "configured")):
            _keep(found, "freq", value.replace("MT/s", "MHz").strip())
    return found


def _dmidecode() -> Found:
    found: Found = {}
    for command in (["dmidecode", "-t", "17"], ["sudo", "-n", "dmidecode", "-t", "17"]):
        out = _probe(lambda command=command: subprocess.check_output(command, text=True, timeout=1, stderr=subprocess.DEVNULL))
        found = {**_dmidecode_lines(out), **found} if out else found
        if all(found.get(f) for f in _FIELDS):
            break
    return found


def _windows() -> Found:
    query = "Get-CimInstance Win32_PhysicalMemory | Select-Object -Property Manufacturer,SMBIOSMemoryType,Speed | ConvertTo-Json"
    data = json.loads(subprocess.check_output(["powershell", "-NoProfile", "-Command", query], text=True, timeout=2))
    item = data[0] if isinstance(data, list) and data else data
    if not isinstance(item, dict):
        return {}
    found: Found = {}
    brand = str(item.get("Manufacturer") or "").strip()
    if brand and brand.lower() not in ("unknown", "not specified"):
        found["brand"] = brand
    if item.get("Speed"):
        found["freq"] = f"{item['Speed']} MHz"
    if item.get("SMBIOSMemoryType") in _SMBIOS_TYPES:
        found["type"] = _SMBIOS_TYPES[item["SMBIOSMemoryType"]]
    return found


def _macos() -> Found:
    keys = {"Type:": "type", "Speed:": "freq", "Manufacturer:": "brand"}
    found: Found = {}
    for line in subprocess.check_output(["system_profiler", "SPMemoryDataType"], text=True, timeout=2).splitlines():
        line = line.strip()
        for prefix, field in keys.items():
            if line.startswith(prefix):
                _keep(found, field, line.split(":", 1)[1].strip())
    found.setdefault("brand", "Apple")
    return found


def _probe(read: Callable[[], Any]) -> Any:
    try:
        return read()
    except Exception as exc:
        logger.debug("get_ram_info : %s", exc)
        return None


def _sources() -> list[tuple[Callable[[Found], bool], Callable[[], Found]]]:
    incomplete = lambda found: not all(found.get(f) for f in _FIELDS)  # noqa: E731
    return [
        (lambda found: is_android_system(), _android),
        (lambda found: not found.get("brand") and sys.platform.startswith("linux") and bool(shutil_which("udevadm")), _udev),
        (lambda found: incomplete(found) and bool(shutil_which("dmidecode")), _dmidecode),
        (lambda found: sys.platform == "win32" and incomplete(found), _windows),
        (lambda found: sys.platform == "darwin" and incomplete(found), _macos),
    ]


def get_ram_info() -> dict[str, Any]:
    """Retourne les informations matérielles détaillées de la mémoire vive."""
    if _HARDWARE_CACHE.get("ram_info"):
        return _HARDWARE_CACHE["ram_info"]
    found: Found = {}
    for wanted, source in _sources():
        if wanted(found):
            extra = _probe(source) or {}
            found = {**{k: v for k, v in extra.items() if v}, **{k: v for k, v in found.items() if v}}
    parts = [found[f] for f in _FIELDS if found.get(f)]
    result = {
        "brand": found.get("brand") or None,
        "type": found.get("type") or None,
        "freq": found.get("freq") or None,
        "model_label": " ".join(parts) if parts else "RAM Système",
    }
    _HARDWARE_CACHE["ram_info"] = result
    return result
