import os
import time
from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    ImportSource,
    Video,
)
from storage_flow_support import _sha, vol_view, wait_job, codes, _register  # noqa: E402


def test_export_writes_temporarily_then_returns_to_read_only_and_counts_bytes(env, tmp_path):
    vol = env.driver.plug("sda", "DDDD-0001", {"deja.txt": b"1"}, kind="sd", label="CARTE")
    env.refresh()
    _register(env, vol.key)
    local = tmp_path / "local" / "cours.mp4"
    local.parent.mkdir()
    local.write_bytes(os.urandom(300_000))
    with SessionLocal() as db:
        video = Video(file_path=str(local), title="__stk_Export", source=ImportSource.upload)
        db.add(video)
        db.commit()
        video_id = video.id
    response = env.client.post(f"/api/storage/volumes/{vol.key}/export", json={"kind": "video", "ids": [video_id], "dest": "Sauvegarde/Bobine"})
    assert response.status_code == 202, response.text
    job = wait_job(env.client, response.json()["job_id"])
    assert job["stage"] == "done" and job["details"]["exported"] == 1
    exported = env.driver.disk_dir(vol.key) / "Sauvegarde" / "Bobine" / "__stk_Export.mp4"
    assert exported.exists() and _sha(exported) == _sha(local) and local.exists()
    assert not list((env.driver.disk_dir(vol.key) / "Sauvegarde" / "Bobine").glob(".bobine-*"))
    deadline = time.time() + 10
    while time.time() < deadline and vol_view(env, vol.key)["mounted_read_only"] is not True:
        time.sleep(0.2)
    view = vol_view(env, vol.key)
    assert view["mounted_read_only"] is True
    rw_calls = [options for _, options in env.driver.mount_calls if options[0] == "rw"]
    assert len(rw_calls) == 1
    assert view["library"]["bytes_written"] == 300_000 and view["library"]["wear_level"] == "ok"
    second = env.client.post(f"/api/storage/volumes/{vol.key}/export", json={"kind": "video", "ids": [video_id], "dest": "Sauvegarde/Bobine"}).json()
    assert wait_job(env.client, second["job_id"])["stage"] == "done"
    assert (env.driver.disk_dir(vol.key) / "Sauvegarde" / "Bobine" / "__stk_Export (2).mp4").exists() and exported.exists()
    with SessionLocal() as db:
        db.query(Video).filter(Video.id == video_id).delete()
        db.commit()


def test_export_refuses_unsafe_destination_and_unwritable_filesystems(env, tmp_path):
    vol = env.driver.plug("sda", "DDDD-0002", {"x.txt": b"1"})
    env.refresh()
    local = tmp_path / "l.mp4"
    local.write_bytes(b"data")
    with SessionLocal() as db:
        video = Video(file_path=str(local), title="__stk_Dest", source=ImportSource.upload)
        db.add(video)
        db.commit()
        video_id = video.id
    base = f"/api/storage/volumes/{vol.key}/export"
    body = {"kind": "video", "ids": [video_id]}
    assert codes(env.client.post(base, json=body)) == "not_mounted"
    env.client.post(f"/api/storage/volumes/{vol.key}/mount", json={})
    for hostile in ("../../etc", "/etc", "a/../../b"):
        refused = env.client.post(base, json={**body, "dest": hostile})
        assert refused.status_code == 400 and codes(refused) == "bad_path"
    assert env.driver.mount_calls[-1][1][0] == "ro" and not (env.tmp / "etc").exists()
    assert codes(env.client.post(base, json={"kind": "video", "ids": [987654]})) == "nothing_to_export"
    assert codes(env.client.post(base, json={"kind": "video", "ids": []})) == "empty_selection"
    env.service._dirty.add(vol.key)
    assert codes(env.client.post(base, json=body)) == "write_refused"
    with SessionLocal() as db:
        db.query(Video).filter(Video.id == video_id).delete()
        db.commit()


