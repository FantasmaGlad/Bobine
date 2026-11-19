import os
import socket
import sys

import pytest

from app import network
from app.process import lifecycle
from app.process.lifecycle import posix, windows


def test_own_pid_is_alive_and_nonpositive_is_not():
    assert lifecycle.pid_alive(os.getpid())
    assert not lifecycle.pid_alive(0)
    assert not lifecycle.pid_alive(-5)


@pytest.mark.parametrize(("name", "module"), [("nt", windows), ("posix", posix)])
def test_lifecycle_follows_the_platform(monkeypatch, name, module):
    calls = []
    monkeypatch.setattr(os, "name", name)
    monkeypatch.setattr(module, "pid_alive", lambda pid: calls.append(pid) or True)
    assert lifecycle.pid_alive(42)
    assert calls == [42]


def test_termination_handler_is_ignored_on_windows(monkeypatch):
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setattr(posix, "install_termination_handler", lambda handler: pytest.fail("POSIX handler on Windows"))
    lifecycle.install_termination_handler(lambda *_: None)


@pytest.mark.parametrize(("name", "system", "reuse"), [("posix", "linux", True), ("posix", "cygwin", False), ("nt", "win32", False)])
def test_listen_socket_reuses_address_only_on_posix(monkeypatch, name, system, reuse):
    monkeypatch.setattr(os, "name", name)
    monkeypatch.setattr(sys, "platform", system)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        network.prepare_listen_socket(sock)
        assert bool(sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)) == reuse
