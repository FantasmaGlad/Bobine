"""Durcissement de la commande bobine : chemins d'export, routes dangereuses encodées, délai, archives."""
import math
import tarfile
import zipfile

import pytest

from app import cli
from app.cli import config as cli_config
from app.utils import zip_safety
from app.utils.zip_safety import UnsafeZipError, safe_extract_archive


@pytest.mark.parametrize("name", ["../x.json", "/etc/passwd", "a/../../b", "C:\\x.json", "a\x00b", "..\\x"])
def test_export_names_leaving_the_folder_are_refused(name):
    with pytest.raises(cli.CliError):
        cli_config._checked_export_name(name)
    assert cli_config._checked_export_name("library/videos.json") == "library/videos.json"


def test_encoded_dangerous_route_is_still_refused(monkeypatch):
    monkeypatch.setenv("BOBINE_PORT", "1903")
    monkeypatch.setattr(cli.Client, "request", lambda self, *a, **k: (_ for _ in ()).throw(AssertionError("appel interdit")))
    assert cli.main(["api", "POST", "/api/updates/%61pply", "--yes"]) == cli.EXIT_USAGE
    assert cli.main(["api", "POST", "/api/settings/backup/%72estore", "--yes"]) == cli.EXIT_USAGE


@pytest.mark.parametrize("value", ["nan", "inf", "0", "-3"])
def test_invalid_timeouts_are_usage_errors(monkeypatch, value):
    monkeypatch.setenv("BOBINE_PORT", "1903")
    assert cli.main(["--timeout", value, "status"]) == cli.EXIT_USAGE


def test_archive_with_too_many_members_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(zip_safety, "MAX_ARCHIVE_MEMBERS", 3)
    archive = tmp_path / "lot.zip"
    with zipfile.ZipFile(archive, "w") as z:
        for i in range(5):
            z.writestr(f"f{i}.txt", b"x")
    with pytest.raises(UnsafeZipError):
        safe_extract_archive(archive, tmp_path / "out")
    assert not (tmp_path / "out").exists() or not any((tmp_path / "out").iterdir())


def test_archive_larger_than_the_free_space_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(zip_safety, "MAX_ARCHIVE_FREE_SPACE_RATIO", 0.0)
    source = tmp_path / "x.txt"
    source.write_bytes(b"x" * 100)
    archive = tmp_path / "lot.tar"
    with tarfile.open(archive, "w") as t:
        t.add(source, arcname="x.txt")
    with pytest.raises(UnsafeZipError):
        safe_extract_archive(archive, tmp_path / "out")
