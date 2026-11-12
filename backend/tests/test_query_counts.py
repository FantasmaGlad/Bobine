"""Régression N+1 : les routes de LISTE (et les détails de playlists) doivent émettre un nombre de requêtes SQL constant, indépendant du nombre de lignes."""

import os

os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")
os.environ.setdefault("BOBINE_MEDIA_DIR", "data/test_videos")
os.environ.setdefault("BOBINE_WATCH_DIR", "data/test_watched")
os.environ.setdefault("BOBINE_THUMBNAILS_DIR", "data/test_thumbnails")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import event  # noqa: E402

from app import database  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    AudioCourse,
    AudioPlaylist,
    AudioPlaylistItem,
    AudioTrack,
    Background,
    ImportSource,
    Playlist,
    PlaylistItem,
    RadioPlaylist,
    RadioPlaylistItem,
    RadioTag,
    RadioTrack,
    Video,
)

ROWS = 12
PREFIX = "qcount-"
MAX_QUERIES = 6


@pytest.fixture(scope="module")
def seeded():
    database.init_db()
    db = database.SessionLocal()
    try:
        bg = Background(file_path=f"{PREFIX}bg.mp4", title=f"{PREFIX}bg")
        tags = [RadioTag(name=f"{PREFIX}tag{i}") for i in range(3)]
        videos = [
            Video(file_path=f"{PREFIX}v{i}.mp4", title=f"{PREFIX}v{i}", duration_seconds=60.0,
                  thumbnail_path=f"{PREFIX}v{i}.jpg", source=ImportSource.upload)
            for i in range(ROWS)
        ]
        db.add_all([bg, *tags, *videos])
        db.flush()

        radio_tracks = []
        for i in range(ROWS):
            t = RadioTrack(file_path=f"{PREFIX}r{i}.mp3", title=f"{PREFIX}r{i}", duration_seconds=100.0,
                           cover_path=f"{PREFIX}r{i}.jpg", source=ImportSource.upload)
            t.tags = [tags[i % 3], tags[(i + 1) % 3]]
            radio_tracks.append(t)
        db.add_all(radio_tracks)

        courses = []
        for c in range(ROWS):
            course = AudioCourse(title=f"{PREFIX}c{c}", program="P", background_id=bg.id)
            course.tracks = [
                AudioTrack(number=k, title=f"{PREFIX}c{c}t{k}", file_path=f"{PREFIX}a{c}-{k}.mp3",
                           duration_seconds=10.0, position=k, background_id=bg.id)
                for k in range(3)
            ]
            courses.append(course)
        db.add_all(courses)
        db.flush()

        playlist = Playlist(name=f"{PREFIX}pl")
        playlist.items = [PlaylistItem(video_id=v.id, position=i) for i, v in enumerate(videos)]
        radio_playlist = RadioPlaylist(name=f"{PREFIX}rpl")
        radio_playlist.items = [
            RadioPlaylistItem(radio_track_id=t.id, position=i) for i, t in enumerate(radio_tracks)
        ]
        audio_playlist = AudioPlaylist(name=f"{PREFIX}apl")
        audio_playlist.items = [
            AudioPlaylistItem(audio_track_id=course.tracks[0].id, position=i, background_id=bg.id)
            for i, course in enumerate(courses)
        ]
        db.add_all([playlist, radio_playlist, audio_playlist])
        db.commit()
        yield {
            "playlist": playlist.id,
            "radio_playlist": radio_playlist.id,
            "audio_playlist": audio_playlist.id,
            "course": courses[0].id,
        }
    finally:
        db.rollback()
        _purge(db)
        db.close()


def _purge(db) -> None:
    for playlist_model, item_model, fk in (
        (AudioPlaylist, AudioPlaylistItem, AudioPlaylistItem.playlist_id),
        (RadioPlaylist, RadioPlaylistItem, RadioPlaylistItem.playlist_id),
        (Playlist, PlaylistItem, PlaylistItem.playlist_id),
    ):
        owned = [p.id for p in db.query(playlist_model).filter(playlist_model.name.like(f"{PREFIX}%"))]
        if owned:
            db.query(item_model).filter(fk.in_(owned)).delete(synchronize_session=False)
            db.query(playlist_model).filter(playlist_model.id.in_(owned)).delete(synchronize_session=False)
    db.query(AudioTrack).filter(AudioTrack.file_path.like(f"{PREFIX}%")).delete(synchronize_session=False)
    db.query(AudioCourse).filter(AudioCourse.title.like(f"{PREFIX}%")).delete(synchronize_session=False)
    for track in db.query(RadioTrack).filter(RadioTrack.file_path.like(f"{PREFIX}%")).all():
        db.delete(track)
    db.query(RadioTag).filter(RadioTag.name.like(f"{PREFIX}%")).delete(synchronize_session=False)
    db.query(Video).filter(Video.file_path.like(f"{PREFIX}%")).delete(synchronize_session=False)
    db.query(Background).filter(Background.file_path.like(f"{PREFIX}%")).delete(synchronize_session=False)
    db.commit()


def _count_queries(client: TestClient, url: str) -> tuple[int, object]:
    statements: list[str] = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(database.engine, "before_cursor_execute", _record)
    try:
        response = client.get(url)
    finally:
        event.remove(database.engine, "before_cursor_execute", _record)
    assert response.status_code == 200, (url, response.status_code, response.text[:200])
    return len(statements), response.json()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.mark.parametrize(
    "template",
    [
        "/api/radio/tracks",
        "/api/radio/tracks?tag=" + PREFIX + "tag0",
        "/api/playlists",
        "/api/playlists/{playlist}",
        "/api/radio/playlists",
        "/api/radio/playlists/{radio_playlist}",
        "/api/audio",
        "/api/audio/tracks",
        "/api/audio/{course}",
        "/api/audio-playlists",
        "/api/audio-playlists/{audio_playlist}",
    ],
)
def test_list_routes_issue_a_constant_number_of_queries(client, seeded, template):
    url = template.format(**seeded)
    queries, _ = _count_queries(client, url)
    assert queries <= MAX_QUERIES, f"{url} : {queries} requêtes SQL (N+1 ?)"


def test_radio_tracks_tags_are_still_returned_with_the_eager_load(client, seeded):
    _, body = _count_queries(client, "/api/radio/tracks")
    ours = [t for t in body if t["title"].startswith(PREFIX)]
    assert len(ours) == ROWS
    assert all(len(t["tags"]) == 2 for t in ours)
