import subprocess

from .fields import Found, brand, keep, kind


def read() -> Found:
    res = subprocess.run(["udevadm", "info", "-p", "/devices/virtual/dmi/id"], capture_output=True, text=True, timeout=2)
    found: Found = {}
    if res.returncode != 0:
        return found
    for line in res.stdout.splitlines():
        value = line.split("=", 1)[1].strip() if "=" in line else ""
        if "MANUFACTURER=" in line:
            keep(found, "brand", brand(value))
        if "TYPE=" in line and "TYPE_DETAIL=" not in line:
            keep(found, "type", kind(value))
        if ("SPEED_MTS=" in line or "CONFIGURED_SPEED_MTS=" in line) and value.isdigit() and int(value) > 0:
            keep(found, "freq", f"{value} MHz")
    return found
