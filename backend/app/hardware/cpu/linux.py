import os

from .guard import guarded


def _cpuinfo_name() -> str:
    if not os.path.exists("/proc/cpuinfo"):
        return ""
    name = ""
    with open("/proc/cpuinfo", "r", encoding="utf-8") as handle:
        for line in handle:
            value = line.split(":", 1)[1].strip() if ":" in line else ""
            if "model name" in line and value:
                return value
            if ("Hardware" in line or "Processor" in line) and not name and value.lower() not in ("", "aarch64", "armv8", "armv7"):
                name = value
    return name


def cpu_name() -> str:
    return guarded(_cpuinfo_name)
