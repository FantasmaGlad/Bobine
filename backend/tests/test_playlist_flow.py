import os
import sys
import unittest
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_playlist_database.db"

from app.config import settings
from app.database import init_db, SessionLocal
from app.models import Video, Playlist, PlaylistItem, ImportSource
from app.playback.manager import PlaybackManager
from app.api.routes.playlists import create_playlist, list_playlists, get_playlist, duplicate_playlist, delete_playlist, update_playlist
from app.api.routes.playlists import PlaylistInput, PlaylistItemInput


class TestPlaylistFlow(unittest.IsolatedAsyncioTestCase):
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
            except PermissionError:
                pass


    def setUp(self):
        self.db = SessionLocal()
        self.video1 = Video(
            file_path="data/test_videos/video1.mp4",
            title="RPM 98",
            program="RPM",
            release="98",
            duration_seconds=2700.0,
            source=ImportSource.upload
        )
        self.video2 = Video(
            file_path="data/test_videos/video2.mp4",
            title="Sprint 35",
            program="Sprint",
            release="35",
            duration_seconds=1800.0,
            source=ImportSource.upload
        )
        self.db.add_all([self.video1, self.video2])
        self.db.commit()

    def tearDown(self):
        self.db.query(PlaylistItem).delete()
        self.db.query(Playlist).delete()
        self.db.query(Video).delete()
        self.db.commit()
        self.db.close()

    async def test_playlist_crud_and_duplicate(self):
        item1 = PlaylistItemInput(video_id=self.video1.id, position=0)
        item2 = PlaylistItemInput(video_id=self.video2.id, position=1)
        payload = PlaylistInput(name="Ma super playlist", items=[item1, item2])
        
        pl = create_playlist(payload, self.db)
        self.assertIsNotNone(pl["id"])
        self.assertEqual(pl["name"], "Ma super playlist")
        self.assertEqual(len(pl["items"]), 2)
        self.assertEqual(pl["items"][0].video.id, self.video1.id)
        self.assertEqual(pl["items"][1].video.id, self.video2.id)

        self.assertEqual(pl["total_duration_seconds"], 4500.0)

        pl_list = list_playlists(self.db)
        self.assertEqual(len(pl_list), 1)
        self.assertEqual(pl_list[0]["item_count"], 2)
        self.assertEqual(pl_list[0]["total_duration_seconds"], 4500.0)

        item2_new = PlaylistItemInput(video_id=self.video2.id, position=0)
        item1_new = PlaylistItemInput(video_id=self.video1.id, position=1)
        update_payload = PlaylistInput(name="Playlist Renommée", items=[item2_new, item1_new])
        
        updated_pl = update_playlist(pl["id"], update_payload, self.db)
        self.assertEqual(updated_pl["name"], "Playlist Renommée")
        self.assertEqual(updated_pl["items"][0].video.id, self.video2.id)
        self.assertEqual(updated_pl["items"][1].video.id, self.video1.id)

        duplicated_pl = duplicate_playlist(pl["id"], self.db)
        self.assertNotEqual(duplicated_pl["id"], pl["id"])
        self.assertEqual(duplicated_pl["name"], "Playlist Renommée (copie)")
        self.assertEqual(len(duplicated_pl["items"]), 2)
        self.assertEqual(duplicated_pl["items"][0].video.id, self.video2.id)

        delete_playlist(pl["id"], self.db)
        self.assertIsNone(self.db.query(Playlist).filter_by(id=pl["id"]).first())
        self.assertEqual(self.db.query(PlaylistItem).filter_by(playlist_id=pl["id"]).count(), 0)
        self.assertEqual(self.db.query(PlaylistItem).filter_by(playlist_id=duplicated_pl["id"]).count(), 2)

    async def test_playback_manager_playlist_flow(self):
        item1 = PlaylistItemInput(video_id=self.video1.id, position=0)
        item2 = PlaylistItemInput(video_id=self.video2.id, position=1)
        payload = PlaylistInput(name="Flow Playlist", items=[item1, item2])
        pl = create_playlist(payload, self.db)

        broadcast_payloads = []
        async def mock_broadcast(data):
            broadcast_payloads.append(data)

        manager = PlaybackManager(mock_broadcast)
        
        items_data = [
            {"id": self.video1.id, "title": self.video1.title, "duration_seconds": self.video1.duration_seconds, "program": self.video1.program},
            {"id": self.video2.id, "title": self.video2.title, "duration_seconds": self.video2.duration_seconds, "program": self.video2.program},
        ]
        await manager.load_playlist(pl["id"], pl["name"], items_data)
        
        self.assertEqual(manager.state["state"], "playing")
        self.assertEqual(manager.state["current_video"]["id"], self.video1.id)
        self.assertEqual(manager.state["playlist_name"], "Flow Playlist")
        self.assertEqual(manager.state["playlist_index"], 0)

        manager.state["state"] = "playing"
        manager.state["position_seconds"] = 2700.0
        
        await manager.video_ended()
        
        self.assertEqual(manager.state["state"], "playlist_waiting")
        self.assertIsNotNone(manager.state["playlist_waiting_remaining"])
        
        await manager.skip_waiting()
        
        self.assertEqual(manager.state["state"], "playing")
        self.assertEqual(manager.state["current_video"]["id"], self.video2.id)
        self.assertEqual(manager.state["playlist_index"], 1)

        manager.state["position_seconds"] = 1800.0
        await manager.video_ended()

        self.assertEqual(manager.state["state"], "waiting")
        self.assertIsNone(manager.state["current_video"])
        self.assertIsNone(manager.state["playlist_name"])

    async def test_playlist_waiting_period_auto_advances(self):
        import time as _time

        item1 = PlaylistItemInput(video_id=self.video1.id, position=0)
        item2 = PlaylistItemInput(video_id=self.video2.id, position=1)
        payload = PlaylistInput(name="Auto-advance Playlist", items=[item1, item2])
        pl = create_playlist(payload, self.db)

        ticks = []
        events = []

        async def mock_broadcast(data):
            events.append((data.get("cause"), data.get("data")))
            if data.get("cause") == "playlist_waiting_tick":
                ticks.append(data["data"]["playlist_waiting_remaining"])

        manager = PlaybackManager(mock_broadcast)
        items_data = [
            {"id": self.video1.id, "title": self.video1.title, "duration_seconds": self.video1.duration_seconds, "program": self.video1.program},
            {"id": self.video2.id, "title": self.video2.title, "duration_seconds": self.video2.duration_seconds, "program": self.video2.program},
        ]
        await manager.load_playlist(pl["id"], pl["name"], items_data)
        manager.state["state"] = "playing"

        original_wait = settings.wait_time_between_courses
        settings.wait_time_between_courses = 2
        try:
            start = _time.monotonic()
            await manager.video_ended()
            self.assertEqual(manager.state["state"], "playlist_waiting")
            await asyncio.wait_for(manager._waiting_task, timeout=8)
            elapsed = _time.monotonic() - start
        finally:
            settings.wait_time_between_courses = original_wait

        self.assertEqual(manager.state["state"], "playing")
        self.assertEqual(manager.state["current_video"]["id"], self.video2.id)
        self.assertEqual(manager.state["playlist_index"], 1)
        self.assertLess(elapsed, 3.6, f"Décompte trop lent ({elapsed:.1f}s pour 2s d'attente)")
        self.assertIn(0.0, ticks)
        load_events = [d for (cause, d) in events if cause == "load"]
        self.assertTrue(load_events, "aucun évènement 'load' diffusé pour le cours suivant")
        self.assertEqual(load_events[-1]["current_video"]["id"], self.video2.id)
        self.assertEqual(load_events[-1]["state"], "playing")


if __name__ == "__main__":
    unittest.main()
