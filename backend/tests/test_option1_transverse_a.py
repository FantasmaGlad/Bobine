import asyncio
import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add backend directory to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Isolate database and directories for test
TEST_DIR = Path(__file__).resolve().parent / "data_test_option1"
os.environ["BOBINE_DATABASE_URL"] = f"sqlite:///{TEST_DIR}/database.db"
os.environ["BOBINE_MEDIA_DIR"] = str(TEST_DIR / "videos")
os.environ["BOBINE_WATCH_DIR"] = str(TEST_DIR / "watched")
os.environ["BOBINE_THUMBNAILS_DIR"] = str(TEST_DIR / "thumbnails")
os.environ["BOBINE_BACKGROUNDS_DIR"] = str(TEST_DIR / "backgrounds")
os.environ["BOBINE_AUDIO_DIR"] = str(TEST_DIR / "audio")
os.environ["BOBINE_RADIO_DIR"] = str(TEST_DIR / "radio")
os.environ["BOBINE_BRANDING_DIR"] = str(TEST_DIR / "branding")
os.environ["BOBINE_LOGS_DIR"] = str(TEST_DIR / "logs")

from fastapi import HTTPException, UploadFile
from app.config import settings
from app.database import engine, init_db, SessionLocal
from app.models import Video, Setting, ImportSource
from app.routers.settings import (
    ResetDataRequest,
    export_backup,
    restore_backup,
    reset_data_system,
    get_system_usage,
)
from app.routers.updates import check_updates
from app.utils.version import get_app_version


