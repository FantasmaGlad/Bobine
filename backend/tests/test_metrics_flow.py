import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

# Add backend directory to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_metrics_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_metrics_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_metrics_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_metrics_thumbnails"

from fastapi import HTTPException

from app.config import settings
from app.database import SessionLocal, init_db
from app.models import CourseRating, ImportSource, PlaybackSession, Video
from app.routers.metrics import (
    RatingCreate,
    create_course_rating,
    get_metrics_dashboard,
    list_course_ratings,
)
from app.routers.settings import get_storage, get_system_usage
from app.utils.hardware_info import (
    get_cpu_model_name,
    get_cpu_temp,
    get_gpu_info,
    get_power_watts,
    get_ram_info,
    get_runtime_info,
    get_storage_model,
)
from app.utils.playback_session_tracker import (
    close_playback_session,
    start_playback_session,
    update_playback_session_progress,
)


class TestMetricsFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    @classmethod
    def tearDownClass(cls):
        from app.database import engine
        engine.dispose()
        db_path = Path(settings.database_url.replace("sqlite:///", ""))
        if db_path.exists():
            try:
                db_path.unlink()
            except Exception:
                pass

    def setUp(self):
        # Clean up database tables for each test
        with SessionLocal() as db:
            db.query(CourseRating).delete()
            db.query(PlaybackSession).delete()
            db.query(Video).delete()
            db.commit()

            # Insert sample video
            self.video = Video(
                file_path="/media/test_rpm.mp4",
                title="RPM 100",
                program="RPM",
                duration_seconds=3000.0,
                source=ImportSource.upload,
            )
            db.add(self.video)
            db.commit()
            db.refresh(self.video)
            self.video_id = self.video.id

    def test_playback_session_lifecycle_completed(self):
        """Teste le cycle de vie d'une session terminée avec complétion (>= 90%)."""
        with SessionLocal() as db:
            sess_id = start_playback_session(
                db, video_id=self.video_id, channel="cable", launch_type="grid", total_duration_seconds=3000.0
            )
            self.assertIsNotNone(sess_id)

            update_playback_session_progress(db, sess_id, 1500.0)
            s = db.query(PlaybackSession).filter(PlaybackSession.id == sess_id).first()
            self.assertEqual(s.duration_played_seconds, 1500.0)
            self.assertFalse(s.completed)

            # Visionnage jusqu'à 2750s (> 90% de 3000s = 2700s)
            close_playback_session(db, sess_id, position_seconds=2750.0)
            s = db.query(PlaybackSession).filter(PlaybackSession.id == sess_id).first()
            self.assertTrue(s.completed)
            self.assertIsNotNone(s.ended_at)
            self.assertEqual(s.duration_played_seconds, 2750.0)

    def test_playback_session_lifecycle_abandoned(self):
        """Teste le cycle de vie d'une session abandonnée (< 90%)."""
        with SessionLocal() as db:
            sess_id = start_playback_session(
                db, video_id=self.video_id, channel="network", launch_type="kiosk", total_duration_seconds=3000.0
            )
            self.assertIsNotNone(sess_id)

            # Abandon à 600s (20%)
            close_playback_session(db, sess_id, position_seconds=600.0)
            s = db.query(PlaybackSession).filter(PlaybackSession.id == sess_id).first()
            self.assertFalse(s.completed)
            self.assertEqual(s.duration_played_seconds, 600.0)

    def test_rating_api_flow(self):
        """Teste les endpoints de notation 5 étoiles."""
        with SessionLocal() as db:
            # 1. Notation valide
            r1 = create_course_rating(
                RatingCreate(video_id=self.video_id, rating=5, channel="cable", source="grid"),
                db=db,
            )
            self.assertEqual(r1["rating"], 5)
            self.assertEqual(r1["source"], "grid")

            # 2. Deuxième note
            r2 = create_course_rating(
                RatingCreate(video_id=self.video_id, rating=4, channel="cable", source="cinema"),
                db=db,
            )
            self.assertEqual(r2["rating"], 4)

            # 3. Vidéo inexistante -> 404
            with self.assertRaises(HTTPException) as cm:
                create_course_rating(
                    RatingCreate(video_id=99999, rating=5, channel="cable", source="grid"),
                    db=db,
                )
            self.assertEqual(cm.exception.status_code, 404)

            # 4. Lister les notes
            ratings = list_course_ratings(video_id=self.video_id, db=db)
            self.assertEqual(len(ratings), 2)

    def test_dashboard_aggregation(self):
        """Teste l'agrégation complète du tableau de bord /api/metrics/dashboard."""
        with SessionLocal() as db:
            s1 = start_playback_session(db, self.video_id, "cable", "grid", 3000.0)
            close_playback_session(db, s1, position_seconds=2800.0)  # completed

            s2 = start_playback_session(db, self.video_id, "cable", "cinema", 3000.0)
            close_playback_session(db, s2, position_seconds=500.0)  # abandoned

            # Insérer un avis
            r = CourseRating(
                video_id=self.video_id,
                rating=5,
                channel="cable",
                source="grid",
                created_at=datetime.now(timezone.utc),
            )
            db.add(r)
            db.commit()

            data = get_metrics_dashboard(period="30d", channel="all", db=db)

        # KPIs
        kpis = data["kpis"]
        self.assertEqual(kpis["sessions"]["total"], 2)
        self.assertEqual(kpis["completion"]["completed_sessions"], 1)
        self.assertEqual(kpis["completion"]["rate"], 50.0)
        self.assertEqual(kpis["satisfaction"]["average"], 5.0)
        self.assertEqual(kpis["satisfaction"]["total_count"], 1)
        self.assertEqual(kpis["satisfaction"]["distribution"]["5"], 1)

        # Volume
        self.assertGreater(kpis["broadcast"]["total_seconds"], 3000.0)

        # Distribution horaire
        self.assertEqual(len(data["hourly_distribution"]), 24)

        # Classement cours
        stats = data["course_stats"]
        self.assertGreaterEqual(len(stats), 1)
        rpm = next(c for c in stats if c["video_id"] == self.video_id)
        self.assertEqual(rpm["sessions_count"], 2)
        self.assertEqual(rpm["average_rating"], 5.0)

        # Télémétrie matérielle
        hw = data["hardware"]
        self.assertIn("cpu_name", hw)
        self.assertIn("gpu_name", hw)
        self.assertIn("storage_model", hw)
        self.assertIn("ram_model", hw)
        self.assertIn("ram_type", hw)
        self.assertIn("runtime", hw)

    def test_hardware_supervision_endpoints(self):
        """Teste l'enrichissement de /api/settings/system et /api/settings/storage."""
        d = get_system_usage()
        self.assertIn("cpu_percent", d)
        self.assertIn("cpu_name", d)
        self.assertIn("gpu_name", d)
        self.assertIn("storage_model", d)
        self.assertIn("ram_model", d)
        self.assertIn("ram_type", d)
        self.assertIn("ram_brand", d)
        self.assertIn("ram_freq", d)
        self.assertIn("runtime", d)

        s = get_storage()
        self.assertIn("storage_model", s)
        self.assertIn("used_percent", s)

    def test_hardware_helpers(self):
        """Valide que les fonctions hardware_info ne lèvent pas d'exception."""
        cpu = get_cpu_model_name()
        self.assertIsInstance(cpu, str)
        self.assertGreater(len(cpu), 0)

        gpu_name, gpu_pct, gpu_temp = get_gpu_info()
        self.assertIsInstance(gpu_name, str)

        storage = get_storage_model()
        self.assertIsInstance(storage, str)

        ram = get_ram_info()
        self.assertIsInstance(ram, dict)
        self.assertIn("model_label", ram)

        runtime = get_runtime_info()
        self.assertIn("service_uptime_formatted", runtime)
