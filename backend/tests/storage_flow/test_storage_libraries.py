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
from storage_flow_support import needs_ffmpeg, get_volumes, vol_view, wait_job, codes, _register  # noqa: E402


def _register_mounted(env, media):
    vol = env.driver.plug("sda", "BBBB-0001", {"Cours/Rpm 101 test.mp4": media.video.read_bytes()}, label="CLUB", mounted_rw=True)
    env.refresh()
    assert vol_view(env, vol.key)["mounted_read_only"] is False
    assert codes(env.client.post(f"/api/storage/volumes/{vol.key}/index", json={"entries": [{"path": "Cours"}], "kind": "video"})) == "not_registered"
    _register(env, vol.key)
    assert env.driver.mount_calls[-1][1][0] == "ro" and vol_view(env, vol.key)["mounted_read_only"] is True
    first_mount = env.driver.volumes[vol.key].mountpoint
    return vol, first_mount


def _index_course(env, vol, first_mount):
    started = env.client.post(f"/api/storage/volumes/{vol.key}/index", json={"entries": [{"path": "Cours"}], "kind": "video"}).json()
    job = wait_job(env.client, started["job_id"])
    assert job["stage"] == "done" and job["details"]["indexed"] == 1
    video_id = job["result_id"]
    with SessionLocal() as db:
        video = db.query(Video).filter(Video.id == video_id).first()
        lib = db.query(ExternalVolume).first()
        assert video.storage_id == lib.id and video.rel_path == "Cours/Rpm 101 test.mp4" and video.file_path == f"{first_mount}/Cours/Rpm 101 test.mp4"
        assert video.duration_seconds and video.thumbnail_path and str(env.tmp) not in video.thumbnail_path
        assert video.program == "RPM"
    again = env.client.post(f"/api/storage/volumes/{vol.key}/index", json={"entries": [{"path": "Cours"}], "kind": "video"}).json()
    assert wait_job(env.client, again["job_id"])["details"]["skipped"][0]["reason"] == "already_indexed"
    return video_id


def _assert_online(env, media, video_id):
    api = env.client.get(f"/api/videos/{video_id}").json()
    assert api["available"] is True and api["external"] is True
    stream = env.client.get(f"/api/videos/{video_id}/stream", headers={"Range": "bytes=0-9"})
    assert stream.status_code == 206 and len(stream.content) == 10
    head = env.client.head(f"/api/videos/{video_id}/stream")
    assert head.status_code == 200 and int(head.headers["content-length"]) == media.video.stat().st_size
    listing = env.client.get("/api/storage/volumes").json()["volumes"][0]
    assert listing["library"]["registered"] and listing["library"]["online"] and listing["library"]["stats"]["videos"] == 1


def _assert_offline(env, vol, video_id):
    env.driver.unplug(vol.key)
    env.refresh()
    assert env.client.get(f"/api/videos/{video_id}").json()["available"] is False
    for method in (env.client.get, env.client.head):
        gone = method(f"/api/videos/{video_id}/stream")
        assert gone.status_code == 503 and gone.headers["retry-after"] == "5"
    assert codes(env.client.get(f"/api/videos/{video_id}/stream")) == "storage_unavailable"
    offline = env.client.get("/api/storage/volumes").json()["volumes"]
    assert offline[0]["connected"] is False and offline[0]["state"] == "offline" and offline[0]["library"]["online"] is False
    with SessionLocal() as db:
        row = db.query(Video).filter(Video.id == video_id).first()
        assert row is not None and row.file_path.startswith("external:") and row.rel_path == "Cours/Rpm 101 test.mp4"
    assert any(not v["available"] for v in env.client.get("/api/videos").json() if v["id"] == video_id)


def _assert_replugged_elsewhere(env, video_id, first_mount):
    env.driver.plug("sdz", "BBBB-0001", None, label="CLUB")
    env.refresh()
    new_mount = env.driver.volumes[next(iter(env.driver.volumes))].mountpoint
    assert new_mount != first_mount
    with SessionLocal() as db:
        assert db.query(Video).filter(Video.id == video_id).first().file_path == f"{new_mount}/Cours/Rpm 101 test.mp4"
    assert env.client.get(f"/api/videos/{video_id}").json()["available"] is True
    assert env.client.get(f"/api/videos/{video_id}/stream", headers={"Range": "bytes=0-4"}).status_code == 206


