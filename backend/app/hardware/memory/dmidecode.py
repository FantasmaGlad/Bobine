import subprocess

from .common import probe
from .fields import FIELDS, Found, brand, keep, kind


def _lines(out: str) -> Found:
    found: Found = {}
    for line in (raw.strip() for raw in out.splitlines()):
        value = line.split(":", 1)[1].strip() if ":" in line else ""
        if line.startswith("Manufacturer:"):
            keep(found, "brand", brand(value))
        elif line.startswith("Type:") and "Type Detail" not in line:
            keep(found, "type", kind(value))
        elif line.startswith(("Speed:", "Configured Memory Speed:")) and value \
                and not any(k in value.lower() for k in ("unknown", "configured")):
            keep(found, "freq", value.replace("MT/s", "MHz").strip())
    return found


def read() -> Found:
    found: Found = {}
    for command in (["dmidecode", "-t", "17"], ["sudo", "-n", "dmidecode", "-t", "17"]):
        out = probe(lambda command=command: subprocess.check_output(command, text=True, timeout=1, stderr=subprocess.DEVNULL))
        found = {**_lines(out), **found} if out else found
        if all(found.get(f) for f in FIELDS):
            break
    return found
