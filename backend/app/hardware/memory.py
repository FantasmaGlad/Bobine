"""Mémoire vive : marque, type, fréquence."""

import subprocess
import sys
from typing import Any

from .probe import _HARDWARE_CACHE, _get_android_prop, is_android_system, shutil_which


def get_ram_info() -> dict[str, Any]:
    """Retourne les informations matérielles détaillées de la mémoire vive."""
    if _HARDWARE_CACHE.get("ram_info"):
        return _HARDWARE_CACHE["ram_info"]

    brand = ""
    ram_type = ""
    freq = ""
    is_android = is_android_system()

    if is_android:
        soc_model = _get_android_prop("ro.soc.model").upper()
        dram_prop = _get_android_prop("ro.boot.dram_type") or _get_android_prop("ro.boot.ddr_type")
        if dram_prop:
            ram_type = dram_prop.upper()

        if any(s in soc_model for s in ("SM8750", "SM8735", "SUN")):
            ram_type = "LPDDR5X"
            freq = "8533 MT/s"
        elif any(s in soc_model for s in ("SM8650", "PINEAPPLE", "SM8635")):
            ram_type = "LPDDR5X"
            freq = "8533 MT/s"
        elif any(s in soc_model for s in ("SM8550", "KALAMA")):
            ram_type = "LPDDR5X"
            freq = "8533 MT/s"
        elif any(s in soc_model for s in ("SM8475", "SM8450", "TARO", "CAPE")):
            ram_type = "LPDDR5"
            freq = "6400 MT/s"

    if not brand and sys.platform.startswith("linux") and shutil_which("udevadm"):
        try:
            res = subprocess.run(
                ["udevadm", "info", "-p", "/devices/virtual/dmi/id"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if "MANUFACTURER=" in line and not brand:
                        val = line.split("=", 1)[1].strip()
                        if val and val.lower() not in ("not specified", "not available", "unknown", "n/a", "other", "none"):
                            brand = val
                    if "TYPE=" in line and not ram_type and "TYPE_DETAIL=" not in line:
                        val = line.split("=", 1)[1].strip()
                        if val and val.lower() not in ("unknown", "other", "none", "n/a"):
                            ram_type = val
                    if ("SPEED_MTS=" in line or "CONFIGURED_SPEED_MTS=" in line) and not freq:
                        val = line.split("=", 1)[1].strip()
                        if val.isdigit() and int(val) > 0:
                            freq = f"{val} MHz"
        except Exception:
            pass

    if (not brand or not ram_type or not freq) and shutil_which("dmidecode"):
        for cmd in (["dmidecode", "-t", "17"], ["sudo", "-n", "dmidecode", "-t", "17"]):
            try:
                out = subprocess.check_output(cmd, text=True, timeout=1, stderr=subprocess.DEVNULL)
                for line in out.splitlines():
                    sline = line.strip()
                    if sline.startswith("Manufacturer:") and not brand:
                        val = sline.split(":", 1)[1].strip()
                        if val and val.lower() not in ("not specified", "not available", "unknown", "n/a", "other", "none"):
                            brand = val
                    elif sline.startswith("Type:") and not ram_type and "Type Detail" not in sline:
                        val = sline.split(":", 1)[1].strip()
                        if val and val.lower() not in ("unknown", "other", "none", "n/a"):
                            ram_type = val
                    elif (sline.startswith("Speed:") or sline.startswith("Configured Memory Speed:")) and not freq:
                        val = sline.split(":", 1)[1].strip()
                        if val and not any(k in val.lower() for k in ("unknown", "configured")):
                            freq = val.replace("MT/s", "MHz").strip()
                if brand and ram_type and freq:
                    break
            except Exception:
                pass

    if sys.platform == "win32" and (not brand or not ram_type or not freq):
        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_PhysicalMemory | Select-Object -Property Manufacturer,SMBIOSMemoryType,Speed | ConvertTo-Json"],
                text=True,
                timeout=2,
            )
            import json
            data = json.loads(out)
            item = data[0] if isinstance(data, list) and data else data
            if isinstance(item, dict):
                if not brand and item.get("Manufacturer"):
                    b = str(item["Manufacturer"]).strip()
                    if b.lower() not in ("unknown", "not specified"):
                        brand = b
                if not freq and item.get("Speed"):
                    freq = f"{item['Speed']} MHz"
                if not ram_type and item.get("SMBIOSMemoryType"):
                    code = item["SMBIOSMemoryType"]
                    smbios_map = {24: "DDR3", 26: "DDR4", 30: "LPDDR4", 34: "DDR5", 35: "LPDDR5"}
                    if code in smbios_map:
                        ram_type = smbios_map[code]
        except Exception:
            pass

    if sys.platform == "darwin" and (not brand or not ram_type or not freq):
        try:
            out = subprocess.check_output(["system_profiler", "SPMemoryDataType"], text=True, timeout=2)
            for line in out.splitlines():
                sline = line.strip()
                if sline.startswith("Type:") and not ram_type:
                    ram_type = sline.split(":", 1)[1].strip()
                elif sline.startswith("Speed:") and not freq:
                    freq = sline.split(":", 1)[1].strip()
                elif sline.startswith("Manufacturer:") and not brand:
                    brand = sline.split(":", 1)[1].strip()
            if not brand:
                brand = "Apple"
        except Exception:
            pass

    parts = []
    if brand:
        parts.append(brand)
    if ram_type:
        parts.append(ram_type)
    if freq:
        parts.append(freq)

    model_label = " ".join(parts) if parts else "RAM Système"

    result = {
        "brand": brand or None,
        "type": ram_type or None,
        "freq": freq or None,
        "model_label": model_label,
    }
    _HARDWARE_CACHE["ram_info"] = result
    return result
