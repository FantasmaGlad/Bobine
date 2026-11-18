from ..cpu import get_cpu_model_name
from ..probe import shutil_which
from .common import output, probe

_DISPLAY_CLASSES = ("vga compatible controller", "3d controller", "display controller")


def _apu_name(cpu_model: str) -> str | None:
    if "w/" not in cpu_model:
        return None
    name = cpu_model.split("w/", 1)[1].strip()
    return f"AMD {name}" if not name.startswith("AMD ") and "Radeon" in name else name or None


def _lspci_label(raw: str) -> str:
    start, end = raw.find("["), raw.find("]", raw.find("["))
    if start < 0 or end < 0:
        return raw.split("(")[0].strip()
    label = raw[start + 1:end].strip()
    if not label:
        return raw.split("(")[0].strip()
    return f"Intel {label}" if "Intel" in raw and not label.lower().startswith("intel") else label


def _lspci_name() -> str | None:
    if not shutil_which("lspci"):
        return None
    for line in output(["lspci"]).splitlines():
        if any(kind in line.lower() for kind in _DISPLAY_CLASSES):
            return _lspci_label(line.split(":", 2)[-1].strip())
    return None


def name() -> str:
    cpu_model = get_cpu_model_name()
    name = _apu_name(cpu_model) or probe(_lspci_name)
    if name:
        return name
    return "Intel HD/UHD Graphics" if "Intel" in cpu_model else "GPU Inconnu"
