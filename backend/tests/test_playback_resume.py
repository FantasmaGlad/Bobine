import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes.playback import state as state_routes
from app.models import Base, ExternalVolume, ImportSource, PlaybackState, Playlist, PlaylistItem, Video


class _Manager:
    def __init__(self):
        self.calls = []

    async def load(self, *args, **kwargs):
        self.calls.append(("load", args, kwargs))

    async def load_playlist(self, *args, **kwargs):
        self.calls.append(("load_playlist", args, kwargs))

    async def seek(self, position):
        self.calls.append(("seek", (position,), {}))


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture()
def manager(monkeypatch):
    fake = _Manager()
    monkeypatch.setattr(state_routes, "get_playback_manager", lambda channel: fake)
    return fake


def _video(db, title, **extra):
    video = Video(file_path=f"/tmp/{title}.mp4", title=title, source=ImportSource.upload, thumbnail_path=f"thumbs/{title}.jpg", **extra)
    db.add(video)
    db.commit()
    return video


def _resume(db):
    return asyncio.run(state_routes.resume_interrupted_state(channel="cable", db=db))


def test_resume_without_pending_action_is_not_found(db, manager):
    with pytest.raises(HTTPException) as exc:
        _resume(db)
    assert exc.value.status_code == 404 and manager.calls == []


def test_resume_reloads_interrupted_video_at_its_position(db, manager):
    video = _video(db, "a", duration_seconds=600.0)
    db.add(PlaybackState(video_id=video.id, position_seconds=42.5, cause="schedule", channel="cable"))
    db.commit()
    assert _resume(db) == {"message": "Lecture reprise"}
    (name, args, kwargs), seek = manager.calls
    assert name == "load" and args == (video.id, "a", 600.0, None) and kwargs["thumbnail_url"] == "a.jpg"
    assert seek == ("seek", (42.5,), {})
    assert db.query(PlaybackState).count() == 0


def test_resume_of_missing_video_discards_the_pending_action(db, manager):
    db.add(PlaybackState(video_id=999, position_seconds=1.0, cause="schedule", channel="cable"))
    db.commit()
    with pytest.raises(HTTPException) as exc:
        _resume(db)
    assert exc.value.status_code == 404 and db.query(PlaybackState).count() == 0


def test_postponed_playlist_relaunch_skips_unavailable_videos(db, manager):
    volume = ExternalVolume(fs_uuid="FFFF-0009", label="Z", kind="usb")
    db.add(volume)
    db.commit()
    kept, offline = _video(db, "kept"), _video(db, "offline", storage_id=volume.id, rel_path="offline.mp4")
    playlist = Playlist(name="pl")
    db.add(playlist)
    db.flush()
    db.add_all([PlaylistItem(playlist_id=playlist.id, video_id=offline.id, position=0),
                PlaylistItem(playlist_id=playlist.id, video_id=kept.id, position=1)])
    db.add(PlaybackState(cause="coach_priority", target_type="playlist", target_id=playlist.id, channel="cable"))
    db.commit()
    assert _resume(db) == {"message": "Programmation relancée"}
    [(name, (playlist_id, playlist_name, items), _)] = manager.calls
    assert (name, playlist_id, playlist_name) == ("load_playlist", playlist.id, "pl")
    assert [item["title"] for item in items] == ["kept"]
