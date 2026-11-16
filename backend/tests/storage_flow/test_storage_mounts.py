import hashlib
import os
import shutil
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.devices.base import DeviceError  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    AudioCourse,
    AudioTrack,
    ExternalVolume,
    ImportSource,
    RadioTrack,
    Setting,
    StorageImport,
    Video,
)
from app.storage import availability  # noqa: E402
from app.storage.service import StorageService  # noqa: E402
from storage_fakes import FakeStorageDriver  # noqa: E402
from storage_flow_support import get_volumes, vol_view, codes  # noqa: E402


def test_hot_plug_listing_never_exposes_paths(env):
    assert get_volumes(env)["volumes"] == []
    vol = env.driver.plug("sda", "7FDB-F2EC", {"Cours/a.mp4": b"x"}, label="COURS")
    env.refresh()
    listing = get_volumes(env)
    assert [v["key"] for v in listing["volumes"]] == [vol.key]
    view = listing["volumes"][0]
    assert view["state"] == "present" and view["mounted"] is False and view["connected"] and view["fstype"] == "exfat"
    assert view["assessment"]["verdict"] in ("acceptable", "recommended") and view["library"]["registered"] is False
    assert view["can_register"] is True
    dumped = str(listing)
    assert "/dev/" not in dumped and str(env.tmp) not in dumped


def test_mount_defaults_to_read_only_with_wear_friendly_options(env):
    vol = env.driver.plug("sda", "AAAA-0001")
    env.refresh()
    response = env.client.post(f"/api/storage/volumes/{vol.key}/mount", json={})
    assert response.status_code == 200 and response.json()["mode"] == "ro"
    key, options = env.driver.mount_calls[-1]
    assert options == ["ro", "noatime", "nodiratime", "noexec"]
    assert not set(options) & {"sync", "discard", "dirsync"}
    view = vol_view(env, vol.key)
    assert view["mounted"] and view["mounted_read_only"] is True and view["state"] == "mounted"
    longevity = {i["id"]: i for i in view["longevity"]}
    assert longevity["read_only"]["status"] == "applied" and longevity["noatime"]["status"] == "applied"
    assert longevity["smart"]["status"] in ("applied", "unavailable")
    assert env.client.post(f"/api/storage/volumes/{vol.key}/mount", json={}).json()["changed"] is False


def test_rw_mount_is_explicit_and_refused_on_dirty_filesystem(env):
    vol = env.driver.plug("sda", "AAAA-0002", fstype="ntfs")
    env.refresh()
    env.driver.fail_mount = DeviceError("dirty", "Le système de fichiers semble endommagé", 409)
    refused = env.client.post(f"/api/storage/volumes/{vol.key}/mount", json={"mode": "ro"})
    assert refused.status_code == 409 and codes(refused) == "dirty"
    view = vol_view(env, vol.key)
    assert view["assessment"]["write_allowed"] is False and view["assessment"]["reason"] == "dirty"
    env.driver.fail_mount = None
    assert codes(env.client.post(f"/api/storage/volumes/{vol.key}/mount", json={"mode": "rw"})) == "write_refused"
    assert env.client.post(f"/api/storage/volumes/{vol.key}/mount", json={"mode": "bogus"}).status_code == 400


def test_unknown_and_malformed_keys(env):
    assert env.client.post("/api/storage/volumes/u-inconnu/mount", json={}).status_code == 404
    assert codes(env.client.get("/api/storage/volumes/u-inconnu/browse")) == "volume_not_found"
    for hostile in ("%2Fdev%2Fsda1", "..%2Fetc", "sda1%3B%20rm%20-rf%20%2F", "x" * 200):
        response = env.client.post(f"/api/storage/volumes/{hostile}/eject")
        assert response.status_code == 404, hostile
    assert env.driver.unmount_calls == [] and env.driver.power_off_calls == []


def test_clean_eject_vs_abrupt_removal(env):
    clean = env.driver.plug("sda", "AAAA-0003")
    env.refresh()
    env.client.post(f"/api/storage/volumes/{clean.key}/mount", json={})
    response = env.client.post(f"/api/storage/volumes/{clean.key}/eject")
    assert response.status_code == 200 and response.json() == {"ejected": True, "powered_off": True}
    assert env.driver.power_off_calls == [clean.key] and env.driver.unmount_calls == [clean.key]
    assert get_volumes(env)["recent_removals"] == [] or all(not r["abrupt"] for r in get_volumes(env)["recent_removals"])

    brutal = env.driver.plug("sdb", "AAAA-0004", label="ARRACHEE")
    env.refresh()
    env.client.post(f"/api/storage/volumes/{brutal.key}/mount", json={})
    env.driver.unplug(brutal.key)
    env.refresh()
    removed = get_volumes(env)["recent_removals"]
    assert [r["name"] for r in removed if r["abrupt"]] == ["ARRACHEE"]


def test_busy_volume_refuses_unmount_and_eject(env):
    vol = env.driver.plug("sda", "AAAA-0005")
    env.refresh()
    env.client.post(f"/api/storage/volumes/{vol.key}/mount", json={})
    env.service._busy[vol.key] = {"job-x"}
    assert vol_view(env, vol.key)["state"] == "busy"
    assert codes(env.client.post(f"/api/storage/volumes/{vol.key}/unmount")) == "busy"
    assert codes(env.client.post(f"/api/storage/volumes/{vol.key}/eject")) == "busy"
    assert env.driver.unmount_calls == []
    env.service._busy.clear()
    assert env.client.post(f"/api/storage/volumes/{vol.key}/unmount").status_code == 200


def test_browse_requires_mount_and_blocks_traversal(env):
    vol = env.driver.plug("sda", "AAAA-0006", {"Cours/RPM/101.mp4": b"v", "Cours/notes.txt": b"n", "Musique/a.mp3": b"a", ".cache/x": b"1"})
    secret = env.tmp / "secret"
    secret.mkdir()
    (secret / "pwd.mp4").write_bytes(b"s")
    os.symlink(secret, env.driver.disk_dir(vol.key) / "Cours" / "evasion")
    env.refresh()
    base = f"/api/storage/volumes/{vol.key}/browse"
    assert codes(env.client.get(base)) == "not_mounted"
    env.client.post(f"/api/storage/volumes/{vol.key}/mount", json={})
    root = env.client.get(base).json()
    assert [e["name"] for e in root["entries"]] == ["Cours", "Musique"] and root["total"] == 2 and root["path"] == ""
    cours = env.client.get(base, params={"path": "Cours"}).json()
    names = [e["name"] for e in cours["entries"]]
    assert names == ["RPM", "notes.txt"] and cours["skipped_links"] == 1 and cours["parent"] == ""
    for bad in ("../..", "../../etc", "/etc", "Cours/../../..", "C:/Windows", "Cours\\..\\x", "Cours/evasion/pwd.mp4"):
        response = env.client.get(base, params={"path": bad})
        assert response.status_code in (400, 403, 404) and "code" in response.json()["detail"], bad
    assert codes(env.client.get(base, params={"path": "Cours/evasion"})) == "outside_volume"
    assert codes(env.client.get(base, params={"path": "n/existe/pas"})) == "not_found"
    paged = env.client.get(base, params={"path": "Cours", "limit": 1, "offset": 1}).json()
    assert len(paged["entries"]) == 1 and paged["total"] == 2
    assert env.client.get(base, params={"limit": 5000}).status_code == 422
    assert env.client.get(base, params={"path": "Cours", "media_only": True}).json()["total"] == 1
    assert str(env.tmp) not in str(root) + str(cours)