def test_settings_are_visible_validated_and_disableable(env):
    vol = env.driver.plug("sda", "EEEE-0001")
    env.refresh()
    assert codes(env.client.put(f"/api/storage/volumes/{vol.key}/settings", json={"noatime": False})) == "not_registered"
    _register(env, vol.key)
    updated = env.client.put(f"/api/storage/volumes/{vol.key}/settings", json={"noatime": False, "standby_minutes": 9999, "read_only": True}).json()
    assert updated["noatime"] is False and updated["standby_minutes"] == 240 and updated["read_only"] is True
    items = {i["id"]: i for i in vol_view(env, vol.key)["longevity"]}
    assert items["noatime"]["status"] == "disabled" and items["noatime"]["enabled"] is False
    env.client.post(f"/api/storage/volumes/{vol.key}/mount", json={})
    defaults = env.client.put("/api/storage/settings", json={"noexec": False}).json()
    assert defaults["noexec"] is False
    other = env.driver.plug("sdb", "EEEE-0002")
    env.refresh()
    assert vol_view(env, other.key)["library"]["settings"]["noexec"] is False
    assert env.client.put("/api/storage/settings", json={"standby_minutes": "beaucoup"}).status_code == 422


def test_health_is_honest_without_smart_and_counts_writes(env):
    vol = env.driver.plug("sda", "EEEE-0003")
    env.refresh()
    report = env.client.get(f"/api/storage/volumes/{vol.key}/health").json()
    assert report["available"] is False and report["reason"] == "permission" and report["overall"] == "ok" and report["bytes_written"] == 0
    env.driver.smart_report = {"available": True, "status": "warning", "warnings": ["reallocated_sectors"], "temperature_c": 40, "wear_percent_used": 12.0}
    refreshed = env.client.get(f"/api/storage/volumes/{vol.key}/health", params={"refresh": True}).json()
    assert refreshed["overall"] == "warning" and refreshed["warnings"] == ["reallocated_sectors"]
    cached = env.client.get(f"/api/storage/volumes/{vol.key}/health").json()
    assert cached["overall"] == "warning"


def test_trim_is_refused_without_privileges(env):
    vol = env.driver.plug("sda", "EEEE-0004")
    env.refresh()
    response = env.client.post(f"/api/storage/volumes/{vol.key}/trim")
    assert response.status_code == 501 and codes(response) == "needs_root"
    env.driver.root_user = True
    assert env.client.post(f"/api/storage/volumes/{vol.key}/trim").json() == {"result": "ok"}


def test_standby_applies_only_to_idle_rotational_disks(env):
    hdd = env.driver.plug("sda", "EEEE-0005", kind="hdd", rotational=True)
    ssd = env.driver.plug("sdb", "EEEE-0006", kind="usb", rotational=False)
    env.refresh()
    for key in (hdd.key, ssd.key):
        env.client.post(f"/api/storage/volumes/{key}/mount", json={})
    env.service._activity[hdd.key] = time.monotonic() - 3600
    env.service._activity[ssd.key] = time.monotonic() - 3600
    env.service._last_maintenance = 0
    env.client.portal.call(env.service._maintenance)
    assert env.driver.standby_calls == [hdd.key]
    assert vol_view(env, hdd.key)["standby"]["ok"] is True
    env.client.portal.call(env.service._maintenance)
    env.service._last_maintenance = 0
    env.client.portal.call(env.service._maintenance)
    assert env.driver.standby_calls == [hdd.key]


def test_format_advisor_endpoint(env):
    rec = env.client.get("/api/storage/advisor/format", params={"host": "linux", "others": "windows,macos"}).json()
    assert rec["fstype"] == "exfat" and rec["destructive"] is True and "windows" in rec["procedures"]
    assert env.client.get("/api/storage/advisor/format", params={"host": "windows"}).json()["fstype"] == "ntfs"
    assert env.client.get("/api/storage/advisor/format", params={"legacy": True}).json()["fstype"] == "vfat"
