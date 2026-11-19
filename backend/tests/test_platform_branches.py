import re
import subprocess
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
BRANCH = re.compile(r"sys\.platform|platform\.system\(\)|os\.name\s*[!=]=")
REGISTRIES = {
    "app/desktop/system/registry.py",
    "app/hardware/platforms.py",
    "app/hardware/probe.py",
    "app/host/registry.py",
    "app/network/registry.py",
    "app/paths/registry.py",
    "app/process/lifecycle/registry.py",
    "app/process/priority/registry.py",
    "app/process/spawn/registry.py",
    "app/utils/android_runtime.py",
    "app/utils/deployment.py",
    "app/videos/encoding/registry.py",
}
PENDING: dict[str, int] = {}


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
