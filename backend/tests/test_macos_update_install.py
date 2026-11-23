import shlex

import pytest

from app.utils.deployment import UpdateUnsupported
from app.utils.deployment_profiles import macos


def _applescript_payload(command: list[str]) -> str:
    script = command[2]
    body = script[len('do shell script "'):script.index('" with prompt')]
    return body.replace('\\"', '"').replace("\\\\", "\\")


def test_admin_command_goes_through_the_macos_administrator_prompt():
    command = ["rsync", "-a", "/Volumes/Bobine 5/Bobine.app/", '/Applications/Bo"bine\\.app/']
    wrapped = macos.admin_command(command)
    assert wrapped[:2] == ["osascript", "-e"]
    assert wrapped[2].endswith("with administrator privileges")
    assert shlex.split(_applescript_payload(wrapped)) == command


@pytest.fixture
def mounted(monkeypatch, tmp_path):
    (tmp_path / "Bobine.app").mkdir()
    calls: list[list[str]] = []
    monkeypatch.setattr(macos, "_attach", lambda dmg: str(tmp_path))
    monkeypatch.setattr(macos, "_detach", lambda mount: calls.append(["detach"]))
    return calls


def test_signature_is_checked_then_the_app_is_replaced_with_authorisation(monkeypatch, mounted):
    monkeypatch.setattr(macos, "run_checked", lambda cmd, **kw: mounted.append(cmd))
    macos._install_from_image(macos.Path("x.dmg"), lambda *a, **k: None)
    assert mounted[0][:4] == ["codesign", "--verify", "--deep", "--strict"]
    assert mounted[1][0] == "osascript" and "rsync -a --delete" in mounted[1][2]
    assert mounted[-1] == ["detach"]


def test_an_invalid_signature_never_replaces_the_app(monkeypatch, mounted):
    def run(cmd, **kw):
        mounted.append(cmd)
        if cmd[0] == "codesign":
            raise RuntimeError("Commande échouée (codesign) : invalid signature")

    monkeypatch.setattr(macos, "run_checked", run)
    with pytest.raises(RuntimeError):
        macos._install_from_image(macos.Path("x.dmg"), lambda *a, **k: None)
    assert not any(cmd[0] == "osascript" for cmd in mounted)


def test_a_refused_prompt_is_reported_as_cancelled(monkeypatch, mounted):
    def run(cmd, **kw):
        if cmd[0] == "osascript":
            raise RuntimeError("Commande échouée (osascript, code 1) : execution error: User canceled. (-128)")

    monkeypatch.setattr(macos, "run_checked", run)
    with pytest.raises(UpdateUnsupported, match="autorisation administrateur"):
        macos._install_from_image(macos.Path("x.dmg"), lambda *a, **k: None)
