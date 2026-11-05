"""Commande `bobine` : chaque commande appelle la même route que l'interface (parité), codes de sortie stables,
`--json` seul sur stdout, journaux sur stderr, démarrage sans charger l'icône système."""

import io
import json
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

from app import cli

BACKEND = Path(__file__).resolve().parents[1]


class Recorder:
    """Remplace le transport HTTP : note chaque appel et renvoie une réponse plausible."""

    def __init__(self, responses=None):
        self.calls = []
        self.responses = responses or {}

    def __call__(self, client, method, path, *, query=None, body=None):
        self.calls.append((method, path, query, body))
        for (m, p), payload in self.responses.items():
            if m == method and p == path:
                return payload
        return {"state": {"state": "playing"}}


@pytest.fixture()
def recorder(monkeypatch):
    rec = Recorder({
        ("GET", "/api/health"): {"status": "ok"},
        ("GET", "/api/playback/state"): {"state": "waiting"},
        ("GET", "/api/diagnostics/system"): {"status": "warning", "checks": [], "problems": [
            {"code": "port_fallback", "severity": "warning", "message": "port", "remedy": "libérer"},
        ]},
        ("GET", "/api/logs"): {"entries": [], "truncated": False},
        ("POST", "/api/config/apply"): {"applied": False, "changes": {}, "skipped": [], "restart_required": []},
        ("GET", "/api/updates/check"): {"has_update": False, "current_version": "5.1.0"},
    })
    monkeypatch.setattr(cli.Client, "request", lambda self, method, path, **kw: rec(self, method, path, **kw))
    monkeypatch.setenv("BOBINE_PORT", "1903")
    return rec


@pytest.mark.parametrize("argv, expected", [
    (["status"], [("GET", "/api/health"), ("GET", "/api/playback/state"), ("GET", "/api/playback/state")]),
    (["diagnose"], [("GET", "/api/diagnostics/system")]),
    (["logs", "--level", "error"], [("GET", "/api/logs")]),
    (["playback", "network", "volume", "volume=40"], [("POST", "/api/playback/network/volume")]),
    (["radio", "cable", "radio_next_track"], [("POST", "/api/radio/cable/radio_next_track")]),
    (["settings", "set", "theme=ciel"], [("PUT", "/api/settings")]),
    (["update", "check"], [("GET", "/api/updates/check")]),
])
def test_each_command_calls_the_interface_route(recorder, argv, expected):
    cli.main(argv)
    assert [(m, p) for m, p, _, _ in recorder.calls] == expected


def test_parameters_reach_the_route_typed(recorder):
    cli.main(["playback", "cable", "load", "video_id=12", "title=Lundi soir", "loop=true"])
    assert recorder.calls[0][3] == {"video_id": 12, "title": "Lundi soir", "loop": True}
    cli.main(["settings", "set", "auto_web_rendition=true"])
    assert recorder.calls[1][3] == {"auto_web_rendition": "true"}
    cli.main(["logs", "--level", "warning", "--since", "2026-11-05T08:00:00Z"])
    assert recorder.calls[2][2]["level"] == "warning" and recorder.calls[2][2]["since"] == "2026-11-05T08:00:00Z"


def test_config_apply_is_a_dry_run_without_yes(recorder, tmp_path):
    (tmp_path / "settings.json").write_text('{"schema": 1, "kind": "settings", "settings": {}}', encoding="utf-8")
    cli.main(["config", "apply", str(tmp_path)])
    cli.main(["config", "apply", str(tmp_path / "settings.json"), "--yes", "--include-machine"])
    assert recorder.calls[0][2] == {"dry_run": "true", "include_machine": "false"}
    assert recorder.calls[1][2] == {"dry_run": "false", "include_machine": "true"}
    assert set(recorder.calls[0][3]["files"]) == {"settings.json"}


def test_exit_codes(recorder, capsys):
    assert cli.main(["diagnose"]) == cli.EXIT_ERROR  # un problème trouvé
    assert cli.main(["update", "apply"]) == cli.EXIT_USAGE  # --yes exigé
    assert cli.main(["playback", "cable", "load", "sans-egal"]) == cli.EXIT_USAGE
    assert cli.main(["inconnue"]) == cli.EXIT_USAGE
    assert cli.main(["status"]) == cli.EXIT_OK


def _http_error(status, detail):
    body = io.BytesIO(json.dumps({"detail": detail}).encode())
    return urllib.error.HTTPError("http://127.0.0.1:1903/x", status, "refus", {}, body)


@pytest.mark.parametrize("raised, code, message", [
    (urllib.error.URLError("Connection refused"), cli.EXIT_UNREACHABLE, "injoignable"),
    (_http_error(409, {"code": "radio_locked", "message": "Le canal cable affiche la radio."}), cli.EXIT_REFUSED, "radio"),
    (_http_error(404, {"code": "unknown_action", "message": "Action inconnue(e) : x.", "allowed": ["play", "pause"]}), cli.EXIT_REFUSED, "Admis : play, pause"),
    (_http_error(422, {"code": "invalid_config", "message": "Rien n'a été appliqué.", "errors": ["settings.json : thème"]}), cli.EXIT_USAGE, "- settings.json"),
])
def test_server_answers_map_to_exit_codes(monkeypatch, capsys, raised, code, message):
    def fail(*args, **kwargs):
        raise raised

    monkeypatch.setattr(cli.urllib.request, "urlopen", fail)
    monkeypatch.setenv("BOBINE_PORT", "1903")
    assert cli.main(["playback", "cable", "play"]) == code
    captured = capsys.readouterr()
    assert captured.out == "" and message in captured.err


def test_json_goes_to_stdout_and_details_to_stderr(recorder, capsys):
    cli.main(["status", "--json", "-vv"])
    captured = capsys.readouterr()
    assert json.loads(captured.out)["health"] == {"status": "ok"}
    cli.main(["status", "-q"])
    assert capsys.readouterr().out == ""


def test_launcher_dispatches_without_loading_the_tray():
    probe = (
        "import runpy, sys; sys.argv = ['bobine', '--version']\n"
        "try:\n    runpy.run_path('run_tray.py', run_name='__main__')\n"
        "except SystemExit:\n    pass\n"
        "print('tray' if 'app.desktop.tray' in sys.modules else 'sans tray')\n"
    )
    result = subprocess.run([sys.executable, "-c", probe], cwd=BACKEND, capture_output=True, text=True, timeout=60)
    assert result.stdout.splitlines() == [f"bobine {cli.local_version()}", "sans tray"]
