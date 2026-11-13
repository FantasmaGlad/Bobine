import io
import json
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

from app import cli
import urllib.request
from app.cli import completion as cli_completion
from app.cli import config as cli_config

BACKEND = Path(__file__).resolve().parents[1]


class Recorder:

    def __init__(self, responses=None):
        self.calls = []
        self.responses = responses or {}

    def __call__(self, client, method, path, *, query=None, body=None, **kwargs):
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


def test_settings_get_unknown_key_is_an_error(monkeypatch, capsys):
    monkeypatch.setenv("BOBINE_PORT", "1903")
    monkeypatch.setattr(cli.Client, "request", lambda self, method, path, **kw: {"theme": "ciel"})
    assert cli.main(["settings", "get", "absente"]) == cli.EXIT_USAGE
    captured = capsys.readouterr()
    assert captured.out == "" and "réglage inconnu" in captured.err
    assert cli.main(["settings", "get", "theme"]) == cli.EXIT_OK
    assert capsys.readouterr().out == "ciel\n"


def test_config_export_to_a_file_is_a_clear_error(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("BOBINE_PORT", "1903")
    monkeypatch.setattr(cli.Client, "request", lambda self, method, path, **kw: {"files": {"settings.json": {}}})
    target = tmp_path / "destination"
    target.write_text("déjà un fichier", encoding="utf-8")
    assert cli.main(["config", "export", str(target)]) == cli.EXIT_ERROR
    assert "écriture impossible" in capsys.readouterr().err


def test_config_apply_is_a_dry_run_without_yes(recorder, tmp_path):
    (tmp_path / "settings.json").write_text('{"schema": 1, "kind": "settings", "settings": {}}', encoding="utf-8")
    cli.main(["config", "apply", str(tmp_path)])
    cli.main(["config", "apply", str(tmp_path / "settings.json"), "--yes", "--include-machine"])
    assert recorder.calls[0][2] == {"dry_run": "true", "include_machine": "false"}
    assert recorder.calls[1][2] == {"dry_run": "false", "include_machine": "true"}
    assert set(recorder.calls[0][3]["files"]) == {"settings.json"}


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


def _http_error(status, detail):
    body = io.BytesIO(json.dumps({"detail": detail}).encode())
    return urllib.error.HTTPError("http://127.0.0.1:1903/x", status, "refus", {}, body)


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


def test_library_lists_and_reads_videos(recorder, capsys):
    recorder.responses[("GET", "/api/videos")] = [
        {"id": 3, "title": "Lundi soir", "duration_seconds": 600},
        {"id": 4, "title": "Mardi", "duration_seconds": None},
    ]
    recorder.responses[("GET", "/api/videos/3")] = {"id": 3, "title": "Lundi soir"}
    assert cli.main(["library", "list", "--search", "Lundi", "--program", "RPM"]) == cli.EXIT_OK
    assert recorder.calls[0] == ("GET", "/api/videos", {
        "search": "Lundi", "program": "RPM", "sort_by": "imported_at", "order": "desc",
    }, None)
    assert capsys.readouterr().out.splitlines() == ["3  Lundi soir (10 min)", "4  Mardi"]
    assert cli.main(["library", "get", "3"]) == cli.EXIT_OK
    assert recorder.calls[1][:2] == ("GET", "/api/videos/3")
    assert capsys.readouterr().out == "3  Lundi soir\n"


def test_library_json_is_the_route_response(recorder, capsys):
    payload = [{"id": 3, "title": "Lundi soir"}]
    recorder.responses[("GET", "/api/videos")] = payload
    assert cli.main(["library", "list", "--json"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out) == payload


def test_launcher_recognizes_the_library_command():
    import run_tray

    assert run_tray._is_cli_invocation(["library", "list"])


def test_playlists_lists_and_reads_a_playlist(recorder, capsys):
    recorder.responses[("GET", "/api/playlists")] = [
        {"id": 1, "name": "Matin", "item_count": 2},
    ]
    recorder.responses[("GET", "/api/playlists/1")] = {
        "id": 1, "name": "Matin",
        "items": [{"video": {"id": 3, "title": "Lundi soir"}}],
    }
    assert cli.main(["playlists", "list"]) == cli.EXIT_OK
    assert recorder.calls[0][:2] == ("GET", "/api/playlists")
    assert capsys.readouterr().out == "1  Matin (2 élément(s))\n"
    assert cli.main(["playlists", "get", "1"]) == cli.EXIT_OK
    assert recorder.calls[1][:2] == ("GET", "/api/playlists/1")
    assert capsys.readouterr().out.splitlines() == ["1  Matin", "  3  Lundi soir"]


def test_playlists_json_is_the_route_response(recorder, capsys):
    payload = [{"id": 1, "name": "Matin"}]
    recorder.responses[("GET", "/api/playlists")] = payload
    assert cli.main(["playlists", "list", "--json"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out) == payload


def test_launcher_recognizes_the_playlists_command():
    import run_tray

    assert run_tray._is_cli_invocation(["playlists", "list"])


def test_schedule_lists_reads_and_reports_next(recorder, capsys):
    recorder.responses[("GET", "/api/schedule")] = [
        {"id": 7, "channel": "cable", "time_of_day": "18:30", "target_title": "Lundi soir", "active": True},
    ]
    recorder.responses[("GET", "/api/schedule/7")] = {
        "id": 7, "channel": "cable", "target_title": "Lundi soir", "schedule_type": "recurring",
        "active": True, "days_of_week": [0], "time_of_day": "18:30", "run_at": None,
    }
    recorder.responses[("GET", "/api/schedule/next")] = {"run_at": "2026-11-09T18:30:00Z", "title": "Lundi soir"}
    assert cli.main(["schedule", "list", "--channel", "cable"]) == cli.EXIT_OK
    assert recorder.calls[0][:3] == ("GET", "/api/schedule", {"channel": "cable"})
    assert capsys.readouterr().out == "#7  cable  18:30  Lundi soir  actif\n"
    assert cli.main(["schedule", "next", "--channel", "cable"]) == cli.EXIT_OK
    assert recorder.calls[1][:3] == ("GET", "/api/schedule/next", {"channel": "cable"})
    assert capsys.readouterr().out == "2026-11-09T18:30:00Z  Lundi soir\n"
    assert cli.main(["schedule", "get", "7"]) == cli.EXIT_OK
    assert recorder.calls[2][:2] == ("GET", "/api/schedule/7")
    assert "#7  cable  Lundi soir" in capsys.readouterr().out


def test_schedule_next_without_occurrence_is_success(recorder, capsys):
    recorder.responses[("GET", "/api/schedule/next")] = None
    assert cli.main(["schedule", "next", "--channel", "network"]) == cli.EXIT_OK
    assert capsys.readouterr().out == "Aucune occurrence à venir.\n"
    assert cli.main(["schedule", "next", "--json"]) == cli.EXIT_OK
    assert capsys.readouterr().out == "null\n"


def test_launcher_recognizes_the_schedule_command():
    import run_tray

    assert run_tray._is_cli_invocation(["schedule", "list"])


@pytest.mark.parametrize("action", ["status", "audio", "bluetooth", "wifi", "topology"])
def test_devices_reads_each_section(recorder, action):
    assert cli.main(["devices", action]) == cli.EXIT_OK
    assert recorder.calls[0][:2] == ("GET", f"/api/devices/{action}")


def test_devices_audio_summarizes_the_listing(recorder, capsys):
    recorder.responses[("GET", "/api/devices/audio")] = {
        "supported": True, "default_id": "hdmi",
        "devices": [{"id": "hdmi", "name": "HDMI", "is_default": True}],
    }
    assert cli.main(["devices", "audio"]) == cli.EXIT_OK
    assert capsys.readouterr().out.splitlines() == [
        "1 sortie(s) audio, défaut : hdmi",
        "  hdmi  HDMI (défaut)",
    ]


def test_devices_json_is_the_route_response(recorder, capsys):
    payload = {"platform": "linux", "driver": "pactl", "local": True, "capabilities": {}}
    recorder.responses[("GET", "/api/devices/status")] = payload
    assert cli.main(["devices", "status", "--json"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out) == payload


def test_launcher_recognizes_the_devices_command():
    import run_tray

    assert run_tray._is_cli_invocation(["devices", "wifi"])


@pytest.mark.parametrize("action", ["status", "volumes", "portable"])
def test_storage_reads_the_inventory(recorder, action):
    assert cli.main(["storage", action]) == cli.EXIT_OK
    assert recorder.calls[0][:2] == ("GET", f"/api/storage/{action}")


def test_storage_browse_passes_path_and_limit(recorder, capsys):
    recorder.responses[("GET", "/api/storage/volumes/u-1/browse")] = {
        "path": "Films", "total": 1,
        "entries": [{"type": "file", "path": "Films/a.mp4", "size": 12}],
    }
    assert cli.main(["storage", "browse", "u-1", "--path", "Films", "--limit", "20"]) == cli.EXIT_OK
    assert recorder.calls[0][:3] == (
        "GET", "/api/storage/volumes/u-1/browse", {"path": "Films", "limit": 20},
    )
    assert capsys.readouterr().out.splitlines() == [
        "Films (1 élément(s))", "  file  Films/a.mp4  12",
    ]


def test_storage_volumes_summarizes_the_listing(recorder, capsys):
    recorder.responses[("GET", "/api/storage/volumes")] = {
        "volumes": [{"key": "u-1", "name": "USB", "state": "mounted"}],
    }
    assert cli.main(["storage", "volumes"]) == cli.EXIT_OK
    assert capsys.readouterr().out.splitlines() == ["1 support(s)", "  u-1  USB  mounted"]


def test_launcher_recognizes_the_storage_command():
    import run_tray

    assert run_tray._is_cli_invocation(["storage", "volumes"])


def test_metrics_dashboard_passes_period_and_channel(recorder, capsys):
    recorder.responses[("GET", "/api/metrics/dashboard")] = {
        "period": "7d", "channel": "cable",
        "kpis": {"completion": {"rate": 80.0, "completed_sessions": 4}, "broadcast": {"total_hours": 2.5}, "sessions": {"total": 5}},
    }
    assert cli.main(["metrics", "dashboard", "--period", "7d", "--channel", "cable"]) == cli.EXIT_OK
    assert recorder.calls[0][:3] == ("GET", "/api/metrics/dashboard", {"period": "7d", "channel": "cable"})
    assert "sessions=5" in capsys.readouterr().out


def test_metrics_system_and_history(recorder, capsys):
    recorder.responses[("GET", "/api/settings/system")] = {
        "cpu_percent": 12.0, "cpu_temp_c": 45.0, "memory_percent": 30.0, "gpu_percent": 0.0, "power_watts": 7.0,
    }
    recorder.responses[("GET", "/api/metrics/hardware/history")] = {
        "label": "Charge CPU", "unit": "%", "current": 12.0, "min": 1.0, "max": 20.0, "avg": 8.0, "count": 3,
    }
    assert cli.main(["metrics", "system"]) == cli.EXIT_OK
    assert capsys.readouterr().out.startswith("CPU 12.0 % (45.0 °C)")
    assert cli.main(["metrics", "history", "--metric", "cpu", "--period", "24h"]) == cli.EXIT_OK
    assert recorder.calls[1][:3] == ("GET", "/api/metrics/hardware/history", {"metric": "cpu", "period": "24h"})
    assert "Charge CPU : 12.0 %" in capsys.readouterr().out


def test_metrics_json_is_the_route_response(recorder, capsys):
    payload = {"period": "all", "channel": "all", "kpis": {}}
    recorder.responses[("GET", "/api/metrics/dashboard")] = payload
    assert cli.main(["metrics", "dashboard", "--json"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out) == payload


def test_launcher_recognizes_the_metrics_command():
    import run_tray

    assert run_tray._is_cli_invocation(["metrics", "system"])


def test_imports_lists_and_cancels_jobs(recorder, capsys):
    recorder.responses[("GET", "/api/import-jobs")] = [
        {"id": "j1", "stage": "normalizing", "filename": "a.mp4", "progress_percent": 40},
    ]
    recorder.responses[("DELETE", "/api/import-jobs/j1")] = {"status": "cancelled", "job_id": "j1"}
    assert cli.main(["imports", "list"]) == cli.EXIT_OK
    assert recorder.calls[0][:2] == ("GET", "/api/import-jobs")
    assert capsys.readouterr().out == "j1  normalizing  a.mp4  40 %\n"
    assert cli.main(["imports", "cancel", "j1"]) == cli.EXIT_OK
    assert recorder.calls[1][:2] == ("DELETE", "/api/import-jobs/j1")
    assert capsys.readouterr().out == "Tâche j1 annulée.\n"


def test_imports_diagnose_exits_one_on_a_problem(recorder, capsys):
    recorder.responses[("GET", "/api/diagnostics/import")] = {"problems": ["disk_low"]}
    assert cli.main(["imports", "diagnose"]) == cli.EXIT_ERROR
    assert "disk_low" in capsys.readouterr().out
    recorder.responses[("GET", "/api/diagnostics/import")] = {"problems": []}
    assert cli.main(["imports", "diagnose"]) == cli.EXIT_OK
    assert capsys.readouterr().out == "Aucun problème détecté.\n"


def test_imports_json_is_the_route_response(recorder, capsys):
    payload = [{"id": "j1", "stage": "queued"}]
    recorder.responses[("GET", "/api/import-jobs")] = payload
    assert cli.main(["imports", "list", "--json"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out) == payload


def test_launcher_recognizes_the_imports_command():
    import run_tray

    assert run_tray._is_cli_invocation(["imports", "list"])


def test_display_reads_and_sets_outputs(recorder, capsys):
    recorder.responses[("GET", "/api/settings/display-output")] = {"cable": "kiosk", "network": "cinema"}
    recorder.responses[("PUT", "/api/settings/display-output")] = {"cable": "cinema", "network": "cinema"}
    assert cli.main(["display", "get"]) == cli.EXIT_OK
    assert recorder.calls[0][:2] == ("GET", "/api/settings/display-output")
    assert capsys.readouterr().out == "câblé=kiosk  réseau=cinema\n"
    assert cli.main(["display", "set", "cable", "cinema"]) == cli.EXIT_OK
    assert recorder.calls[1][:2] == ("PUT", "/api/settings/display-output")
    assert recorder.calls[1][3] == {"channel": "cable", "output": "cinema"}
    assert capsys.readouterr().out == "câblé=cinema  réseau=cinema\n"


def test_display_json_is_the_route_response(recorder, capsys):
    payload = {"cable": "kiosk", "network": "cinema"}
    recorder.responses[("GET", "/api/settings/display-output")] = payload
    assert cli.main(["display", "get", "--json"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out) == payload


def test_display_rejects_an_unknown_output():
    assert cli.main(["display", "set", "network", "radio"]) == cli.EXIT_USAGE


def test_launcher_recognizes_the_display_command():
    import run_tray

    assert run_tray._is_cli_invocation(["display", "get"])


def test_playback_and_radio_status_read_the_snapshot(recorder, capsys):
    recorder.responses[("GET", "/api/playback/state")] = {"state": "paused"}
    recorder.responses[("GET", "/api/radio/state")] = {"playing": True}
    assert cli.main(["playback", "cable", "status"]) == cli.EXIT_OK
    assert recorder.calls[0][:3] == ("GET", "/api/playback/state", {"channel": "cable"})
    assert capsys.readouterr().out == "cable : paused\n"
    assert cli.main(["radio", "network", "status", "--json"]) == cli.EXIT_OK
    assert recorder.calls[1][:3] == ("GET", "/api/radio/state", {"channel": "radio_network"})
    assert json.loads(capsys.readouterr().out) == {"playing": True}


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


def test_settings_set_json_is_the_server_answer(monkeypatch, capsys):
    monkeypatch.setattr(cli.Client, "request", lambda self, m, p, **kw: {"language": "en", "language_restart_required": True})
    cli.main(["--port", "1903", "--json", "settings", "set", "language=en"])
    assert json.loads(capsys.readouterr().out)["language_restart_required"] is True
    cli.main(["--port", "1903", "settings", "set", "language=en"])
    assert "redémarrage" in capsys.readouterr().out


def test_unknown_setting_is_a_usage_error(recorder):
    recorder.responses[("GET", "/api/settings")] = {"theme": "lune"}
    assert cli.main(["--port", "1903", "settings", "get", "zzz"]) == cli.EXIT_USAGE


def test_duplicate_config_file_names_are_refused(tmp_path):
    (tmp_path / "a").mkdir(); (tmp_path / "b").mkdir()
    for folder in ("a", "b"):
        (tmp_path / folder / "settings.json").write_text("{}", encoding="utf-8")
    with pytest.raises(cli.CliError) as error:
        cli_config._read_documents([str(tmp_path / "a"), str(tmp_path / "b")])
    assert error.value.code == cli.EXIT_USAGE


def test_recurring_schedule_shows_its_days(monkeypatch, capsys):
    monkeypatch.setattr(cli.Client, "request", lambda self, m, p, **kw: [
        {"id": 1, "channel": "cable", "time_of_day": "09:30", "days_of_week": [0, 2], "target_title": "Cours", "active": True}])
    cli.main(["--port", "1903", "schedule", "list"])
    assert "lun,mer 09:30" in capsys.readouterr().out

def test_config_documents_keep_their_place_in_the_tree(tmp_path):
    (tmp_path / "playlists").mkdir()
    (tmp_path / "playlists" / "video.json").write_text("{}", encoding="utf-8")
    (tmp_path / "settings.json").write_text("{}", encoding="utf-8")
    assert sorted(cli_config._read_documents([str(tmp_path)])) == ["playlists/video.json", "settings.json"]
    assert sorted(cli_config._read_documents([str(tmp_path / "playlists")])) == ["playlists/video.json"]
    assert sorted(cli_config._read_documents([str(tmp_path / "playlists" / "video.json")])) == ["playlists/video.json"]
    assert sorted(cli_config._read_documents([str(tmp_path / "settings.json")])) == ["settings.json"]


REPORT = {"status": "warning", "checks": [], "problems": [
    {"code": "import_job_stuck", "severity": "warning", "message": "bloqué", "remedy": "annuler",
     "fix": {"action": "cancel_import_jobs", "job_ids": ["abcdef0123456789"]}},
    {"code": "media_native_fallback", "severity": "info", "message": "inutilisé", "remedy": "désactiver",
     "fix": {"action": "set_settings", "settings": {"media_native": "false"}}},
    {"code": "firewall_rule_missing", "severity": "warning", "message": "règle absente", "remedy": "à la main"},
]}


def _scripted(monkeypatch, calls):
    answers = {"n": 0}

    def request(self, method, path, **kw):
        calls.append((method, path, kw.get("body")))
        if (method, path) == ("GET", "/api/diagnostics/system"):
            answers["n"] += 1
            return REPORT if answers["n"] == 1 else {"status": "warning", "checks": [], "problems": [REPORT["problems"][2]]}
        return {}

    monkeypatch.setattr(cli.Client, "request", request)


def test_auto_fix_without_yes_only_lists(monkeypatch, capsys):
    calls = []
    _scripted(monkeypatch, calls)
    assert cli.main(["--port", "1903", "diagnose", "--auto-fix"]) == cli.EXIT_ERROR
    out = capsys.readouterr().out
    assert "2 correction(s) possible(s)" in out and "--yes" in out
    assert [c for c in calls if c[0] != "GET"] == []


def test_auto_fix_yes_applies_only_the_declared_fixes(monkeypatch, capsys):
    calls = []
    _scripted(monkeypatch, calls)
    cli.main(["--port", "1903", "diagnose", "--auto-fix", "--yes"])
    writes = [c for c in calls if c[0] != "GET"]
    assert writes == [("DELETE", "/api/import-jobs/abcdef0123456789", None), ("PUT", "/api/settings", {"media_native": "false"})]
    out = capsys.readouterr().out
    assert "corrigé : import_job_stuck : import abcdef01 annulé" in out and "1 constat(s) restant(s)" in out


def test_diagnose_without_the_option_changes_nothing(monkeypatch):
    calls = []
    _scripted(monkeypatch, calls)
    cli.main(["--port", "1903", "diagnose"])
    assert [c for c in calls if c[0] != "GET"] == []


def test_unknown_fix_is_an_error_not_a_crash(monkeypatch, capsys):
    monkeypatch.setattr(cli.Client, "request", lambda self, m, p, **kw: {"status": "warning", "checks": [], "problems": [
        {"code": "x", "severity": "info", "message": "m", "remedy": "r", "fix": {"action": "inconnue"}}]})
    assert cli.main(["--port", "1903", "diagnose", "--auto-fix", "--yes"]) == cli.EXIT_ERROR
    assert "correction inconnue" in capsys.readouterr().err


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
