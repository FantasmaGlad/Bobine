"""Sonde du pare-feu : Bobine bloqué par le pare-feu de macOS ou règle Windows absente, avec la commande de réparation ;
installation de développement et Linux non vérifiés (lecture réservée à l'administrateur)."""
import subprocess

from app.utils import firewall

EXE_MAC = "/Applications/Bobine.app/Contents/MacOS/BobineBackend"


def fake_run(outputs):
    def run(command):
        for key, (code, text) in outputs.items():
            if key in command:
                return subprocess.CompletedProcess(command, code, stdout=text, stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
    return run


def test_macos_blocked_app_gets_the_exact_command(monkeypatch):
    monkeypatch.setattr(firewall.Path, "exists", lambda self: True)
    monkeypatch.setattr(firewall, "_run", fake_run({
        "--getglobalstate": (0, "Firewall is enabled. (State = 1)"),
        "--getblockall": (0, "Block all DISABLED!"),
        "--getappblocked": (0, f"The application {EXE_MAC} is blocked"),
    }))
    state = firewall.status("darwin", EXE_MAC)
    assert state["state"] == "blocked"
    assert f'--unblockapp "{EXE_MAC}"' in state["remedy"] and "setblockall" not in state["remedy"]


def test_macos_disabled_firewall_allows(monkeypatch):
    monkeypatch.setattr(firewall.Path, "exists", lambda self: True)
    monkeypatch.setattr(firewall, "_run", fake_run({"--getglobalstate": (0, "Firewall is disabled. (State = 0)")}))
    assert firewall.status("darwin", EXE_MAC)["state"] == "allowed"


def test_windows_missing_rule_is_reported_with_local_networks(monkeypatch):
    monkeypatch.setattr(firewall, "_run", fake_run({"name=Bobine": (1, "Aucune règle ne correspond")}))
    state = firewall.status("win32", r"C:\Program Files\Bobine\BobineBackend.exe")
    assert state["state"] == "rule_missing" and "remoteip=LocalSubnet" in state["remedy"]


def test_development_and_linux_are_not_checked():
    assert firewall.status("darwin", "/usr/bin/python3")["state"] == "not_checked"
    assert firewall.status("linux", "/usr/lib/bobine/BobineBackend")["state"] == "not_checked"
