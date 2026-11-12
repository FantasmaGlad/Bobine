"""Retour arrière d'une mise à jour de l'appliance : le backend arme un marqueur, le chien de garde confirme la
nouvelle version par le contrôle de santé ou restaure la précédente. Les commandes système sont simulées."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.deployment_profiles import linux_headless  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
HEALTHY = '{"status":"ok","version":"5.1.2","components":{"database":"ok","kiosk":true,"scheduler":"ok","frontend":"ok"}}'
BROKEN = '{"status":"ok","version":"5.1.2","components":{"database":"ok","kiosk":true,"scheduler":"down","frontend":"ok"}}'
OLDER = '{"status":"ok","components":{"database":"ok","kiosk":true}}'

pytestmark = pytest.mark.skipif(sys.platform == "win32" or shutil.which("bash") is None, reason="script de l'appliance Linux")


@pytest.fixture
def appliance(tmp_path):
    """Copie du chien de garde dans un faux dépôt, avec des commandes système qui notent leurs appels."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "backend").mkdir()
    (repo / "frontend").mkdir()
    shutil.copy(ROOT / "scripts/watchdog.sh", repo / "scripts/watchdog.sh")
    stubs = tmp_path / "bin"
    stubs.mkdir()
    calls = tmp_path / "calls.log"

    def stub(name: str, body: str) -> None:
        path = stubs / name
        path.write_text(f'#!/bin/sh\necho "{name} $*" >> "{calls}"\n{body}\n', encoding="utf-8")
        path.chmod(0o755)

    # `curl -w '%{http_code}'` (santé simple) rend le code ; sans `-w`, le corps de la réponse.
    stub("curl", 'case "$*" in *http_code*) printf "%s" "${FAKE_HTTP_CODE:-200}" ;; *) printf "%s" "$FAKE_HEALTH" ;; esac')
    stub("runuser", 'shift 3; exec "$@"')  # runuser -u <propriétaire> -- commande…
    for name in ("systemctl", "logger", "git", "npm", "pgrep"):
        stub(name, "exit 0")

    def run(health: str, http_code: str = "200") -> list[str]:
        env = {**os.environ, "PATH": f"{stubs}:{os.environ['PATH']}", "FAKE_HEALTH": health, "FAKE_HTTP_CODE": http_code}
        subprocess.run(["bash", str(repo / "scripts/watchdog.sh")], env=env, check=True, timeout=30)
        return calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []

    return repo, run


def _arm(repo: Path, deadline_offset: int, pid: int | None = None) -> Path:
    marker = repo / "backend" / linux_headless.PENDING_UPDATE_FILE
    payload = {"previous_ref": "V5.1.1", "deadline": int(time.time()) + deadline_offset}
    if pid is not None:
        payload["pid"] = pid
    marker.write_text(json.dumps(payload), encoding="utf-8")
    return marker


def test_backend_arms_the_rollback_before_restarting(tmp_path):
    (tmp_path / "backend").mkdir()
    linux_headless.write_pending_update(tmp_path, "abc123")
    marker = json.loads((tmp_path / "backend" / linux_headless.PENDING_UPDATE_FILE).read_text(encoding="utf-8"))
    assert marker["previous_ref"] == "abc123"
    assert marker["pid"] == os.getpid()
    assert 0 < marker["deadline"] - time.time() <= linux_headless.UPDATE_CONFIRMATION_SECONDS


def test_a_healthy_new_version_is_confirmed(appliance):
    repo, run = appliance
    marker = _arm(repo, deadline_offset=-10)
    calls = run(HEALTHY)
    assert not marker.exists()
    assert not any(call.startswith("git ") for call in calls)


def test_the_old_backend_still_answering_does_not_confirm_the_update(appliance):
    repo, run = appliance
    (repo / "backend" / "backend-runtime.json").write_text(json.dumps({"port": 1903, "pid": 4242}), encoding="utf-8")
    marker = _arm(repo, deadline_offset=120, pid=4242)
    run(HEALTHY)
    assert marker.exists(), "l'ancien processus répond encore : la nouvelle version n'est pas confirmée"

    (repo / "backend" / "backend-runtime.json").write_text(json.dumps({"port": 1903, "pid": 4243}), encoding="utf-8")
    run(HEALTHY)
    assert not marker.exists()


def test_an_unhealthy_version_keeps_its_delay_then_is_rolled_back(appliance):
    repo, run = appliance
    marker = _arm(repo, deadline_offset=120)
    calls = run(BROKEN, http_code="503")
    assert marker.exists(), "avant l'échéance, le nouveau backend garde sa chance"
    assert not any(call.startswith(("git ", "systemctl restart")) for call in calls)

    marker = _arm(repo, deadline_offset=-1)
    calls = run(BROKEN, http_code="503")
    assert not marker.exists()
    assert any(call.startswith("git ") and "checkout --quiet V5.1.1" in call for call in calls)
    assert any(call == "systemctl restart bobine-backend.service" for call in calls)
    assert any(call.startswith("npm run build") for call in calls)


def test_a_deliberate_downgrade_to_an_older_version_is_not_reverted(appliance):
    repo, run = appliance
    marker = _arm(repo, deadline_offset=-10)
    calls = run(OLDER)
    assert not marker.exists()
    assert not any(call.startswith("git ") for call in calls)


def test_a_stale_marker_is_dropped_without_rollback(appliance):
    repo, run = appliance
    marker = _arm(repo, deadline_offset=-7200)
    calls = run(BROKEN, http_code="503")
    assert not marker.exists()
    assert not any(call.startswith("git ") for call in calls)
