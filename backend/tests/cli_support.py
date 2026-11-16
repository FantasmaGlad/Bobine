"""Appui des tests de la commande bobine : enregistreur de requêtes, erreurs HTTP simulées."""

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


def _http_error(status, detail):
    body = io.BytesIO(json.dumps({"detail": detail}).encode())
    return urllib.error.HTTPError("http://127.0.0.1:1903/x", status, "refus", {}, body)