def _assert_read_only_library(env, media, video_id):
    on_disk = env.driver.disk_dir(next(iter(env.driver.volumes))) / "Cours" / "Rpm 101 test.mp4"
    assert env.client.put(f"/api/videos/{video_id}", json={"title": "Nouveau titre"}).status_code == 200
    assert on_disk.exists()
    normalize = env.client.post(f"/api/videos/{video_id}/normalize")
    assert normalize.status_code == 409 and normalize.json()["detail"]["code"] == "external_read_only"
    assert env.client.delete(f"/api/videos/{video_id}").status_code == 200
    assert on_disk.exists() and on_disk.read_bytes() == media.video.read_bytes()


@needs_ffmpeg
def test_library_lifecycle_unplug_replug_other_mount_point(env, media):
    vol, first_mount = _register_mounted(env, media)
    video_id = _index_course(env, vol, first_mount)
    _assert_online(env, media, video_id)
    _assert_offline(env, vol, video_id)
    _assert_replugged_elsewhere(env, video_id, first_mount)
    _assert_read_only_library(env, media, video_id)


def test_disk_images_are_never_remounted_automatically(env):
    image = env.driver.plug("loop5", "BBBB-0099", kind="image", dev_type="loop", mounted_rw=True)
    usb = env.driver.plug("sdq", "BBBB-0098", mounted_rw=True)
    env.refresh()
    _register(env, image.key)
    _register(env, usb.key)
    env.refresh()
    assert env.driver.unmount_calls == [usb.key]
    assert vol_view(env, usb.key)["mounted_read_only"] is True and vol_view(env, image.key)["mounted_read_only"] is False
    read_only = {i["id"]: i for i in vol_view(env, image.key)["longevity"]}["read_only"]
    assert read_only["status"] == "inactive"


@needs_ffmpeg
def test_unregister_requires_confirmation_and_never_deletes_files(env, media):
    vol = env.driver.plug("sda", "BBBB-0002", {"Cours/Rpm 102.mp4": media.video.read_bytes(), "Album stk/01 - a.mp3": media.audio.read_bytes()})
    env.refresh()
    _register(env, vol.key)
    jobs = [
        env.client.post(f"/api/storage/volumes/{vol.key}/index", json={"entries": [{"path": "Cours"}], "kind": "video"}).json(),
        env.client.post(f"/api/storage/volumes/{vol.key}/index", json={"entries": [{"path": "Album stk"}], "kind": "audio_course"}).json(),
    ]
    for j in jobs:
        assert wait_job(env.client, j["job_id"])["stage"] == "done"
    with SessionLocal() as db:
        assert db.query(AudioTrack).filter(AudioTrack.storage_id.isnot(None)).count() == 1
    refused = env.client.delete(f"/api/storage/volumes/{vol.key}/library")
    assert refused.status_code == 409 and codes(refused) == "has_media"
    removed = env.client.delete(f"/api/storage/volumes/{vol.key}/library", params={"purge": True})
    assert removed.status_code == 200 and removed.json()["removed"]["videos"] == 1 and removed.json()["removed"]["audio_courses"] == 1
    with SessionLocal() as db:
        assert db.query(Video).filter(Video.storage_id.isnot(None)).count() == 0 and db.query(ExternalVolume).count() == 0
    assert (env.driver.disk_dir(vol.key) / "Cours" / "Rpm 102.mp4").exists()
    assert (env.driver.disk_dir(vol.key) / "Album stk" / "01 - a.mp3").exists()


def test_portable_device_cannot_be_used_as_extension_or_written(env):
    assert env.client.get("/api/storage/portable").json()["reason"] == "missing_tool"
    assert "gvfs-backends" in env.client.get("/api/storage/portable").json()["install"]
    for action in ("index", "export"):
        response = env.client.post(f"/api/storage/volumes/p-abc123/{action}", json={"entries": [{"path": "a"}], "kind": "video", "ids": [1]})
        assert response.status_code == 409 and codes(response) in ("portable_no_direct", "read_only_device")
    assert codes(env.client.post("/api/storage/volumes/p-abc123/import", json={"entries": [{"path": "a"}], "kind": "video"})) == "not_mounted"


