import os
import sys
import io
import asyncio
import shutil
import unittest
import subprocess
from pathlib import Path
from unittest.mock import patch

# Add backend directory to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Set test directories before importing config
os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

from app.config import settings
from app.database import init_db, SessionLocal, get_db
from app.models import Video, ImportSource
from app.utils.video_utils import extract_metadata, check_compatibility, generate_thumbnail, read_mp4_duration_seconds
from app.utils.importer import import_video
from app.routers.videos import VideoUpdate, update_video, upload_video_thumbnail


class TestVideoFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create directories if they do not exist
        Path(settings.media_dir).mkdir(parents=True, exist_ok=True)
        Path(settings.watch_dir).mkdir(parents=True, exist_ok=True)
        Path(settings.thumbnails_dir).mkdir(parents=True, exist_ok=True)

        cls.dummy_compatible_path = str(Path(settings.watch_dir) / "test_RPM_98_compatible.mp4")
        cls.dummy_incompatible_path = str(Path(settings.watch_dir) / "test_Sprint_35_incompatible.mkv")

        print("Generating compatible test video with ffmpeg...")
        # H264 + AAC MP4 (Direct Play compatible). `-movflags +faststart` place
        # l'atome moov en tête : sans lui, check_compatibility déclencherait un
        # remux_faststart (réf. correctif "kiosk/réseau figé sur la première
        # frame") — une vidéo réellement optimisée web ne nécessite aucune
        # normalisation, ce que ce test valide.
        cmd_comp = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=1",
            "-c:v", "libx264", "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            cls.dummy_compatible_path
        ]
        subprocess.run(cmd_comp, capture_output=True, check=True)

        print("Generating incompatible test video with ffmpeg...")
        # H264 + AC-3 MKV (Needs normalization)
        cmd_incomp = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=1",
            "-c:v", "libx264", "-c:a", "ac3",
            "-pix_fmt", "yuv420p",
            cls.dummy_incompatible_path
        ]
        subprocess.run(cmd_incomp, capture_output=True, check=True)

    @classmethod
    def tearDownClass(cls):
        # Dispose engine to release file locks
        from app.database import engine
        engine.dispose()
        # Clean up database file
        db_path = Path(settings.database_url.replace("sqlite:///", ""))
        if db_path.exists():
            try:
                db_path.unlink()
            except PermissionError:
                pass


        # Clean up directories
        for d in [settings.media_dir, settings.watch_dir, settings.thumbnails_dir]:
            p = Path(d)
            if p.exists():
                shutil.rmtree(p)

    def setUp(self):
        # Initialize Database schema
        init_db()
        self.db = SessionLocal()

    def tearDown(self):
        self.db.query(Video).delete()
        self.db.commit()
        self.db.close()

    def test_01_extract_metadata_compatible(self):
        meta = extract_metadata(self.dummy_compatible_path)
        self.assertIsNotNone(meta["duration_seconds"])
        self.assertEqual(meta["width"], 320)
        self.assertEqual(meta["height"], 240)
        self.assertEqual(meta["codec"], "h264")
        self.assertEqual(meta["audio_codec"], "aac")
        self.assertFalse(meta["is_drm"])

        compat = check_compatibility(meta, self.dummy_compatible_path)
        self.assertTrue(compat["is_compatible"])
        self.assertFalse(compat["needs_normalization"])

    def test_02_extract_metadata_incompatible(self):
        meta = extract_metadata(self.dummy_incompatible_path)
        self.assertIsNotNone(meta["duration_seconds"])
        self.assertEqual(meta["codec"], "h264")
        self.assertEqual(meta["audio_codec"], "ac3")
        self.assertFalse(meta["is_drm"])

        compat = check_compatibility(meta, self.dummy_incompatible_path)
        self.assertFalse(compat["is_compatible"])
        self.assertTrue(compat["needs_normalization"])
        self.assertIn("recode_audio", compat["actions"])
        self.assertIn("recode_container", compat["actions"])

    def test_03_generate_thumbnail(self):
        thumb_path = generate_thumbnail(
            self.dummy_compatible_path,
            settings.thumbnails_dir,
            1.0
        )
        self.assertTrue(os.path.exists(thumb_path))
        self.assertTrue(Path(thumb_path).is_file())

    def test_04_import_video_direct_play(self):
        # Create a temp copy of compatible to import (since importer moves/deletes source)
        temp_src = str(Path(settings.watch_dir) / "temp_compatible_import.mp4")
        shutil.copy(self.dummy_compatible_path, temp_src)

        video = import_video(temp_src, "RPM 98 Compatible.mp4", ImportSource.upload)
        self.assertIsNotNone(video.id)
        self.assertEqual(video.program, "RPM")
        self.assertEqual(video.release, "98")
        self.assertTrue(os.path.exists(video.file_path))
        self.assertTrue(os.path.exists(video.thumbnail_path))

    def test_05_import_video_with_normalization(self):
        # Create a temp copy of incompatible to import
        temp_src = str(Path(settings.watch_dir) / "temp_incompatible_import.mkv")
        shutil.copy(self.dummy_incompatible_path, temp_src)

        video = import_video(temp_src, "Sprint 35 Incompatible.mkv", ImportSource.watched_folder)
        self.assertIsNotNone(video.id)
        self.assertEqual(video.program, "Sprint")
        self.assertEqual(video.release, "35")
        self.assertTrue(os.path.exists(video.file_path))
        self.assertTrue(video.file_path.endswith(".mp4"))
        self.assertTrue(os.path.exists(video.thumbnail_path))

        # Check metadata of final file - should be H.264 / AAC / MP4
        meta = extract_metadata(video.file_path)
        self.assertEqual(meta["audio_codec"], "aac")
        self.assertEqual(meta["codec"], "h264")

    def test_06_video_metadata_rename_flow(self):
        temp_src = str(Path(settings.watch_dir) / "temp_rename_test.mp4")
        shutil.copy(self.dummy_compatible_path, temp_src)

        video = import_video(temp_src, "Initial Title.mp4", ImportSource.upload)
        old_file_path = video.file_path
        self.assertTrue(os.path.exists(old_file_path))

        # Trigger metadata update with new title
        payload = VideoUpdate(title="Updated Title RPM 99", program="RPM", release="99")
        updated_video = update_video(video.id, payload, self.db)

        # Check DB title updated
        self.assertEqual(updated_video.title, "Updated Title RPM 99")
        self.assertEqual(updated_video.release, "99")

        # Check physical file is renamed
        new_file_path = updated_video.file_path
        self.assertNotEqual(old_file_path, new_file_path)
        self.assertFalse(os.path.exists(old_file_path))
        self.assertTrue(os.path.exists(new_file_path))
        self.assertIn("Updated_Title_RPM_99", new_file_path)

    def test_07_import_video_without_ffprobe(self):
        # Réf. Lot 8 (docs/plan-implementation-android.md) : sous Android, ni
        # ffprobe ni ffmpeg ne sont utilisables (aucun binaire ne survit au
        # filtre seccomp). Ce test simule exactement l'erreur réelle observée
        # sur tablette pour vérifier que l'import aboutit quand même : la
        # durée est récupérée par repli pur Python (mvhd, cf.
        # read_mp4_duration_seconds), mais largeur/hauteur/codec/miniature
        # restent absents.
        temp_src = str(Path(settings.watch_dir) / "temp_no_ffprobe_import.mp4")
        shutil.copy(self.dummy_compatible_path, temp_src)

        with patch(
            "app.utils.importer.extract_metadata",
            side_effect=FileNotFoundError(2, "No such file or directory", "ffprobe"),
        ), patch(
            "app.utils.importer.generate_thumbnail",
            side_effect=FileNotFoundError(2, "No such file or directory", "ffmpeg"),
        ):
            video = import_video(temp_src, "RPM 108.mp4", ImportSource.upload)

        self.assertIsNotNone(video.id)
        self.assertEqual(video.program, "RPM")
        self.assertTrue(os.path.exists(video.file_path))
        self.assertIsNotNone(video.duration_seconds)
        self.assertAlmostEqual(video.duration_seconds, 1.0, delta=0.5)
        self.assertIsNone(video.width)
        self.assertIsNone(video.height)
        self.assertIsNone(video.codec)
        self.assertIsNone(video.thumbnail_path)

    def test_08_read_mp4_duration_seconds(self):
        # Vérifie le repli pur Python directement (indépendamment de
        # l'import) contre le fichier de test généré par ffmpeg en
        # setUpClass — évite de dépendre uniquement d'un test bout-en-bout
        # pour couvrir ses cas limites (mauvaise extension, fichier absent).
        duration = read_mp4_duration_seconds(self.dummy_compatible_path)
        self.assertIsNotNone(duration)
        self.assertAlmostEqual(duration, 1.0, delta=0.5)

        self.assertIsNone(read_mp4_duration_seconds("/chemin/inexistant.mp4"))
        # Un conteneur sans atome 'moov' (ex. le .mkv de test) doit renvoyer
        # None proprement, jamais lever.
        self.assertIsNone(read_mp4_duration_seconds(self.dummy_incompatible_path))

    def test_09_upload_video_thumbnail(self):
        # Réf. retour utilisateur "comment avoir une miniature alors ?" (Lot 8
        # bloque generate_thumbnail, qui dépend de ffmpeg) : miniature fournie
        # manuellement par l'admin, décodée avec Pillow seul (aucune vidéo à
        # décoder), même chemin que _import_background_image().
        from PIL import Image
        from fastapi import UploadFile

        temp_src = str(Path(settings.watch_dir) / "temp_thumb_test.mp4")
        shutil.copy(self.dummy_compatible_path, temp_src)
        # ffmpeg est disponible dans cet environnement de test (contrairement
        # à Android) : l'import produit déjà une miniature normale ici — ce
        # test vérifie le REMPLACEMENT par une miniature manuelle, un cas
        # tout aussi réel (l'admin n'aime pas la miniature auto) que le cas
        # Android (aucune miniature auto du tout).
        video = import_video(temp_src, "RPM 111.mp4", ImportSource.upload)
        self.assertIsNotNone(video.thumbnail_path)
        auto_thumb_path = Path(video.thumbnail_path)

        buf = io.BytesIO()
        Image.new("RGB", (800, 450), color=(200, 30, 30)).save(buf, "PNG")
        buf.seek(0)
        upload = UploadFile(file=buf, filename="cover.png")

        updated = asyncio.run(upload_video_thumbnail(video.id, upload, self.db))
        self.assertIsNotNone(updated.thumbnail_path)
        first_thumb_path = Path(updated.thumbnail_path)
        self.assertTrue(first_thumb_path.exists())
        self.assertNotEqual(first_thumb_path, auto_thumb_path)
        # La miniature auto générée par ffmpeg à l'import est remplacée et
        # nettoyée, comme n'importe quel remplacement ci-dessous.
        self.assertFalse(auto_thumb_path.exists())

        # Un second envoi doit remplacer la miniature ET nettoyer l'ancien
        # fichier (pas d'orphelin accumulé à chaque remplacement).
        buf2 = io.BytesIO()
        Image.new("RGB", (800, 450), color=(30, 200, 30)).save(buf2, "PNG")
        buf2.seek(0)
        upload2 = UploadFile(file=buf2, filename="cover2.png")
        updated2 = asyncio.run(upload_video_thumbnail(video.id, upload2, self.db))
        self.assertNotEqual(updated2.thumbnail_path, str(first_thumb_path))
        self.assertFalse(first_thumb_path.exists())
        self.assertTrue(Path(updated2.thumbnail_path).exists())

        # Un fichier qui n'est pas une image doit être rejeté (400), pas planter.
        from fastapi import HTTPException
        bad_upload = UploadFile(file=io.BytesIO(b"not an image"), filename="bad.png")
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(upload_video_thumbnail(video.id, bad_upload, self.db))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_10_target_bitrate_heavy_video_4k_60(self):
        from app.utils.video_utils import _get_target_bitrate
        self.assertEqual(_get_target_bitrate(3840, 2160), "28M")  # 4K
        self.assertEqual(_get_target_bitrate(2560, 1440), "14M")  # 2K
        self.assertEqual(_get_target_bitrate(1920, 1080), "6M")   # 1080p
        self.assertEqual(_get_target_bitrate(1280, 720), "6M")    # 720p

    def test_11_encoder_args_multi_os(self):
        from app.utils.video_utils import _get_encoder_args
        args_android, name_android = _get_encoder_args(is_android=True, width=1920, height=1080)
        self.assertEqual(name_android, "h264_mediacodec")
        self.assertIn("-operating_rate", args_android)
        self.assertIn("1000", args_android)
        self.assertIn("nv12", args_android)

    def test_12_cancel_import_job(self):
        from app.utils.import_jobs import create_job, cancel_job, is_job_cancelled, get_job, JobCancelledError
        job_id = create_job("video", "cancel_test.mp4")
        self.assertFalse(is_job_cancelled(job_id))
        
        cancelled = cancel_job(job_id)
        self.assertTrue(cancelled)
        self.assertTrue(is_job_cancelled(job_id))
        
        job = get_job(job_id)
        self.assertIsNotNone(job)
        self.assertEqual(job["stage"], "cancelled")

        # Vérifier que import_video lève JobCancelledError immédiatement si annulé
        with self.assertRaises(JobCancelledError):
            import_video(self.dummy_compatible_path, "cancelled_import.mp4", ImportSource.upload, job_id=job_id)
        
        # Vérifier qu'aucune vidéo n'a été insérée en base
        self.assertEqual(self.db.query(Video).count(), 0)


if __name__ == "__main__":
    unittest.main()

