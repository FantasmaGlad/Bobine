import json

from app import cli
from app.cli import read as cli_read
from app.cli.core import CliError, EXIT_UNREACHABLE


def test_a_read_without_id_or_label_shows_its_fields(recorder, capsys):
    recorder.responses[("GET", "/api/settings/storage")] = {
        "total_bytes": 32000000000, "used_percent": 8.5, "storage_model": "Flash eMMC 5.1", "removable": False, "label": None,
    }
    assert cli.main(["settings", "storage"]) == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "Fait." not in out
    assert "used_percent : 8.5" in out
    assert "storage_model : Flash eMMC 5.1" in out
    assert "removable : non" in out
    assert "label : —" in out


def test_nested_reads_are_indented(recorder, capsys):
    recorder.responses[("GET", "/api/devices/mixer")] = {"radio_cable": {"master": 1.0, "music": 0.8}, "channels": [{"id": "a", "label": "Salle"}]}
    assert cli.main(["devices", "mixer"]) == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "radio_cable :\n  master : 1.0\n  music : 0.8" in out
    assert "channels (1) :\n  a  Salle" in out


def test_a_write_stays_short(recorder, capsys):
    recorder.responses[("POST", "/api/playback/interrupted/resume")] = {"resumed": True}
    assert cli.main(["interrupted", "resume"]) == cli.EXIT_OK
    assert capsys.readouterr().out.strip() == "Fait."


def test_missing_metrics_show_a_dash_not_none(recorder, capsys):
    recorder.responses[("GET", "/api/settings/system")] = {
        "cpu_percent": 34.3, "cpu_temp_c": None, "memory_percent": 72.1, "gpu_percent": None, "power_watts": 4.9,
    }
    assert cli.main(["metrics", "system"]) == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "None" not in out
    assert out.startswith("CPU 34.3 % (— °C)  RAM 72.1 %  GPU — %")


def test_both_lists_round_a_duration_the_same_way(recorder, capsys):
    recorder.responses[("GET", "/api/videos")] = [{"id": 1, "title": "Bodycombat 108", "duration_seconds": 3230.208}]
    recorder.responses[("GET", "/api/media")] = {"items": [{"kind": "video", "id": 1, "title": "Bodycombat 108", "duration_seconds": 3230.208, "available": True}], "total": 1}
    assert cli.main(["library", "list"]) == cli.EXIT_OK
    assert cli.main(["media", "list"]) == cli.EXIT_OK
    out = capsys.readouterr().out
    assert out.count("54 min") == 2
    assert "53 min" not in out


def test_version_names_the_client_and_the_target(recorder, capsys, monkeypatch):
    recorder.responses[("GET", "/api/health")] = {"status": "ok", "version": "5.2.2"}
    monkeypatch.setattr(cli_read, "local_version", lambda: "5.2.2-canary")
    assert cli.main(["version"]) == cli.EXIT_OK
    assert capsys.readouterr().out == "5.2.2-canary\nserveur 5.2.2\n"
    assert cli.main(["--json", "version"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out) == {"version": "5.2.2-canary", "server": "5.2.2"}


def test_version_still_answers_when_the_target_is_unreachable(monkeypatch, capsys):
    def unreachable(self, method, path, **kwargs):
        raise CliError("Bobine injoignable", EXIT_UNREACHABLE)

    monkeypatch.setattr(cli.Client, "request", unreachable)
    monkeypatch.setattr(cli_read, "local_version", lambda: "5.2.2")
    assert cli.main(["version"]) == cli.EXIT_OK
    assert capsys.readouterr().out == "5.2.2\nserveur injoignable\n"
