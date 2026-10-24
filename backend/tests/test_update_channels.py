"""Robustesse des mises a jour et de la gestion des canaux de mise a jour
Stable/Beta/Canary : decision pure `_evaluate_update` (dont le retour en
arriere Beta/Canary -> Stable), migration DB du canal "beta" historique
(rolling) vers "canary", choix de l'asset par profil (APK telephone vs
Android TV), reconciliation de l'etat persiste apres un redemarrage reussi,
telechargement verifie avec nouvelles tentatives."""

import asyncio
import hashlib
import http.server
import json
import threading
from pathlib import Path

import pytest

from app.routers import updates
from app.utils import update_orchestrator as orch


def _local(version: str, commit: str = "aaaaaaa", local_rolling_channel: str | None = None) -> dict:
    return {
        "current_version": version, "current_tag": version,
        "current_commit": commit, "local_rolling_channel": local_rolling_channel,
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
    r = updates._evaluate_update("stable", _local("V4.0.2-beta", local_rolling_channel="beta"), _stable("V4.0.2"))
    assert r["has_update"] is True and r["is_downgrade"] is False


def test_beta_build_ahead_of_stable_can_go_back_to_stable():
    # Repasser en Stable "a tout moment" : propose la stable anterieure,
    # marquee comme retour en arriere (jamais applique par la planification).
    r = updates._evaluate_update("stable", _local("V4.0.3-beta", local_rolling_channel="beta"), _stable("V4.0.2"))
    assert r == {"has_update": True, "is_downgrade": True, "latest_version": "V4.0.2"}


def test_canary_build_of_same_base_is_replaced_by_stable():
    r = updates._evaluate_update("stable", _local("V4.0.2-canary", local_rolling_channel="canary"), _stable("V4.0.2"))
    assert r["has_update"] is True and r["is_downgrade"] is False


def test_canary_build_ahead_of_stable_can_go_back_to_stable():
    r = updates._evaluate_update("stable", _local("V4.0.3-canary", local_rolling_channel="canary"), _stable("V4.0.2"))
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


def test_canary_channel_compares_commits_not_versions():
    release = {"tag_name": "canary", "target_commitish": "c05011755e69136ce3d24655f4562c3a57e131e9"}
    same = updates._evaluate_update("canary", _local("V4.0.2", commit="c050117"), release)
    assert same["has_update"] is False
    other = updates._evaluate_update("canary", _local("V4.0.2", commit="deadbee"), release)
    assert other["has_update"] is True and other["is_downgrade"] is False
    assert other["latest_version"] == "canary (c050117)"


def test_canary_channel_unknown_local_commit_never_claims_an_update():
    release = {"tag_name": "canary", "target_commitish": "c05011755e69136ce3d24655f4562c3a57e131e9"}
    assert updates._evaluate_update("canary", _local("V4.0.2", commit="unknown"), release)["has_update"] is False


# --- migration DB du canal "beta" historique (rolling) vers "canary" -------

def test_migrate_update_channel_beta_to_canary_rewrites_existing_value(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, text

    from app import database as db_module

    temp_engine = create_engine(f"sqlite:///{tmp_path / 'migrate.db'}")
    with temp_engine.connect() as conn:
        conn.execute(text("CREATE TABLE settings (key VARCHAR PRIMARY KEY, value VARCHAR NOT NULL)"))
        conn.execute(text("INSERT INTO settings (key, value) VALUES ('update_channel', 'beta')"))
        conn.commit()

    monkeypatch.setattr(db_module, "engine", temp_engine)
    monkeypatch.setattr(db_module, "_IS_SQLITE", True)
    db_module._migrate_update_channel_beta_to_canary()

    with temp_engine.connect() as conn:
        value = conn.execute(text("SELECT value FROM settings WHERE key='update_channel'")).scalar()
    assert value == "canary"


def test_migrate_update_channel_beta_to_canary_is_a_noop_for_other_values(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, text

    from app import database as db_module

    temp_engine = create_engine(f"sqlite:///{tmp_path / 'migrate.db'}")
    with temp_engine.connect() as conn:
        conn.execute(text("CREATE TABLE settings (key VARCHAR PRIMARY KEY, value VARCHAR NOT NULL)"))
        conn.execute(text("INSERT INTO settings (key, value) VALUES ('update_channel', 'stable')"))
        conn.commit()

    monkeypatch.setattr(db_module, "engine", temp_engine)
    monkeypatch.setattr(db_module, "_IS_SQLITE", True)
    db_module._migrate_update_channel_beta_to_canary()
    db_module._migrate_update_channel_beta_to_canary()  # idempotent, deuxieme appel sans effet ni erreur

    with temp_engine.connect() as conn:
        value = conn.execute(text("SELECT value FROM settings WHERE key='update_channel'")).scalar()
    assert value == "stable"


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


def test_multi_distro_and_multi_arch_asset_resolution():
    full_release = {
        "assets": [
            {"name": "Bobine-Setup-5.0.5.exe", "browser_download_url": "u/win-x64.exe", "size": 10, "digest": "sha256:1"},
            {"name": "Bobine-Setup-5.0.5-arm64.exe", "browser_download_url": "u/win-arm64.exe", "size": 11, "digest": "sha256:2"},
            {"name": "bobine_5.0.5_amd64.deb", "browser_download_url": "u/deb-amd64.deb", "size": 12, "digest": "sha256:3"},
            {"name": "bobine_5.0.5_arm64.deb", "browser_download_url": "u/deb-arm64.deb", "size": 13, "digest": "sha256:4"},
            {"name": "bobine-5.0.5-1.x86_64.rpm", "browser_download_url": "u/rpm-x64.rpm", "size": 14, "digest": "sha256:5"},
            {"name": "bobine-5.0.5-1.aarch64.rpm", "browser_download_url": "u/rpm-arm64.rpm", "size": 15, "digest": "sha256:6"},
            {"name": "bobine-5.0.5-1-x86_64.pkg.tar.zst", "browser_download_url": "u/arch-x64.pkg.tar.zst", "size": 16, "digest": "sha256:7"},
            {"name": "bobine-5.0.5-1-aarch64.pkg.tar.zst", "browser_download_url": "u/arch-arm64.pkg.tar.zst", "size": 17, "digest": "sha256:8"},
        ]
    }
    assert updates._resolve_asset("windows", full_release, arch="x86_64")["download_url"] == "u/win-x64.exe"
    assert updates._resolve_asset("windows", full_release, arch="arm64")["download_url"] == "u/win-arm64.exe"
    assert updates._resolve_asset("linux-desktop", full_release, arch="x86_64", linux_ext=".deb")["download_url"] == "u/deb-amd64.deb"
    assert updates._resolve_asset("linux-desktop", full_release, arch="arm64", linux_ext=".deb")["download_url"] == "u/deb-arm64.deb"
    assert updates._resolve_asset("linux-desktop", full_release, arch="x86_64", linux_ext=".rpm")["download_url"] == "u/rpm-x64.rpm"
    assert updates._resolve_asset("linux-desktop", full_release, arch="arm64", linux_ext=".rpm")["download_url"] == "u/rpm-arm64.rpm"
    assert updates._resolve_asset("linux-desktop", full_release, arch="x86_64", linux_ext=".pkg.tar.zst")["download_url"] == "u/arch-x64.pkg.tar.zst"
    assert updates._resolve_asset("linux-desktop", full_release, arch="arm64", linux_ext=".pkg.tar.zst")["download_url"] == "u/arch-arm64.pkg.tar.zst"


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


# --- acquittement persiste de la notification (anti-boucle) ----------------
# Non-regression du correctif "la notification de mise a jour apparait en
# continu" : l'acquittement doit survivre a un rechargement de page (donc
# etre lu depuis l'etat serveur, jamais un seul state React volatile).

def test_acknowledge_persists_started_at_and_broadcasts(state_file, monkeypatch):
    orch._state["started_at"] = 123.0
    orch._state["acknowledged_started_at"] = None
    broadcasted = {}

    async def fake_broadcast(payload):
        broadcasted.update(payload)

    monkeypatch.setattr(orch.ws_manager, "broadcast", fake_broadcast)
    result = asyncio.run(orch.acknowledge_current())

    assert result["acknowledged_started_at"] == 123.0
    assert broadcasted["acknowledged_started_at"] == 123.0
    assert json.loads(state_file.read_text())["acknowledged_started_at"] == 123.0


def test_acknowledge_is_a_noop_for_idle_state(state_file, monkeypatch):
    orch._state["started_at"] = None
    orch._state["acknowledged_started_at"] = None
    monkeypatch.setattr(orch.ws_manager, "broadcast", lambda payload: asyncio.sleep(0))
    result = asyncio.run(orch.acknowledge_current())
    assert result["acknowledged_started_at"] is None


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


def test_download_calls_on_verifying_before_digest_check(tmp_path, monkeypatch):
    # Non-regression : l'etape "verifying" du wizard (cf. ACTIVE_STEPS cote
    # frontend) doit etre emise exactement une fois, apres le telechargement
    # complet mais avant la comparaison d'empreinte SHA-256.
    monkeypatch.setattr(orch.time, "sleep", lambda *_: None)
    payload = b"w" * 50_000
    server = _Server(payload)
    try:
        dest = tmp_path / "f.bin"
        calls = []
        orch.download_with_progress(
            server.url, dest, _digest(payload), on_verifying=lambda: calls.append("verifying"),
        )
        assert calls == ["verifying"]
        assert dest.read_bytes() == payload
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


# --- environnement assaini des sous-processus systeme ----------------------
# Non-regression du correctif "systemctl: libcrypto.so.3: version
# OPENSSL_3.4.0 not found" (LD_LIBRARY_PATH d'un build PyInstaller frozen
# herite par un binaire systeme totalement etranger au bundle, cf.
# clean_subprocess_env()).

def test_clean_subprocess_env_strips_ld_library_path_without_original(monkeypatch):
    monkeypatch.setenv("LD_LIBRARY_PATH", "/usr/lib/bobine")
    monkeypatch.delenv("LD_LIBRARY_PATH_ORIG", raising=False)
    env = orch.clean_subprocess_env()
    assert "LD_LIBRARY_PATH" not in env


def test_clean_subprocess_env_restores_original_ld_library_path(monkeypatch):
    monkeypatch.setenv("LD_LIBRARY_PATH", "/usr/lib/bobine")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/usr/lib/x86_64-linux-gnu")
    env = orch.clean_subprocess_env()
    assert env["LD_LIBRARY_PATH"] == "/usr/lib/x86_64-linux-gnu"
    assert "LD_LIBRARY_PATH_ORIG" not in env


def test_clean_subprocess_env_noop_when_unset(monkeypatch):
    monkeypatch.delenv("LD_LIBRARY_PATH", raising=False)
    monkeypatch.delenv("LD_LIBRARY_PATH_ORIG", raising=False)
    env = orch.clean_subprocess_env()
    assert "LD_LIBRARY_PATH" not in env


def test_run_checked_uses_sanitized_env(monkeypatch):
    monkeypatch.setenv("LD_LIBRARY_PATH", "/usr/lib/bobine")
    captured = {}
    real_run = orch.subprocess.run

    def spy_run(cmd, **kwargs):
        captured.update(kwargs)
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(orch.subprocess, "run", spy_run)
    orch.run_checked(["true"])
    assert "LD_LIBRARY_PATH" not in captured["env"]


# --- build Google Play : mises a jour par la boutique -----------------------

class _StoreHandler:
    def is_store_managed(self) -> bool:
        return True

    def can_auto_apply(self) -> bool:
        return False


def test_store_managed_check_does_not_query_github(monkeypatch):
    monkeypatch.setattr(updates, "get_profile_handler", lambda: _StoreHandler())
    monkeypatch.setattr(updates, "_get_local_version_info", lambda: _local("V5.0.0"))
    monkeypatch.setattr(updates, "_get_update_channel", lambda db: "stable")

    async def _boom(*args, **kwargs):
        raise AssertionError("aucune requete GitHub pour un build de boutique")

    monkeypatch.setattr(updates, "_fetch_release_for_channel", _boom)
    result = asyncio.run(updates.check_updates(refresh=True, db=None))
    assert result["store_managed"] is True
    assert result["has_update"] is False and result["can_auto_apply"] is False


def test_store_managed_apply_is_refused(monkeypatch):
    from fastapi import BackgroundTasks, HTTPException

    monkeypatch.setattr(updates, "get_profile_handler", lambda: _StoreHandler())
    with pytest.raises(HTTPException) as exc:
        asyncio.run(updates.apply_update(BackgroundTasks(), db=None))
    assert exc.value.status_code == 400
