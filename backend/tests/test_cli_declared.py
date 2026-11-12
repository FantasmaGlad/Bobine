import pytest

from app import cli
from app.api import contract


class Recorder:
    def __init__(self):
        self.calls, self.uploads = [], []

    def request(self, method, path, query=None, body=None, **kwargs):
        self.calls.append((method, path, query, body))
        return {"items": [{"kind": "video", "id": 12, "title": "RPM", "available": True}], "total": 1}

    def upload(self, path, files, fields=None, method="POST"):
        self.uploads.append((method, path, [(name, file.name) for name, file in files], fields))
        return {"id": 1}


@pytest.fixture()
def rec(monkeypatch):
    recorder = Recorder()
    monkeypatch.setenv("BOBINE_PORT", "1903")
    monkeypatch.setattr(cli.Client, "request", lambda self, method, path, **kw: recorder.request(method, path, **kw))
    monkeypatch.setattr(cli.Client, "upload", lambda self, *a, **kw: recorder.upload(*a, **kw))
    return recorder


def test_media_list_filters_through_the_catalog(rec, capsys):
    assert cli.main(["media", "list", "--kind", "video", "--q", "rpm", "--limit", "5"]) == cli.EXIT_OK
    assert rec.calls == [("GET", "/api/media", {"kind": "video", "q": "rpm", "limit": 5}, None)]
    assert "12" in capsys.readouterr().out


@pytest.mark.parametrize("kind", list(contract.PLAYABLE_MEDIA))
def test_play_sends_the_load_action_of_each_kind(rec, kind):
    family, action, param = contract.PLAYABLE_MEDIA[kind]
    assert cli.main(["play", kind, "12", "--channel", "network"]) == cli.EXIT_OK
    assert rec.calls == [("POST", f"/api/{family}/network/{action}", None, {param: 12})]


def test_typed_fields_are_converted(rec):
    assert cli.main(["radio-playlists", "add", "Soir", "--track-ids", "3,1,2"]) == cli.EXIT_OK
    assert rec.calls[0][3] == {"name": "Soir", "track_ids": [3, 1, 2]}
    assert cli.main(["devices", "bt-power", "off"]) == cli.EXIT_OK
    assert rec.calls[1][3] == {"on": False}


def test_invalid_boolean_is_a_usage_error(rec):
    assert cli.main(["devices", "bt-power", "peut-etre"]) == cli.EXIT_USAGE
    assert rec.calls == []


def test_reserved_names_are_renamed(rec):
    assert cli.main(["storage", "advisor", "--for-host", "linux"]) == cli.EXIT_OK
    assert rec.calls[0][2] == {"host": "linux"}


def test_raw_body_is_sent_as_is(rec):
    assert cli.main(["radio-settings", "sound-set", '{"bass": 2}', "--channel", "radio_cable"]) == cli.EXIT_OK
    assert rec.calls[0][2:] == ({"channel": "radio_cable"}, {"bass": 2})


def test_files_go_through_multipart_with_the_route_method(rec, tmp_path):
    image = tmp_path / "cover.png"
    image.write_bytes(b"x")
    assert cli.main(["library", "thumbnail", "4", str(image)]) == cli.EXIT_OK
    assert rec.uploads == [("PUT", "/api/videos/4/thumbnail", [("file", "cover.png")], {})]


def test_several_files_share_one_field(rec, tmp_path):
    paths = [tmp_path / name for name in ("a.mp3", "b.mp3")]
    for path in paths:
        path.write_bytes(b"x")
    assert cli.main(["radio-announcements", "add-batch", *map(str, paths)]) == cli.EXIT_OK
    assert rec.uploads[0][2] == [("files", "a.mp3"), ("files", "b.mp3")]


def test_missing_file_is_a_usage_error(rec, tmp_path):
    assert cli.main(["settings", "logo", str(tmp_path / "absent.png")]) == cli.EXIT_USAGE


def test_partial_update_needs_one_field(rec):
    assert cli.main(["storage", "volume-set", "sdb1"]) == cli.EXIT_USAGE
    assert cli.main(["storage", "volume-set", "sdb1", "--noatime", "on"]) == cli.EXIT_OK
    assert rec.calls[-1][1:] == ("/api/storage/volumes/sdb1/settings", None, {"noatime": True})
