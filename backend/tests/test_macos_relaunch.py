"""Mise à jour macOS : après le remplacement du bundle, tout Bobine redémarre
(tray + backend) au lieu de laisser l'ancien tray superviser le nouveau backend.
Le script de relance est exécuté pour de vrai avec de faux processus et un faux
`open` : seul le lancement par macOS (`open`) n'est pas exercé sans Mac."""

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from app.utils.deployment_profiles import macos

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="script sh")


def _attendre(condition, delai=15.0):
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        if condition():
            return True
        time.sleep(0.1)
    return False


def test_le_script_est_valide_en_sh():
    res = subprocess.run(["sh", "-n"], input=macos._RELAUNCH_SCRIPT, text=True, capture_output=True)
    assert res.returncode == 0, res.stderr


def test_le_script_arrete_l_ancienne_version_puis_ouvre_le_bundle(tmp_path):
    app = tmp_path / "Bobine.app"
    macos_dir = app / "Contents" / "MacOS"
    macos_dir.mkdir(parents=True)
    # faux binaires du bundle : attendent, et portent leur chemin dans leur ligne de commande
    backend_bin = macos_dir / "BobineBackend"
    tray_bin = macos_dir / "BobineTray"
    for fake in (backend_bin, tray_bin):
        fake.write_text("#!/usr/bin/env python3\nimport sys, time\ntime.sleep(float(sys.argv[1]))\n")
        fake.chmod(0o755)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    marqueur = tmp_path / "open.txt"
    fake_open = bin_dir / "open"
    fake_open.write_text(f'#!/bin/sh\necho "$@" > "{marqueur}"\n')
    fake_open.chmod(0o755)

    tray = subprocess.Popen([str(tray_bin), "300"])
    # l'ancien backend (fils du tray) puis un nouveau, respawné par le superviseur
    backend_courant = subprocess.Popen([str(backend_bin), "0.5"])
    backend_respawn = subprocess.Popen([str(backend_bin), "300"])

    # en vrai, launchd récupère les orphelins ; ici le test les moissonne pour
    # qu'ils ne restent pas zombies (un zombie répond encore à `kill -0`)
    reapers = [threading.Thread(target=p.wait, daemon=True) for p in (tray, backend_courant, backend_respawn)]
    for t in reapers:
        t.start()

    script = tmp_path / "relance.sh"
    script.write_text(macos._RELAUNCH_SCRIPT)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "BOBINE_APP": str(app),
        "BOBINE_BACKEND_BIN": str(backend_bin),
        "BOBINE_TRAY_PID": str(tray.pid),
        "BOBINE_BACKEND_PID": str(backend_courant.pid),
    }
    runner = subprocess.Popen(["sh", str(script)], env=env)
    try:
        assert _attendre(lambda: marqueur.exists()), "open n'a pas été appelé"
        assert marqueur.read_text().strip() == str(app)
        for t in reapers:
            t.join(timeout=5)
        assert tray.returncode == -signal.SIGTERM
        assert backend_respawn.returncode == -signal.SIGTERM
        assert runner.wait(timeout=5) == 0
        assert not script.exists(), "le script doit se supprimer"
    finally:
        for proc in (tray, backend_courant, backend_respawn, runner):
            if proc.poll() is None:
                proc.kill()


class _Appels:
    def __init__(self):
        self.popen = []
        self.sorties = 0


@pytest.fixture
def appels(monkeypatch, tmp_path):
    a = _Appels()
    monkeypatch.setattr(macos.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(macos.subprocess, "Popen", lambda *args, **kw: a.popen.append((args, kw)))
    monkeypatch.setattr(macos.MacOSHandler, "restart_services", lambda self: setattr(a, "sorties", a.sorties + 1))
    return a


def test_relance_lance_le_script_puis_quitte(appels, monkeypatch, tmp_path):
    monkeypatch.setattr(macos, "_is_bobine_tray", lambda pid: True)
    macos.MacOSHandler().relaunch_application()
    (args, kw), = appels.popen
    assert args[0] == ["sh", str(tmp_path / "bobine_relaunch_runner.sh")]
    assert kw["start_new_session"] is True
    assert kw["env"]["BOBINE_TRAY_PID"] == str(os.getppid())
    assert kw["env"]["BOBINE_BACKEND_PID"] == str(os.getpid())
    assert kw["env"]["BOBINE_APP"] == "/Applications/Bobine.app"
    assert kw["env"]["BOBINE_BACKEND_BIN"] == "/Applications/Bobine.app/Contents/MacOS/BobineBackend"
    # ni le chemin du backend ni le motif de pkill ne figurent dans la ligne de commande
    assert "BobineBackend" not in " ".join(args[0])
    assert appels.sorties == 1


def test_parent_inconnu_ne_tue_rien(appels, monkeypatch):
    monkeypatch.setattr(macos, "_is_bobine_tray", lambda pid: False)
    macos.MacOSHandler().relaunch_application()
    assert appels.popen == []
    assert appels.sorties == 1


def test_echec_du_script_retombe_sur_la_relance_du_backend(appels, monkeypatch):
    monkeypatch.setattr(macos, "_is_bobine_tray", lambda pid: True)

    def echec(*a, **k):
        raise OSError("sh introuvable")

    monkeypatch.setattr(macos.subprocess, "Popen", echec)
    macos.MacOSHandler().relaunch_application()
    assert appels.sorties == 1


def test_is_bobine_tray_lit_le_nom_du_parent(monkeypatch):
    class R:
        stdout = "/Applications/Bobine.app/Contents/MacOS/BobineTray\n"

    monkeypatch.setattr(macos.subprocess, "run", lambda *a, **k: R())
    assert macos._is_bobine_tray(1) is True
    R.stdout = "/bin/zsh\n"
    assert macos._is_bobine_tray(1) is False


def test_la_mise_a_jour_appelle_la_relance_et_non_la_simple_sortie():
    source = Path(macos.__file__).read_text(encoding="utf-8")
    fin = source.split("def apply_update")[1]
    assert "self.relaunch_application()" in fin
    assert "self.restart_services()" not in fin
