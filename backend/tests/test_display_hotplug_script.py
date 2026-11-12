import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "bobine-display-hotplug.sh"


def _connector(root: Path, name: str, status: str):
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "status").write_text(status + "\n")


def _env(tmp: Path):
    fake = tmp / "systemctl"
    fake.write_text(f'#!/bin/sh\necho "$@" >> "{tmp}/calls"\n')
    fake.chmod(0o755)
    return {
        **os.environ,
        "BOBINE_DRM_ROOT": str(tmp / "drm"),
        "BOBINE_SIG_FILE": str(tmp / "sig"),
        "BOBINE_LOCK_FILE": str(tmp / "lock"),
        "BOBINE_DEBOUNCE": "0",
        "BOBINE_SYSTEMCTL": str(fake),
    }


def _run(env, *args):
    return subprocess.run(["sh", str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=20)


def _calls(tmp: Path):
    f = tmp / "calls"
    return f.read_text().splitlines() if f.exists() else []


def test_aucun_redemarrage_si_la_topologie_est_inchangee(tmp_path):
    drm = tmp_path / "drm"
    _connector(drm, "card0-HDMI-A-1", "connected")
    _connector(drm, "card0-DP-1", "disconnected")
    env = _env(tmp_path)
    assert _run(env, "--record").returncode == 0
    assert _run(env).returncode == 0
    assert _calls(tmp_path) == []


def test_branchement_d_un_projecteur_redemarre_le_kiosque_une_seule_fois(tmp_path):
    drm = tmp_path / "drm"
    _connector(drm, "card0-HDMI-A-1", "disconnected")
    _connector(drm, "card0-DP-1", "disconnected")
    env = _env(tmp_path)
    _run(env, "--record")
    _connector(drm, "card0-HDMI-A-1", "connected")
    _run(env)
    assert _calls(tmp_path) == ["try-restart bobine-kiosk.service"]
    _run(env)
    assert len(_calls(tmp_path)) == 1


def test_debranchement_puis_rebranchement(tmp_path):
    drm = tmp_path / "drm"
    _connector(drm, "card0-HDMI-A-1", "connected")
    env = _env(tmp_path)
    _run(env, "--record")
    _connector(drm, "card0-HDMI-A-1", "disconnected")
    _run(env)
    assert _calls(tmp_path) == []
    _connector(drm, "card0-HDMI-A-1", "connected")
    _run(env)
    assert _calls(tmp_path) == ["try-restart bobine-kiosk.service"]


def test_changement_de_sortie_connectee_redemarre(tmp_path):
    drm = tmp_path / "drm"
    _connector(drm, "card0-HDMI-A-1", "connected")
    _connector(drm, "card0-DP-1", "disconnected")
    env = _env(tmp_path)
    _run(env, "--record")
    _connector(drm, "card0-HDMI-A-1", "disconnected")
    _connector(drm, "card0-DP-1", "connected")
    _run(env)
    assert len(_calls(tmp_path)) == 1


def test_sans_reference_enregistree_aucune_action_destructrice(tmp_path):
    drm = tmp_path / "drm"
    _connector(drm, "card0-HDMI-A-1", "connected")
    env = _env(tmp_path)
    assert _run(env).returncode == 0
