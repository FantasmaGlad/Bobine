"""Reprise d'une programmation après un redémarrage du serveur : calcul de la position, puis relance réelle."""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_schedule_database.db")

from app.database import SessionLocal, init_db  # noqa: E402
from app.models import (  # noqa: E402
    ImportSource,
    Playlist,
    PlaylistItem,
    Schedule,
    ScheduledLaunch,
    ScheduleTargetType,
    ScheduleType,
    Video,
)
from app.playback_manager import get_playback_manager, init_playback_managers  # noqa: E402
from app.scheduling.launch import launch_target  # noqa: E402
from app.scheduling.resume import resume_running_schedules  # noqa: E402
from app.scheduling import launch_store as scheduled_launch_store  # noqa: E402
from app.scheduling.offsets import MIN_REMAINING_SECONDS, playback_offset, playlist_resume_point  # noqa: E402

T0 = datetime(2026, 11, 11, 18, 0, tzinfo=timezone.utc)


class PlaybackOffsetTests(unittest.TestCase):
    def test_un_cours_lance_a_18h_reprend_a_la_quatorzieme_minute_a_18h14(self):
        self.assertEqual(playback_offset(T0, T0 + timedelta(minutes=14), 2700.0), 840.0)

    def test_rien_a_reprendre_quand_le_cours_est_fini_ou_presque(self):
        self.assertIsNone(playback_offset(T0, T0 + timedelta(seconds=2700), 2700.0))
        self.assertIsNone(playback_offset(T0, T0 + timedelta(seconds=2700 - MIN_REMAINING_SECONDS + 1), 2700.0))
        self.assertIsNotNone(playback_offset(T0, T0 + timedelta(seconds=2700 - MIN_REMAINING_SECONDS), 2700.0))

    def test_duree_inconnue_ou_horloge_en_retard_ne_reprennent_rien(self):
        self.assertIsNone(playback_offset(T0, T0 + timedelta(minutes=5), None))
        self.assertIsNone(playback_offset(T0, T0 + timedelta(minutes=5), 0))
        self.assertIsNone(playback_offset(T0, T0 - timedelta(minutes=1), 2700.0))


class PlaylistResumePointTests(unittest.TestCase):
    DURATIONS = [600.0, 600.0, 600.0]

    def test_position_dans_la_premiere_puis_la_deuxieme_video(self):
        self.assertEqual(playlist_resume_point(self.DURATIONS, 0.0, 240.0), (0, 240.0))
        self.assertEqual(playlist_resume_point(self.DURATIONS, 0.0, 840.0), (1, 240.0))

    def test_l_attente_entre_deux_cours_compte_dans_le_temps_ecoule(self):
        self.assertEqual(playlist_resume_point(self.DURATIONS, 60.0, 900.0), (1, 240.0))
        # Pendant l'attente : la vidéo suivante démarre à zéro.
        self.assertEqual(playlist_resume_point(self.DURATIONS, 60.0, 630.0), (1, 0.0))

    def test_fin_de_video_et_fin_de_playlist(self):
        self.assertEqual(playlist_resume_point(self.DURATIONS, 0.0, 595.0), (1, 0.0))
        self.assertIsNone(playlist_resume_point(self.DURATIONS, 0.0, 1795.0))
        self.assertIsNone(playlist_resume_point(self.DURATIONS, 0.0, 5000.0))

    def test_duree_inconnue_ou_temps_negatif(self):
        self.assertIsNone(playlist_resume_point([600.0, None, 600.0], 0.0, 700.0))
        self.assertEqual(playlist_resume_point([600.0, None, 600.0], 0.0, 100.0), (0, 100.0))
        self.assertIsNone(playlist_resume_point(self.DURATIONS, 0.0, -1.0))


class ResumeAfterRestartTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        from app import playback_manager as playback_manager_module

        saved_managers = dict(playback_manager_module._managers)
        self.addCleanup(lambda: playback_manager_module._managers.update(saved_managers))
        self.db = SessionLocal()
        self.db.query(ScheduledLaunch).delete()
        self.video = Video(file_path="data/test_videos/resume_a.mp4", title="RPM 98", duration_seconds=2700.0, source=ImportSource.upload)
        self.short = Video(file_path="data/test_videos/resume_b.mp4", title="Sprint 35", duration_seconds=600.0, source=ImportSource.upload)
        self.db.add_all([self.video, self.short])
        self.db.commit()
        self.playlist = Playlist(name="Enchaînement de reprise")
        self.db.add(self.playlist)
        self.db.flush()
        self.db.add_all([
            PlaylistItem(playlist_id=self.playlist.id, video_id=self.short.id, position=0),
            PlaylistItem(playlist_id=self.playlist.id, video_id=self.video.id, position=1),
        ])
        self.db.commit()
        self._restart()

    def tearDown(self):
        for model in (ScheduledLaunch, Schedule, PlaylistItem, Playlist, Video):
            self.db.query(model).delete()
        self.db.commit()
        self.db.close()

    def _restart(self):
        """Un redémarrage du serveur : moteurs de lecture neufs, la base seule survit."""
        async def broadcast(payload, channel="cable"):
            return None

        init_playback_managers(broadcast)

    def _state(self, channel="cable"):
        return get_playback_manager(channel).snapshot()

    async def test_un_cours_programme_reprend_a_sa_position_apres_un_redemarrage(self):
        await launch_target(self.db, ScheduleTargetType.video, self.video.id, "cable")
        record = scheduled_launch_store.get(self.db, "cable")
        record.started_at = datetime.now(timezone.utc) - timedelta(minutes=14)
        self.db.commit()

        self._restart()
        self.assertEqual(self._state()["state"], "waiting")
        await resume_running_schedules()

        state = self._state()
        self.assertEqual(state["state"], "playing")
        self.assertEqual(state["current_video"]["id"], self.video.id)
        self.assertAlmostEqual(state["position_seconds"], 840.0, delta=5.0)
        self.assertTrue(state["scheduled_launch"])

    async def test_un_cours_arrete_a_la_main_n_est_pas_relance(self):
        await launch_target(self.db, ScheduleTargetType.video, self.video.id, "cable")
        await get_playback_manager("cable").stop()
        self._restart()
        await resume_running_schedules()
        self.assertEqual(self._state()["state"], "waiting")

    async def test_une_lecture_manuelle_qui_remplace_le_cours_empeche_sa_reprise(self):
        await launch_target(self.db, ScheduleTargetType.video, self.video.id, "cable")
        await get_playback_manager("cable").load(self.short.id, self.short.title, self.short.duration_seconds, None)
        self._restart()
        await resume_running_schedules()
        self.assertEqual(self._state()["state"], "waiting")

    async def test_une_lecture_lancee_depuis_le_demarrage_garde_l_ecran(self):
        scheduled_launch_store.remember(
            self.db, "cable", "video", self.video.id, datetime.now(timezone.utc) - timedelta(minutes=14)
        )
        await get_playback_manager("cable").load(self.short.id, self.short.title, self.short.duration_seconds, None)
        await resume_running_schedules()
        self.assertEqual(self._state()["current_video"]["id"], self.short.id)

    async def test_un_cours_termine_pendant_la_coupure_n_est_pas_relance(self):
        scheduled_launch_store.remember(
            self.db, "cable", "video", self.video.id, datetime.now(timezone.utc) - timedelta(hours=2)
        )
        await resume_running_schedules()
        self.assertEqual(self._state()["state"], "waiting")
        self.db.expire_all()
        self.assertFalse(scheduled_launch_store.get(self.db, "cable").active)

    async def test_une_playlist_reprend_a_la_bonne_video(self):
        scheduled_launch_store.remember(
            self.db, "cable", "playlist", self.playlist.id, datetime.now(timezone.utc) - timedelta(minutes=14)
        )
        await resume_running_schedules()
        state = self._state()
        self.assertEqual(state["playlist_index"], 1)
        self.assertEqual(state["current_video"]["id"], self.video.id)
        self.assertAlmostEqual(state["position_seconds"], 240.0, delta=5.0)

    async def test_une_occurrence_dont_l_heure_est_passee_serveur_eteint_demarre_en_cours_de_route(self):
        self.db.add(Schedule(
            target_type=ScheduleTargetType.video, target_id=self.video.id, schedule_type=ScheduleType.once,
            run_at=datetime.now(timezone.utc) - timedelta(minutes=5), active=True, channel="network",
        ))
        self.db.commit()
        await resume_running_schedules()

        self.assertEqual(self._state("cable")["state"], "waiting")
        state = self._state("network")
        self.assertEqual(state["current_video"]["id"], self.video.id)
        self.assertAlmostEqual(state["position_seconds"], 300.0, delta=5.0)
        # Second redémarrage : la même occurrence reprend d'après son lancement mémorisé, sans repartir de zéro.
        self._restart()
        await resume_running_schedules()
        self.assertAlmostEqual(self._state("network")["position_seconds"], 300.0, delta=5.0)


if __name__ == "__main__":
    unittest.main()
