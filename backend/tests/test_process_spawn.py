import os
import subprocess
import sys

import pytest

from app.process import spawn


@pytest.mark.parametrize(("name", "suffix", "console"), [("nt", ".exe", {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}), ("posix", "", {})])
def test_spawn_follows_the_platform(monkeypatch, name, suffix, console):
    monkeypatch.setattr(os, "name", name)
    assert spawn.executable_name("bobine-media") == f"bobine-media{suffix}"
    assert spawn.hidden_console_kwargs() == console


@pytest.mark.parametrize(("name", "system", "expected"), [("nt", "win32", {"creationflags"}), ("posix", "linux", {"preexec_fn"}), ("posix", "darwin", set())])
def test_daemons_are_tied_to_the_parent_where_possible(monkeypatch, name, system, expected):
    monkeypatch.setattr(os, "name", name)
    monkeypatch.setattr(sys, "platform", system)
    assert set(spawn.tied_to_parent_kwargs()) == expected


@pytest.mark.skipif(os.name == "nt", reason="POSIX modes")
def test_private_directory_on_posix(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    spawn.restrict_directory(tmp_path)
    assert tmp_path.stat().st_mode & 0o777 == 0o700
