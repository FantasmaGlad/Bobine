import os
import subprocess

import pytest

from app.process import spawn


@pytest.mark.parametrize(("name", "suffix", "console"), [("nt", ".exe", {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}), ("posix", "", {})])
def test_spawn_follows_the_platform(monkeypatch, name, suffix, console):
    monkeypatch.setattr(os, "name", name)
    assert spawn.executable_name("bobine-media") == f"bobine-media{suffix}"
    assert spawn.hidden_console_kwargs() == console
