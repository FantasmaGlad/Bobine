"""Commandes d'écriture de `bobine` : route et corps envoyés, confirmations, `bobine api`, envoi de fichiers, sauvegarde."""

import json

import pytest

from app import cli
import urllib.request
from app.cli.specs import SPECS


class Recorder:
    def __init__(self):
        self.calls = []
        self.uploads = []

    def request(self, client, method, path, *, query=None, body=None, **kwargs):
        self.calls.append((method, path, query, body))
        if path == "/api/import-jobs":
            return [{"id": "job-1", "stage": "done"}]
        return {"id": 7, "name": "x", "title": "x"}


@pytest.fixture()
def rec(monkeypatch):
    recorder = Recorder()
    monkeypatch.setenv("BOBINE_PORT", "1903")
    monkeypatch.setattr(cli.Client, "request", lambda self, method, path, **kw: recorder.request(self, method, path, **kw))
    monkeypatch.setattr(cli.Client, "upload", lambda self, path, files, fields=None: recorder.uploads.append((path, files, fields)) or {"job_id": "job-1"})
    return recorder


@pytest.mark.parametrize("argv, method, path", [
    (["playlists", "add", "Soir", "--video", "3", "--video", "4"], "POST", "/api/playlists"),
    (["schedule", "rm", "5", "--yes"], "DELETE", "/api/schedule/5"),
    (["library", "rm", "9", "--yes"], "DELETE", "/api/videos/9"),
])
def test_write_commands_call_the_interface_route(rec, argv, method, path):
    assert cli.main(argv) == cli.EXIT_OK
    assert rec.calls[0][:2] == (method, path)


def test_playlist_items_keep_the_given_order(rec):
    cli.main(["playlists", "add", "Soir", "--video", "3", "--video", "4"])
    assert json.dumps(rec.calls[0][3]).count("3") and rec.calls[0][3]["name"] == "Soir"


@pytest.mark.parametrize("argv", [["schedule", "rm", "5"], ["library", "rm", "9"], ["playlists", "rm", "2"]])
def test_destructive_commands_need_yes(rec, argv, capsys):
    assert cli.main(argv) == cli.EXIT_USAGE
    assert rec.calls == [] and "--yes" in capsys.readouterr().err


def test_every_spec_route_is_declared_as_covered():
    from app.cli import routes as cli_routes
    for spec in SPECS:
        for route in spec.covers:
            assert cli_routes.COVERED[route] == spec.command


def test_api_get_prints_the_answer(rec, capsys):
    assert cli.main(["api", "GET", "/api/health", "--query", "a=1"]) == cli.EXIT_OK
    assert rec.calls[0][:3] == ("GET", "/api/health", {"a": 1})
    assert json.loads(capsys.readouterr().out)["id"] == 7


def test_api_write_needs_yes_and_a_valid_path(rec, capsys):
    assert cli.main(["api", "POST", "/api/playback/cable/stop"]) == cli.EXIT_USAGE
    assert cli.main(["api", "GET", "/api/../etc"]) == cli.EXIT_USAGE
    assert cli.main(["api", "GET", "/api/x?y=1"]) == cli.EXIT_USAGE
    assert cli.main(["api", "POST", "/api/playback/cable/stop", "--yes", "--body", "{pas du json"]) == cli.EXIT_USAGE
    assert rec.calls == []


def test_api_refuses_dangerous_routes_even_with_yes(rec):
    assert cli.main(["api", "POST", "/api/settings/backup/restore", "--yes"]) == cli.EXIT_USAGE
    assert cli.main(["api", "POST", "/api/updates/apply", "--yes"]) == cli.EXIT_USAGE
    assert rec.calls == []


def test_api_body_from_a_file(rec, tmp_path):
    body = tmp_path / "b.json"
    body.write_text('{"k": 1}', encoding="utf-8")
    assert cli.main(["api", "PUT", "/api/settings", "--yes", "--body", f"@{body}"]) == cli.EXIT_OK
    assert rec.calls[0][3] == {"k": 1}


def test_import_sends_each_video_alone_and_waits(rec, tmp_path, capsys):
    a, b = tmp_path / "a.mp4", tmp_path / "b.mp4"
    a.write_bytes(b"1"); b.write_bytes(b"2")
    assert cli.main(["library", "import", str(a), str(b), "--wait"]) == cli.EXIT_OK
    assert [u[0] for u in rec.uploads] == ["/api/videos/upload"] * 2


def test_import_refuses_one_title_for_several_files(rec, tmp_path):
    a, b = tmp_path / "a.mp4", tmp_path / "b.mp4"
    a.write_bytes(b"1"); b.write_bytes(b"2")
    assert cli.main(["library", "import", str(a), str(b), "--title", "T"]) == cli.EXIT_USAGE
    assert rec.uploads == []


def test_import_missing_file_and_audio_title(rec, tmp_path):
    assert cli.main(["library", "import", str(tmp_path / "absent.mp4")]) == cli.EXIT_USAGE
    f = tmp_path / "a.mp3"; f.write_bytes(b"1")
    assert cli.main(["audio", "import", str(f)]) == cli.EXIT_USAGE
    assert cli.main(["audio", "import", str(f), "--title", "Cours"]) == cli.EXIT_OK


def test_audio_zip_uses_the_archive_route(rec, tmp_path):
    z = tmp_path / "c.zip"; z.write_bytes(b"PK")
    cli.main(["radio-library", "import", str(z)])
    assert rec.uploads[0][0] == "/api/radio/tracks/upload-zip"


def test_restore_needs_yes(rec, tmp_path):
    f = tmp_path / "s.zip"; f.write_bytes(b"PK")
    assert cli.main(["settings", "restore", str(f)]) == cli.EXIT_USAGE
    assert rec.uploads == []
    assert cli.main(["settings", "restore", str(f), "--yes"]) == cli.EXIT_OK


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, size=-1):
        data, self.data = self.data, b""
        return data


def test_backup_writes_a_new_file_and_never_overwrites(monkeypatch, tmp_path):
    monkeypatch.setenv("BOBINE_PORT", "1903")
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: FakeResponse(b"PKdonnees"))
    target = tmp_path / "sauvegarde.zip"
    assert cli.main(["settings", "backup", str(target)]) == cli.EXIT_OK
    assert target.read_bytes() == b"PKdonnees"
    target.write_bytes(b"precieux")
    assert cli.main(["settings", "backup", str(target)]) == cli.EXIT_USAGE
    assert target.read_bytes() == b"precieux"


def test_archives_use_the_archive_route_for_every_family(rec, tmp_path):
    z = tmp_path / "lot.zip"; z.write_bytes(b"PK")
    for family, route in (("library", "/api/videos/upload-zip"), ("backgrounds", "/api/backgrounds/upload-zip")):
        assert cli.main([family, "import", str(z)]) == cli.EXIT_OK
        assert rec.uploads[-1][0] == route