class TestOption1TransverseA(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        TEST_DIR.mkdir(parents=True, exist_ok=True)
        init_db()

    @classmethod
    def tearDownClass(cls):
        engine.dispose()
        if TEST_DIR.exists():
            shutil.rmtree(TEST_DIR, ignore_errors=True)

    def setUp(self):
        init_db()
        # Seed test data in database
        db = SessionLocal()
        try:
            db.query(Video).delete()
            test_video = Video(
                title="Course Test 1",
                file_path=str(Path(settings.media_dir) / "course1.mp4"),
                duration_seconds=120.0,
                source=ImportSource.upload,
            )
            db.add(test_video)
            db.commit()
        finally:
            db.close()

        # Seed dummy file in media dir
        media_path = Path(settings.media_dir)
        media_path.mkdir(parents=True, exist_ok=True)
        (media_path / "course1.mp4").write_bytes(b"dummy video data")

    # -----------------------------------------------------------------------
    # Part 1: Profile-aware updates
    # -----------------------------------------------------------------------

    async def test_check_updates_offline(self):
        """Vérifie que check_updates gère le mode hors-ligne sans planter."""
        with patch("urllib.request.urlopen", side_effect=OSError("Offline")):
            res = await check_updates(db=SessionLocal())
            self.assertFalse(res["online"])
            self.assertIn("deployment_profile", res)
            self.assertIn("can_auto_apply", res)
            self.assertIsNone(res["download_url"])

    async def test_check_updates_profile_asset_matching(self):
        """Vérifie que chaque profil sélectionne l'asset adapté (.exe, .deb, .dmg)."""
        mock_release = {
            "tag_name": "V9.9.9",
            "name": "Bobine V9.9.9",
            "body": "Release notes test",
            "published_at": "2026-09-06T12:00:00Z",
            "html_url": "https://github.com/FantasmaGlad/Bobine/releases/tag/V9.9.9",
            "assets": [
                {
                    "name": "Bobine-Setup-9.9.9.exe",
                    "browser_download_url": "https://github.com/FantasmaGlad/Bobine/releases/download/V9.9.9/Bobine-Setup-9.9.9.exe",
                    "size": 65000000,
                },
                {
                    "name": "bobine_9.9.9_amd64.deb",
                    "browser_download_url": "https://github.com/FantasmaGlad/Bobine/releases/download/V9.9.9/bobine_9.9.9_amd64.deb",
                    "size": 48000000,
                },
                {
                    "name": "Bobine-9.9.9.dmg",
                    "browser_download_url": "https://github.com/FantasmaGlad/Bobine/releases/download/V9.9.9/Bobine-9.9.9.dmg",
                    "size": 55000000,
                },
            ],
        }

        # Mock urllib.request
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(mock_release).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        # Test Windows profile
        with patch("urllib.request.urlopen", return_value=mock_resp), \
             patch("app.routers.updates.get_deployment_profile", return_value="windows"), \
             patch("app.routers.updates.get_profile_handler") as mock_handler:
            mock_handler.return_value.supports_git_versioning.return_value = False
            res = await check_updates(db=SessionLocal())
            self.assertTrue(res["online"])
            self.assertTrue(res["has_update"])
            self.assertFalse(res["can_auto_apply"])
            self.assertEqual(res["asset_name"], "Bobine-Setup-9.9.9.exe")
            self.assertTrue(res["download_url"].endswith(".exe"))

        # Test Linux Desktop profile (.deb)
        with patch("urllib.request.urlopen", return_value=mock_resp), \
             patch("app.routers.updates.get_deployment_profile", return_value="linux-desktop"), \
             patch("app.routers.updates.get_profile_handler") as mock_handler:
            mock_handler.return_value.supports_git_versioning.return_value = False
            res = await check_updates(db=SessionLocal())
            self.assertEqual(res["asset_name"], "bobine_9.9.9_amd64.deb")
            self.assertTrue(res["download_url"].endswith(".deb"))

        # Test macOS profile (.dmg)
        with patch("urllib.request.urlopen", return_value=mock_resp), \
             patch("app.routers.updates.get_deployment_profile", return_value="macos"), \
             patch("app.routers.updates.get_profile_handler") as mock_handler:
            mock_handler.return_value.supports_git_versioning.return_value = False
            res = await check_updates(db=SessionLocal())
            self.assertEqual(res["asset_name"], "Bobine-9.9.9.dmg")
            self.assertTrue(res["download_url"].endswith(".dmg"))

        # Test Linux Headless appliance (git auto-apply)
        with patch("urllib.request.urlopen", return_value=mock_resp), \
             patch("app.routers.updates.get_deployment_profile", return_value="linux-headless"), \
             patch("app.routers.updates.get_profile_handler") as mock_handler:
            mock_handler.return_value.supports_git_versioning.return_value = True
            res = await check_updates(db=SessionLocal())
            self.assertTrue(res["can_auto_apply"])

    # -----------------------------------------------------------------------
    # Part 2: Universal Backup & Restore
    # -----------------------------------------------------------------------

    def test_export_backup(self):
        """Vérifie la génération d'une archive ZIP de sauvegarde valide."""
        response = export_backup()
        self.assertEqual(response.media_type, "application/zip")
        self.assertIn("attachment; filename=", response.headers.get("Content-Disposition", ""))

        # Vérification du contenu du ZIP
        buf = io.BytesIO(response.body)
        self.assertTrue(zipfile.is_zipfile(buf))
        with zipfile.ZipFile(buf, "r") as zf:
            namelist = zf.namelist()
            self.assertIn("manifest.json", namelist)
            self.assertIn("database.db", namelist)

            manifest_data = json.loads(zf.read("manifest.json").decode("utf-8"))
            self.assertEqual(manifest_data["app"], "Bobine")
            self.assertEqual(manifest_data["version"], get_app_version())

            db_data = zf.read("database.db")
            self.assertTrue(db_data.startswith(b"SQLite format 3\x00"))

    async def test_restore_backup_invalid_file(self):
        """Vérifie le rejet de fichiers corrompus ou invalides."""
        # Non-zip file
        upload = UploadFile(filename="corrupt.zip", file=io.BytesIO(b"not a zip file"))
        with self.assertRaises(HTTPException) as ctx:
            await restore_backup(file=upload, db=MagicMock())
        self.assertEqual(ctx.exception.status_code, 400)

        # Zip without database.db
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("manifest.json", "{}")
        buf.seek(0)
        upload = UploadFile(filename="missing_db.zip", file=buf)
        with self.assertRaises(HTTPException) as ctx:
            await restore_backup(file=upload, db=MagicMock())
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("database.db manquant", ctx.exception.detail)

        # Zip with fake database.db (not SQLite)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("database.db", "not a sqlite database")
        buf.seek(0)
        upload = UploadFile(filename="fake_db.zip", file=buf)
        with self.assertRaises(HTTPException) as ctx:
            await restore_backup(file=upload, db=MagicMock())
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("pas une base SQLite valide", ctx.exception.detail)

    async def test_restore_backup_success(self):
        """Vérifie la restauration réussie d'une sauvegarde valide."""
        # 1. Export initial backup
        export_resp = export_backup()
        backup_bytes = export_resp.body

        # 2. Modify database (add a video with title 'To be overwritten')
        db = SessionLocal()
        try:
            db.add(Video(
                title="Should Disappear",
                file_path=str(Path(settings.media_dir) / "disappear.mp4"),
                duration_seconds=60.0,
                source=ImportSource.upload,
            ))
            db.commit()
            self.assertEqual(db.query(Video).count(), 2)
        finally:
            db.close()

        # 3. Restore initial backup
        upload = UploadFile(filename="valid_backup.zip", file=io.BytesIO(backup_bytes))
        mock_bg = MagicMock()
        with patch("app.routers.settings._run_restore_restart"):
            result = await restore_backup(file=upload, background_tasks=mock_bg, db=MagicMock())
            self.assertEqual(result["status"], "ok")

        # 4. Verify database returned to state of backup (1 video, Course Test 1)
        db = SessionLocal()
        try:
            videos = db.query(Video).all()
            self.assertEqual(len(videos), 1)
            self.assertEqual(videos[0].title, "Course Test 1")
        finally:
            db.close()

        # 5. Verify .bak file was created
        db_path = Path(settings.database_url.replace("sqlite:///", ""))
        self.assertTrue(db_path.with_suffix(".db.bak").exists())

    # -----------------------------------------------------------------------
    # Part 3: Clean factory data reset
    # -----------------------------------------------------------------------

    async def test_reset_data_confirmation_required(self):
        """Vérifie qu'une confirmation exacte est exigée."""
        with self.assertRaises(HTTPException) as ctx:
            await reset_data_system(ResetDataRequest(confirm="OUI"), MagicMock())
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("REINITIALISER", ctx.exception.detail)

    async def test_reset_data_success(self):
        """Vérifie la purge des médias et la réinitialisation de la DB sans toucher aux dossiers parents."""
        media_file = Path(settings.media_dir) / "course1.mp4"
        self.assertTrue(media_file.exists())

        mock_bg = MagicMock()
        with patch("app.routers.settings._run_reset_data_restart"):
            res = await reset_data_system(ResetDataRequest(confirm="reinitialiser"), mock_bg)
            self.assertIn("Remise à zéro des données effectuée", res["message"])

        # Media file inside media_dir must be deleted
        self.assertFalse(media_file.exists())
        # Media directory itself must still exist
        self.assertTrue(Path(settings.media_dir).exists())

        # Database must be clean and usable
        db = SessionLocal()
        try:
            self.assertEqual(db.query(Video).count(), 0)
        finally:
            db.close()

    def test_system_usage_normal_and_android_fallback(self):
        """Vérifie que get_system_usage fonctionne normalement et ne lève jamais
        d'erreur 500 même si psutil.cpu_percent échoue avec PermissionError (/proc/stat)."""
        # Cas 1 : appel standard
        usage = get_system_usage()
        self.assertIn("cpu_percent", usage)
        self.assertIn("memory_total_bytes", usage)
        self.assertIn("memory_used_bytes", usage)
        self.assertIn("memory_percent", usage)
        self.assertIsInstance(usage["cpu_percent"], float)
        self.assertIsInstance(usage["memory_total_bytes"], int)
        self.assertGreater(usage["memory_total_bytes"], 0)

        # Cas 2 : simulation échec psutil sous Android (SELinux /proc/stat)
        with patch("psutil.cpu_percent", side_effect=PermissionError(13, "Permission denied: '/proc/stat'")), \
             patch("psutil.virtual_memory", side_effect=PermissionError(13, "Permission denied")):
            fallback_usage = get_system_usage()
            self.assertIn("cpu_percent", fallback_usage)
            self.assertIn("memory_total_bytes", fallback_usage)
            self.assertIn("memory_used_bytes", fallback_usage)
            self.assertIn("memory_percent", fallback_usage)
            self.assertIsInstance(fallback_usage["cpu_percent"], float)
            self.assertIsInstance(fallback_usage["memory_total_bytes"], int)



if __name__ == "__main__":
    unittest.main()
