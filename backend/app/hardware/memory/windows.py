import json
import subprocess

from .fields import Found

_SMBIOS_TYPES = {24: "DDR3", 26: "DDR4", 30: "LPDDR4", 34: "DDR5", 35: "LPDDR5"}


def read() -> Found:
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
