import json
import pytest
from app import cli
from app.cli import config as cli_config


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
