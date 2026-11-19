import io
import json
import os
import shutil
import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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
from app.models import Video, ImportSource
from app.api.routes.settings.backup import ResetDataRequest, export_backup, restore_backup, reset_data_system
from app.api.routes.settings.maintenance import get_system_usage
from app.api.routes.updates import check_updates
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

        media_path = Path(settings.media_dir)
        media_path.mkdir(parents=True, exist_ok=True)
        (media_path / "course1.mp4").write_bytes(b"dummy video data")


    async def test_check_updates_offline(self):
        with patch("urllib.request.urlopen", side_effect=OSError("Offline")):
            res = await check_updates(db=SessionLocal())
            self.assertFalse(res["online"])
            self.assertIn("deployment_profile", res)
            self.assertIn("can_auto_apply", res)
            self.assertIsNone(res["download_url"])

    _RELEASE = {
        "tag_name": "V9.9.9",
        "name": "Bobine V9.9.9",
        "body": "Release notes test",
        "published_at": "2026-09-06T12:00:00Z",
        "html_url": "https://github.com/FantasmaGlad/Bobine/releases/tag/V9.9.9",
        "assets": [
            {"name": name, "size": size,
             "browser_download_url": f"https://github.com/FantasmaGlad/Bobine/releases/download/V9.9.9/{name}"}
            for name, size in (
                ("Bobine-Setup-9.9.9.exe", 65000000),
                ("bobine_9.9.9_amd64.deb", 48000000),
                ("Bobine-9.9.9.dmg", 55000000),
            )
        ],
    }
    _PROFILE_CASES = (
        ("windows", True, "Bobine-Setup-9.9.9.exe"),
        ("linux-desktop", True, "bobine_9.9.9_amd64.deb"),
        ("macos", False, "Bobine-9.9.9.dmg"),
        ("linux-headless", True, None),
    )

    async def _check_updates_as(self, profile, auto_apply):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(self._RELEASE).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        with patch("urllib.request.urlopen", return_value=mock_resp), \
             patch("app.api.routes.updates.get_deployment_profile", return_value=profile), \
             patch("app.api.routes.updates.get_profile_handler") as mock_handler:
            mock_handler.return_value.can_auto_apply.return_value = auto_apply
            mock_handler.return_value.is_store_managed.return_value = False
            return await check_updates(db=SessionLocal())

    async def test_check_updates_profile_asset_matching(self):
        for profile, auto_apply, asset in self._PROFILE_CASES:
            res = await self._check_updates_as(profile, auto_apply)
            self.assertTrue(res["online"], profile)
            self.assertTrue(res["has_update"], profile)
            self.assertEqual(bool(res["can_auto_apply"]), auto_apply, profile)
            if asset is not None:
                self.assertEqual(res["asset_name"], asset)
                self.assertTrue(res["download_url"].endswith(asset.rsplit(".", 1)[1]))

    def test_export_backup(self):
        response = export_backup()
        self.assertEqual(response.media_type, "application/zip")
        self.assertIn("attachment; filename=", response.headers.get("Content-Disposition", ""))

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
        upload = UploadFile(filename="corrupt.zip", file=io.BytesIO(b"not a zip file"))
        with self.assertRaises(HTTPException) as ctx:
            await restore_backup(file=upload, db=MagicMock())
        self.assertEqual(ctx.exception.status_code, 422)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("manifest.json", "{}")
        buf.seek(0)
        upload = UploadFile(filename="missing_db.zip", file=buf)
        with self.assertRaises(HTTPException) as ctx:
            await restore_backup(file=upload, db=MagicMock())
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("database.db manquant", ctx.exception.detail)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("database.db", "not a sqlite database")
        buf.seek(0)
        upload = UploadFile(filename="fake_db.zip", file=buf)
        with self.assertRaises(HTTPException) as ctx:
            await restore_backup(file=upload, db=MagicMock())
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("pas une base SQLite valide", ctx.exception.detail)

    async def test_restore_backup_success(self):
        export_resp = export_backup()
        backup_bytes = export_resp.body

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

        upload = UploadFile(filename="valid_backup.zip", file=io.BytesIO(backup_bytes))
        mock_bg = MagicMock()
        with patch("app.api.routes.settings.backup._run_restore_restart"):
            result = await restore_backup(file=upload, background_tasks=mock_bg, db=MagicMock())
            self.assertEqual(result["status"], "ok")

        db = SessionLocal()
        try:
            videos = db.query(Video).all()
            self.assertEqual(len(videos), 1)
            self.assertEqual(videos[0].title, "Course Test 1")
        finally:
            db.close()

        db_path = Path(settings.database_url.replace("sqlite:///", ""))
        self.assertTrue(db_path.with_suffix(".db.bak").exists())


    async def test_reset_data_confirmation_required(self):
        with self.assertRaises(HTTPException) as ctx:
            await reset_data_system(ResetDataRequest(confirm="OUI"), MagicMock())
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("REINITIALISER", ctx.exception.detail)

    async def test_reset_data_success(self):
        media_file = Path(settings.media_dir) / "course1.mp4"
        self.assertTrue(media_file.exists())

        mock_bg = MagicMock()
        with patch("app.api.routes.settings.backup._run_reset_data_restart"):
            res = await reset_data_system(ResetDataRequest(confirm="reinitialiser"), mock_bg)
            self.assertIn("Remise à zéro des données effectuée", res["message"])

        self.assertFalse(media_file.exists())
        self.assertTrue(Path(settings.media_dir).exists())

        db = SessionLocal()
        try:
            self.assertEqual(db.query(Video).count(), 0)
        finally:
            db.close()

    def test_system_usage_normal_and_android_fallback(self):
        usage = get_system_usage()
        self.assertIn("cpu_percent", usage)
        self.assertIn("memory_total_bytes", usage)
        self.assertIn("memory_used_bytes", usage)
        self.assertIn("memory_percent", usage)
        self.assertIsInstance(usage["cpu_percent"], float)
        self.assertIsInstance(usage["memory_total_bytes"], int)
        self.assertGreater(usage["memory_total_bytes"], 0)

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
