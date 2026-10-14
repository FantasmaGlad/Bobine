"""Robustesse des mises a jour et de la gestion des canaux Stable/Beta :
decision pure `_evaluate_update` (dont le retour en arriere Beta -> Stable),
choix de l'asset par profil (APK telephone vs Android TV), reconciliation de
l'etat persiste apres un redemarrage reussi, telechargement verifie avec
nouvelles tentatives."""

import hashlib
import http.server
import json
import threading
from pathlib import Path

import pytest

from app.routers import updates
from app.utils import update_orchestrator as orch


def _local(version: str, commit: str = "aaaaaaa", prerelease: bool = False) -> dict:
    return {
        "current_version": version, "current_tag": version,
        "current_commit": commit, "is_prerelease_build": prerelease,
    }


def _stable(tag: str) -> dict:
    return {"tag_name": tag}


# --- decision de mise a jour ----------------------------------------------

def test_stable_newer_version_is_an_upgrade():
    r = updates._evaluate_update("stable", _local("V4.0.1"), _stable("V4.0.2"))
    assert r == {"has_update": True, "is_downgrade": False, "latest_version": "V4.0.2"}


def test_stable_same_version_is_up_to_date():
    r = updates._evaluate_update("stable", _local("V4.0.2"), _stable("V4.0.2"))
    assert r["has_update"] is False


def test_beta_build_of_same_base_is_replaced_by_stable():
    # "4.0.2-beta" < "4.0.2" : promesse "une stable equivalente la remplace".
    r = updates._evaluate_update("stable", _local("V4.0.2-beta", prerelease=True), _stable("V4.0.2"))
    assert r["has_update"] is True and r["is_downgrade"] is False


def test_beta_build_ahead_of_stable_can_go_back_to_stable():
    # Repasser en Stable "a tout moment" : propose la stable anterieure,
    # marquee comme retour en arriere (jamais applique par la planification).
    r = updates._evaluate_update("stable", _local("V4.0.3-beta", prerelease=True), _stable("V4.0.2"))
    assert r == {"has_update": True, "is_downgrade": True, "latest_version": "V4.0.2"}


def test_stable_build_never_offered_an_older_stable():
    r = updates._evaluate_update("stable", _local("V4.0.3"), _stable("V4.0.2"))
    assert r["has_update"] is False


def test_beta_channel_compares_commits_not_versions():
    release = {"tag_name": "beta", "target_commitish": "c05011755e69136ce3d24655f4562c3a57e131e9"}
    same = updates._evaluate_update("beta", _local("V4.0.2", commit="c050117"), release)
    assert same["has_update"] is False
    other = updates._evaluate_update("beta", _local("V4.0.2", commit="deadbee"), release)
    assert other["has_update"] is True and other["is_downgrade"] is False
    assert other["latest_version"] == "beta (c050117)"


def test_beta_channel_unknown_local_commit_never_claims_an_update():
    release = {"tag_name": "beta", "target_commitish": "c05011755e69136ce3d24655f4562c3a57e131e9"}
    assert updates._evaluate_update("beta", _local("V4.0.2", commit="unknown"), release)["has_update"] is False


# --- choix de l'asset ------------------------------------------------------

_RELEASE_ASSETS = {
    "assets": [
        {"name": "bobine-assistant", "browser_download_url": "u/assistant", "size": 1, "digest": "sha256:aa"},
        {"name": "Bobine-4.0.2.apk", "browser_download_url": "u/mobile.apk", "size": 2, "digest": "sha256:bb"},
        {"name": "Bobine-TV-4.0.2.apk", "browser_download_url": "u/tv.apk", "size": 3, "digest": "sha256:cc"},
        {"name": "Bobine-Setup-4.0.2.exe", "browser_download_url": "u/setup.exe", "size": 4, "digest": "sha256:dd"},
        {"name": "bobine_4.0.2_amd64.deb", "browser_download_url": "u/b.deb", "size": 5, "digest": "sha256:ee"},
    ]
}


def test_android_mobile_gets_the_phone_apk():
    assert updates._resolve_asset("android", _RELEASE_ASSETS, "mobile")["download_url"] == "u/mobile.apk"
    assert updates._resolve_asset("android", _RELEASE_ASSETS, None)["download_url"] == "u/mobile.apk"


def test_android_tv_gets_the_tv_apk_even_when_listed_second():
    assert updates._resolve_asset("android", _RELEASE_ASSETS, "tv")["download_url"] == "u/tv.apk"


def test_android_tv_without_tv_asset_gets_nothing_rather_than_the_wrong_apk():
    only_phone = {"assets": [_RELEASE_ASSETS["assets"][1]]}
    assert updates._resolve_asset("android", only_phone, "tv")["download_url"] is None


