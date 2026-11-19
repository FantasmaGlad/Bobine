import io
import json
import subprocess
import sys
import urllib.error
import pytest
from app import cli
import urllib.request
from app.cli import completion as cli_completion
from cli_support import BACKEND, _http_error  # noqa: E402


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


def test_no_argument_prints_the_help(capsys):
    assert cli.main([]) == cli.EXIT_USAGE
    captured = capsys.readouterr()
    assert "usage: bobine" in captured.out and captured.err == ""


def test_global_options_are_kept_before_the_subcommand():
    args = cli.build_parser().parse_args(["--host", "192.0.2.1", "--port", "1234", "--json", "status"])
    assert (args.host, args.port, args.json) == ("192.0.2.1", 1234, True)


def test_invalid_ports_are_usage_errors(monkeypatch, capsys):
    monkeypatch.setenv("BOBINE_PORT", "abc")
    assert cli.main(["status"]) == cli.EXIT_USAGE
    assert "BOBINE_PORT invalide" in capsys.readouterr().err
    monkeypatch.setenv("BOBINE_PORT", "1903")
    assert cli.main(["status", "--port", "0"]) == cli.EXIT_USAGE
    assert "port invalide" in capsys.readouterr().err
    assert cli.main(["status", "--port", "70000"]) == cli.EXIT_USAGE


def test_exit_codes(recorder, capsys):
    assert cli.main(["diagnose"]) == cli.EXIT_ERROR
    assert cli.main(["update", "apply"]) == cli.EXIT_USAGE
    assert cli.main(["playback", "cable", "load", "sans-egal"]) == cli.EXIT_USAGE
    assert cli.main(["inconnue"]) == cli.EXIT_USAGE
    assert cli.main(["status"]) == cli.EXIT_OK


@pytest.mark.parametrize("raised, code, message", [
    (urllib.error.URLError("Connection refused"), cli.EXIT_UNREACHABLE, "injoignable"),
    (_http_error(409, {"code": "radio_locked", "message": "Le canal cable affiche la radio."}), cli.EXIT_REFUSED, "radio"),
    (_http_error(404, {"code": "unknown_action", "message": "Action inconnue(e) : x.", "allowed": ["play", "pause"]}), cli.EXIT_NOT_FOUND, "Admis : play, pause"),
    (_http_error(422, {"code": "invalid_config", "message": "Rien n'a été appliqué.", "errors": ["settings.json : thème"]}), cli.EXIT_USAGE, "- settings.json"),
])


def test_server_answers_map_to_exit_codes(monkeypatch, capsys, raised, code, message):
    def fail(*args, **kwargs):
        raise raised

    monkeypatch.setattr(urllib.request, "urlopen", fail)
    monkeypatch.setenv("BOBINE_PORT", "1903")
    assert cli.main(["playback", "cable", "play"]) == code
    captured = capsys.readouterr()
    assert captured.out == "" and message in captured.err


def test_validation_errors_are_printed_once_as_text(monkeypatch, capsys):
    detail = {"code": "invalid", "message": "volume : valeur trop grande", "errors": [{"loc": ["body", "volume"], "msg": "valeur trop grande"}]}
    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(_http_error(422, detail)))
    monkeypatch.setenv("BOBINE_PORT", "1903")
    assert cli.main(["playback", "cable", "play"]) == cli.EXIT_USAGE
    assert capsys.readouterr().err.strip() == "bobine : Refusé (422) : volume : valeur trop grande"


def test_health_503_reports_a_problem_not_a_refusal(monkeypatch, capsys):
    monkeypatch.setattr(cli.Client, "request", lambda self, method, path, **kw: {"status": "degraded"} if path == "/api/health" else {"state": "waiting"})
    assert cli.main(["status", "--port", "1903"]) == cli.EXIT_ERROR
    assert "degraded" in capsys.readouterr().out


def test_non_json_success_is_a_clear_error(monkeypatch, capsys):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def read(self):
            return b"<html>portail captif</html>"

    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: Response())
    assert cli.main(["status", "--port", "1903"]) == cli.EXIT_ERROR
    captured = capsys.readouterr()
    assert captured.out == "" and "non JSON" in captured.err


def test_json_goes_to_stdout_and_details_to_stderr(recorder, capsys):
    cli.main(["status", "--json", "-vv"])
    captured = capsys.readouterr()
    assert json.loads(captured.out)["health"] == {"status": "ok"}
    cli.main(["status", "-q"])
    assert capsys.readouterr().out == ""


def test_launcher_recognizes_global_options_before_the_command():
    import run_tray

    assert run_tray._is_cli_invocation(["--host", "192.0.2.1", "status"])
    assert run_tray._is_cli_invocation(["--json", "status"])
    assert run_tray._is_cli_invocation(["-vv", "logs"])
    assert not run_tray._is_cli_invocation(["--startup"])
    assert not run_tray._is_cli_invocation(["--minimized"])
    assert not run_tray._is_cli_invocation(["-psn_0_12345"])


def test_launcher_dispatches_without_loading_the_tray():
    probe = (
        "import runpy, sys; sys.argv = ['bobine', '--version']\n"
        "try:\n    runpy.run_path('run_tray.py', run_name='__main__')\n"
        "except SystemExit:\n    pass\n"
        "print('tray' if 'app.desktop.tray' in sys.modules else 'sans tray')\n"
    )
    result = subprocess.run([sys.executable, "-c", probe], cwd=BACKEND, capture_output=True, text=True, timeout=60)
    assert result.stdout.splitlines() == [f"bobine {cli.local_version()}", "sans tray"]


