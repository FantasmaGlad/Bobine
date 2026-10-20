"""Mini client WebDriver W3C (bibliothèque standard uniquement) pour piloter
geckodriver/Firefox depuis les scripts de ce dossier — aucune dépendance
(selenium/playwright) à installer. Voir `README.md` de ce dossier."""

import base64
import json
import os
import urllib.request

BASE = os.environ.get("GECKODRIVER_URL", "http://127.0.0.1:4444")
_SESSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".wd_session")


def _call(method, path, body=None):
    req = urllib.request.Request(
        BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as response:
        return json.loads(response.read())["value"]


def _sid():
    return open(_SESSION_FILE).read().strip()


def start(headless=True, width=1400, height=900):
    args = (["-headless"] if headless else []) + [f"--width={width}", f"--height={height}"]
    caps = {"capabilities": {"alwaysMatch": {"browserName": "firefox", "moz:firefoxOptions": {"args": args}}}}
    value = _call("POST", "/session", caps)
    open(_SESSION_FILE, "w").write(value["sessionId"])
    return value["capabilities"].get("browserVersion")


def set_window_rect(width, height):
    """Redimensionne la fenêtre (viewport ≈ taille demandée en mode headless)."""
    _call("POST", f"/session/{_sid()}/window/rect", {"width": width, "height": height})


def navigate(url):
    _call("POST", f"/session/{_sid()}/url", {"url": url})


def execute(script, args=None):
    return _call("POST", f"/session/{_sid()}/execute/sync", {"script": script, "args": args or []})


def execute_async(script, args=None):
    return _call("POST", f"/session/{_sid()}/execute/async", {"script": script, "args": args or []})


def find(css):
    return list(_call("POST", f"/session/{_sid()}/element", {"using": "css selector", "value": css}).values())[0]


def send_keys(element, text):
    _call("POST", f"/session/{_sid()}/element/{element}/value", {"text": text})


def screenshot(path):
    open(path, "wb").write(base64.b64decode(_call("GET", f"/session/{_sid()}/screenshot")))


def quit_session():
    _call("DELETE", f"/session/{_sid()}")
