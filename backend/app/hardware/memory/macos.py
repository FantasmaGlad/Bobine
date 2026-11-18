import subprocess

from .fields import Found, keep


def read() -> Found:
    keys = {"Type:": "type", "Speed:": "freq", "Manufacturer:": "brand"}
    found: Found = {}
    for line in subprocess.check_output(["system_profiler", "SPMemoryDataType"], text=True, timeout=2).splitlines():
        line = line.strip()
        for prefix, field in keys.items():
            if line.startswith(prefix):
                keep(found, field, line.split(":", 1)[1].strip())
    found.setdefault("brand", "Apple")
    return found
