from .common import output

_VIRTUAL_ADAPTERS = ("virtual", "remote", "rdp", "basic display")


def name() -> str | None:
    out = output(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_VideoController).Name"], 2)
    names = [line.strip() for line in out.splitlines() if line.strip()]
    return next((n for n in names if not any(x in n.lower() for x in _VIRTUAL_ADAPTERS)), None)
