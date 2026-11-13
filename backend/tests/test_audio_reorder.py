import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AudioCourse, AudioTrack  # noqa: E402


def test_reorder_is_not_taken_for_a_track_id():
    init_db()
    with SessionLocal() as db:
        course = AudioCourse(title="Ordre des pistes")
        db.add(course)
        db.flush()
        first = AudioTrack(audio_course_id=course.id, number=1, title="A", file_path="data/test_audio/reorder_a.mp3", position=0)
        second = AudioTrack(audio_course_id=course.id, number=2, title="B", file_path="data/test_audio/reorder_b.mp3", position=1)
        db.add_all([first, second])
        db.commit()
        ids = (course.id, first.id, second.id)
    try:
        answer = TestClient(app).put(f"/api/audio/{ids[0]}/tracks/reorder", json={"track_ids": [ids[2], ids[1]]})
        assert answer.status_code == 200, answer.text
        assert [track["id"] for track in answer.json()["tracks"]] == [ids[2], ids[1]]
    finally:
        with SessionLocal() as db:
            db.query(AudioTrack).filter(AudioTrack.audio_course_id == ids[0]).delete()
            db.query(AudioCourse).filter(AudioCourse.id == ids[0]).delete()
            db.commit()