def test_duplicate_uuid_cannot_be_registered(env):
    a = env.driver.plug("sda", "CCCC-0001", label="A")
    b = env.driver.plug("sdb", "CCCC-0001", label="B")
    env.driver.volumes[b.key + "x"] = b.__class__(**{**b.__dict__, "key": b.key + "x", "device": "/dev/sdb1x", "name": "sdb1x"})
    env.driver.volumes.pop(b.key, None)
    env.refresh()
    views = get_volumes(env)["volumes"]
    assert len(views) == 2 and all(v["can_register"] is False and v["register_block"] == "uuid_duplicate" for v in views)
    assert codes(env.client.post(f"/api/storage/volumes/{a.key}/library", json={})) == "uuid_duplicate"


def test_startup_puts_every_external_path_in_waiting_state(env):
    from app.storage import library

    with SessionLocal() as db:
        lib = ExternalVolume(fs_uuid="FFFF-0001", label="X", kind="usb")
        db.add(lib)
        db.commit()
        video = Video(file_path="/run/media/u/X/a.mp4", title="__stk_Startup", source=ImportSource.upload, storage_id=lib.id, rel_path="a.mp4")
        db.add(video)
        db.commit()
        library.mark_all_offline(db)
        db.refresh(video)
        assert video.file_path == "external://FFFF-0001/a.mp4" and video.available is False


def test_scheduler_and_playlists_skip_unavailable_media(env):
    from app.models import Playlist, PlaylistItem, ScheduleTargetType
    from app.videos.describe import playlist_video_items
    from app.scheduling.launch import scheduled_target_unavailable

    with SessionLocal() as db:
        lib = ExternalVolume(fs_uuid="FFFF-0002", label="Y", kind="usb")
        db.add(lib)
        db.commit()
        remote_video = Video(file_path="external://FFFF-0002/a.mp4", title="__stk_Ext", source=ImportSource.upload, storage_id=lib.id, rel_path="a.mp4")
        local_video = Video(file_path="/tmp/local.mp4", title="__stk_Loc", source=ImportSource.upload)
        playlist = Playlist(name="__stk_pl")
        db.add_all([remote_video, local_video, playlist])
        db.commit()
        db.add_all([PlaylistItem(playlist_id=playlist.id, video_id=remote_video.id, position=0), PlaylistItem(playlist_id=playlist.id, video_id=local_video.id, position=1)])
        db.commit()
        db.refresh(playlist)
        assert scheduled_target_unavailable(db, ScheduleTargetType.video, remote_video.id) is True
        assert scheduled_target_unavailable(db, ScheduleTargetType.video, local_video.id) is False
        assert scheduled_target_unavailable(db, ScheduleTargetType.playlist, playlist.id) is False
        assert [i["title"] for i in playlist_video_items(playlist)] == ["__stk_Loc"]
        availability.set_online({lib.id: "/mnt/y"})
        assert [i["title"] for i in playlist_video_items(playlist)] == ["__stk_Ext", "__stk_Loc"]
        availability.set_online({})
        db.query(PlaylistItem).filter(PlaylistItem.playlist_id == playlist.id).delete()
        db.query(Playlist).filter(Playlist.id == playlist.id).delete()
        db.commit()


def test_radio_engine_skips_tracks_of_unplugged_storage():
    import asyncio

    from app.radio.manager import RadioPlaybackManager

    async def noop(message):
        return None

    availability.set_online({7: "/mnt/z"})
    tracks = [{"id": 1, "title": "a", "storage_id": None}, {"id": 2, "title": "b", "storage_id": 7}, {"id": 3, "title": "c", "storage_id": 7}, {"id": 4, "title": "d", "storage_id": None}]

    async def scenario():
        manager = RadioPlaybackManager(noop)
        await manager.load_playlist(1, "pl", tracks, shuffle=False, repeat="playlist")
        assert [t["id"] for t in manager.state["order"]] == [1, 2, 3, 4]
        availability.set_online({})
        await manager._advance_or_stop()
        assert manager.state["current_track"]["id"] == 4
        await manager._advance_or_stop()
        assert manager.state["current_track"]["id"] == 1
        reloaded = RadioPlaybackManager(noop)
        await reloaded.load_playlist(1, "pl", tracks, shuffle=False)
        assert [t["id"] for t in reloaded.state["order"]] == [1, 4]
        all_gone = RadioPlaybackManager(noop)
        await all_gone.load_playlist(1, "pl", [tracks[1], tracks[2]], repeat="playlist")
        assert all_gone.state["state"] == "idle" and all_gone.state["current_track"] is None

    try:
        asyncio.run(scenario())
    finally:
        availability.set_online({})
