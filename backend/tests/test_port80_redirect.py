"""Le redirecteur du port 80 n'envoie jamais vers un nom choisi par l'appelant."""

import pytest

from app.utils.port80 import redirect_location


@pytest.mark.parametrize("host, expected", [
    ("bobine.local", "http://bobine.local:8000/x"),
    ("192.168.1.5:80", "http://192.168.1.5:8000/x"),
    ("bobine", "http://bobine:8000/x"),
    ("evil.example", "http://bobine.local:8000/x"),
    ("evil.example:80", "http://bobine.local:8000/x"),
    ("", "http://bobine.local:8000/x"),
])
def test_redirect_host(host, expected):
    assert redirect_location(host, "/x", 8000) == expected