def test_path_segments_are_quoted(recorder):
    cli.main(["imports", "cancel", "../playlists/1?x=1"])
    assert recorder.calls[0][1] == "/api/import-jobs/..%2Fplaylists%2F1%3Fx%3D1"
    cli.main(["playback", "cable", "pa/use"])
    assert recorder.calls[1][1] == "/api/playback/cable/pa%2Fuse"


def test_unexpected_response_shape_is_a_message_not_a_traceback(monkeypatch, capsys):
    monkeypatch.setattr(cli.Client, "request", lambda self, method, path, **kw: None)
    assert cli.main(["--port", "1903", "library", "list"]) == cli.EXIT_ERROR
    err = capsys.readouterr().err
    assert "réponse inattendue" in err and "Traceback" not in err


@pytest.mark.parametrize("status, code", [(400, 2), (422, 2), (403, 4), (404, 5), (409, 4), (503, 4), (500, 1)])
def test_http_statuses_map_to_stable_exit_codes(monkeypatch, status, code):
    class Response:
        def __init__(self, body=b"{}"): self.body = body; self.status = status
        def read(self): return self.body
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, status, "x", {}, io.BytesIO(b'{"detail": "non"}'))

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert cli.main(["--port", "1903", "settings", "get"]) == code


def test_timeout_option_and_environment(monkeypatch):
    seen = {}

    def fake(req, timeout=None):
        seen["timeout"] = timeout
        raise OSError("fermé")

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    cli.main(["--port", "1903", "--timeout", "7", "status"])
    assert seen["timeout"] == 7
    monkeypatch.setenv("BOBINE_TIMEOUT", "11")
    cli.main(["--port", "1903", "status"])
    assert seen["timeout"] == 11
    cli.main(["--port", "1903", "status", "--timeout", "3.5"])
    assert seen["timeout"] == 3.5


@pytest.mark.parametrize("value", ["0", "-1", "abc", "99999"])
def test_invalid_timeout_is_a_usage_error(recorder, value):
    assert cli.main(["--port", "1903", "--timeout", value, "status"]) == cli.EXIT_USAGE


def test_completion_scripts_follow_the_parser(capsys):
    for shell in ("bash", "zsh", "fish"):
        assert cli.main(["completion", shell]) == cli.EXIT_OK
        script = capsys.readouterr().out
        assert all(name in script for name in ("diagnose", "playlists", "--auto-fix" if shell != "fish" else "auto-fix"))
    assert cli.main(["completion", "csh"]) == cli.EXIT_USAGE


def test_completion_bash_is_valid_shell(tmp_path, capsys):
    import shutil
    import subprocess

    if not shutil.which("bash"):
        pytest.skip("bash absent")
    cli.main(["completion", "bash"])
    script = tmp_path / "bobine.bash"
    script.write_text(capsys.readouterr().out, encoding="utf-8")
    assert subprocess.run(["bash", "-n", str(script)]).returncode == 0
    probe = subprocess.run(["bash", "-c", f'source {script}; COMP_WORDS=(bobine lib); COMP_CWORD=1; _bobine; echo "${{COMPREPLY[@]}}"'],
                           capture_output=True, text=True)
    assert probe.stdout.strip() == "library"


def test_every_command_is_listed_for_the_windows_launcher():
    parser_commands = set(cli_completion._command_tree(cli.build_parser())[1])
    assert parser_commands == set(cli.COMMANDS)


def test_short_version_flag(capsys):
    assert cli.main(["-V"]) == 0
    assert capsys.readouterr().out.startswith("bobine ")


def test_open_uses_the_real_port_and_the_requested_page(monkeypatch, capsys):
    import webbrowser

    opened = []
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url) or True)
    assert cli.main(["--port", "2024", "open", "grid"]) == 0
    assert opened == ["http://127.0.0.1:2024/grid"]
    assert cli.main(["--port", "2024", "open"]) == 0
    assert opened[-1] == "http://127.0.0.1:2024/"


def test_update_check_offline_is_a_failure(monkeypatch, capsys):
    offline = {"online": False, "error_code": "offline", "message": "Hors ligne", "has_update": False}
    monkeypatch.setattr(cli.Client, "request", lambda self, method, path, **kw: offline)
    monkeypatch.setenv("BOBINE_PORT", "1903")
    assert cli.main(["update", "check"]) == cli.EXIT_ERROR
    assert "Hors ligne" in capsys.readouterr().out


def test_filters_and_fields_of_the_api_are_reachable(recorder):
    recorder.responses[("GET", "/api/videos")] = []
    recorder.responses[("GET", "/api/storage/volumes/u-1/browse")] = {"path": "", "total": 0, "entries": []}
    assert cli.main(["library", "list", "--release", "42"]) == cli.EXIT_OK
    assert recorder.calls[-1][2]["release"] == "42"
    assert cli.main(["storage", "browse", "u-1", "--offset", "200", "--show-hidden", "--media-only"]) == cli.EXIT_OK
    assert recorder.calls[-1][2] == {"path": "", "limit": 200, "offset": 200, "show_hidden": "true", "media_only": "true"}
    assert cli.main(["audio", "set", "7", "--background-id", "3"]) == cli.EXIT_OK
    assert recorder.calls[-1] == ("PUT", "/api/audio/7", None, {"background_id": 3})
    assert cli.main(["radio-library", "set", "9", "--album-artist", "Divers", "--track-number", "2", "--tags", "cardio, force"]) == cli.EXIT_OK
    assert recorder.calls[-1] == ("PUT", "/api/radio/tracks/9", None, {"album_artist": "Divers", "track_number": 2, "tags": ["cardio", "force"]})
    assert cli.main(["audio", "set", "7"]) == cli.EXIT_USAGE
