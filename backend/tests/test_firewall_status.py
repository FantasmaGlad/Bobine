import subprocess

import pytest

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
    assert state["state"] == "rule_missing" and "remoteip=10.0.0.0/8" in state["remedy"]


def test_development_and_linux_are_not_checked():
    assert firewall.status("darwin", "/usr/bin/python3")["state"] == "not_checked"
    assert firewall.status("linux", "/usr/lib/bobine/BobineBackend")["state"] == "not_checked"


WIN_EXE = r"C:\Program Files\Bobine\BobineBackend.exe"


def _rule(enabled="Yes", program=WIN_EXE, remote="10.0.0.0/8,192.168.0.0/16"):
    return f"Rule Name: Bobine\nEnabled: {enabled}\nProgram: {program}\nRemoteIP: {remote}\nAction: Allow\n"


@pytest.mark.parametrize("output, state", [
    (_rule(), "allowed"),
    (_rule(enabled="No"), "rule_missing"),
    (_rule(remote="Any"), "rule_missing"),
    (_rule(program=r"C:\Autre\x.exe"), "rule_missing"),
])
def test_windows_rule_must_be_enabled_for_this_program_and_not_open_to_any(monkeypatch, output, state):
    monkeypatch.setattr(firewall, "_run", fake_run({"name=Bobine": (0, output)}))
    assert firewall.status("win32", WIN_EXE)["state"] == state
