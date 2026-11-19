import re
import subprocess
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
BRANCH = re.compile(r"sys\.platform|platform\.system\(\)|os\.name\s*[!=]=")
REGISTRIES = {
    "app/hardware/platforms.py",
    "app/host/registry.py",
    "app/hardware/probe.py",
    "app/network/registry.py",
    "app/paths/registry.py",
    "app/process/lifecycle/registry.py",
    "app/process/priority/registry.py",
    "app/process/spawn/registry.py",
    "app/utils/android_runtime.py",
    "app/utils/deployment.py",
    "app/videos/encoding/registry.py",
}
PENDING = {
    "app/desktop/display_report.py": 1,
    "app/desktop/monitors.py": 1,
    "app/desktop/projector.py": 2,
    "app/desktop/tray_display.py": 4,
    "app/desktop/tray_install.py": 2,
    "app/desktop/tray_supervisor.py": 1,
    "app/desktop/tray_updates.py": 1,
}


def _branches() -> dict[str, int]:
    listing = subprocess.run(["git", "ls-files", "app"], cwd=BACKEND, capture_output=True, text=True, check=True)
    found = {}
    for name in listing.stdout.split():
        if name.endswith(".py") and name not in REGISTRIES:
            count = len(BRANCH.findall((BACKEND / name).read_text(encoding="utf-8")))
            if count:
                found[name] = count
    return found


def test_platform_branches_stay_in_registries():
    assert _branches() == PENDING, "choisir la plateforme dans un registre ; retirer de PENDING ce qui a été rangé"