def test_desktop_profiles_pick_their_extension():
    assert updates._resolve_asset("windows", _RELEASE_ASSETS)["download_url"] == "u/setup.exe"
    assert updates._resolve_asset("linux-desktop", _RELEASE_ASSETS)["asset_digest"] == "sha256:ee"
    assert updates._resolve_asset("macos", _RELEASE_ASSETS)["download_url"] is None


# --- reconciliation de l'etat apres redemarrage -----------------------------

@pytest.fixture
def state_file(tmp_path, monkeypatch):
    path = tmp_path / "update_status.json"
    monkeypatch.setattr(orch, "status_file_path", lambda: path)
    monkeypatch.setattr(orch, "_status_file_path", lambda: path)
    saved = dict(orch._state)
    yield path
    orch._state.clear()
    orch._state.update(saved)


def _persist(path: Path, **fields):
    base = {k: None for k in orch._state}
    base.update(fields)
    path.write_text(json.dumps(base), encoding="utf-8")


def test_restart_after_real_update_is_reported_as_done(state_file, monkeypatch):
    _persist(state_file, step="restarting", from_fingerprint="4.0.1|aaaaaaa")
    monkeypatch.setattr(orch, "get_build_fingerprint", lambda: "4.0.2|bbbbbbb")
    orch.load_persisted_state_at_startup()
    assert orch.get_status()["step"] == "done"
    assert orch.get_status()["error"] is None
    assert "from_fingerprint" not in orch.get_status()


def test_restart_without_change_is_reported_as_failed(state_file, monkeypatch):
    _persist(state_file, step="installing", from_fingerprint="4.0.2|aaaaaaa")
    monkeypatch.setattr(orch, "get_build_fingerprint", lambda: "4.0.2|aaaaaaa")
    orch.load_persisted_state_at_startup()
    assert orch.get_status()["step"] == "failed"
    assert orch.get_status()["error"]


def test_apk_never_installed_returns_to_idle(state_file, monkeypatch):
    _persist(state_file, step="awaiting_user_confirmation", from_fingerprint="4.0.2|aaaaaaa")
    monkeypatch.setattr(orch, "get_build_fingerprint", lambda: "4.0.2|aaaaaaa")
    orch.load_persisted_state_at_startup()
    assert orch.get_status()["step"] == "idle"


def test_terminal_states_are_left_untouched(state_file, monkeypatch):
    _persist(state_file, step="failed", error="boom", from_fingerprint="x|y")
    monkeypatch.setattr(orch, "get_build_fingerprint", lambda: "z|w")
    orch.load_persisted_state_at_startup()
    assert orch.get_status()["step"] == "failed" and orch.get_status()["error"] == "boom"


# --- telechargement verifie ---------------------------------------------------

class _Server:
    """Serveur HTTP local : `fail_first` coupe la 1re reponse en plein
    transfert (fichier tronque) pour exercer la nouvelle tentative."""

    def __init__(self, payload: bytes, fail_first: int = 0):
        outer = self
        self.hits = 0

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                outer.hits += 1
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                if outer.hits <= fail_first:
                    self.wfile.write(payload[: len(payload) // 2])
                    return
                self.wfile.write(payload)

            def log_message(self, *a):
                pass

        self.httpd = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/f.bin"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()


def _digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def test_download_verifies_digest_and_renames_atomically(tmp_path, monkeypatch):
    monkeypatch.setattr(orch.time, "sleep", lambda *_: None)
    payload = b"x" * 300_000
    server = _Server(payload)
    try:
        dest = tmp_path / "f.bin"
        seen = []
        orch.download_with_progress(server.url, dest, _digest(payload), seen.append)
        assert dest.read_bytes() == payload
        assert not (tmp_path / "f.bin.part").exists()
        assert seen[-1] == 100
    finally:
        server.close()


def test_download_retries_after_truncated_transfer(tmp_path, monkeypatch):
    monkeypatch.setattr(orch.time, "sleep", lambda *_: None)
    payload = b"y" * 300_000
    server = _Server(payload, fail_first=1)
    try:
        dest = tmp_path / "f.bin"
        orch.download_with_progress(server.url, dest, _digest(payload))
        assert dest.read_bytes() == payload
        assert server.hits == 2
    finally:
        server.close()


def test_download_rejects_wrong_digest_and_leaves_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(orch.time, "sleep", lambda *_: None)
    payload = b"z" * 10_000
    server = _Server(payload)
    try:
        dest = tmp_path / "f.bin"
        with pytest.raises(RuntimeError, match="invalide"):
            orch.download_with_progress(server.url, dest, _digest(b"other"))
        assert not dest.exists() and not (tmp_path / "f.bin.part").exists()
    finally:
        server.close()


def test_download_without_digest_is_refused(tmp_path):
    with pytest.raises(RuntimeError, match="Empreinte"):
        orch.download_with_progress("http://127.0.0.1:1/x", tmp_path / "f.bin", None)
