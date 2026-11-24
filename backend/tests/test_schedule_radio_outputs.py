import asyncio
import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.database.migrations import migrate_schedule_radio_channel_to_network
from app.main import app
from app.models import (
    ImportSource,
    RadioPlaylist,
    RadioPlaylistItem,
    RadioTrack,
    Schedule,
    ScheduleOverride,
    ScheduleTargetType,
    ScheduleType,
    Setting,
)
from app.radio.manager import get_radio_manager
from app.scheduling.launch import launch_target, fire_schedule_end


def _clean_db():
    db = SessionLocal()
    try:
        db.query(ScheduleOverride).delete()
        db.query(Schedule).delete()
        db.query(Setting).filter(Setting.key.in_(["display_output_cable", "display_output_network"])).delete(
            synchronize_session=False
        )
        db.query(RadioPlaylistItem).delete()
        db.query(RadioPlaylist).delete()
        db.query(RadioTrack).delete()
        db.commit()
    finally:
        db.close()


def _stop_engines():
    for channel in ("radio_cable", "radio_network_2"):
        asyncio.run(get_radio_manager(channel).stop())


@pytest.fixture()
def client():
    with TestClient(app) as c:
        _clean_db()
        _stop_engines()
        yield c
        _clean_db()
        _stop_engines()


def _playlist():
    db = SessionLocal()
    try:
        track = RadioTrack(file_path="/tmp/test-sched-radio.mp3", title="T", duration_seconds=100.0,
                           source=ImportSource.upload)
        db.add(track)
        db.commit()
        playlist = RadioPlaylist(name="Fenêtre")
        db.add(playlist)
        db.commit()
        db.add(RadioPlaylistItem(playlist_id=playlist.id, radio_track_id=track.id, position=0))
        db.commit()
        return playlist.id
    finally:
        db.close()


def _payload(playlist_id, channel, **extra):
    return {
        "target_type": "radio_playlist", "target_id": playlist_id, "channel": channel,
        "schedule_type": "recurring", "days_of_week": [0, 1, 2], "time_of_day": "08:00", "end_time": "10:00",
        **extra,
    }


def test_la_migration_rattache_l_ancienne_voie_radio_a_la_sortie_reseau_et_est_idempotente(client):
    db = SessionLocal()
    try:
        for channel in ("radio", "cable", "network", "radio_cable"):
            db.add(Schedule(target_type=ScheduleTargetType.radio_playlist, target_id=1,
                            schedule_type=ScheduleType.recurring, recurrence_rule="{}", channel=channel))
        db.commit()
    finally:
        db.close()
    migrate_schedule_radio_channel_to_network()
    migrate_schedule_radio_channel_to_network()
    db = SessionLocal()
    try:
        channels = sorted(s.channel for s in db.query(Schedule).all())
    finally:
        db.close()
    assert channels == ["cable", "network", "radio_cable", "radio_network"]


def test_une_fenetre_radio_vit_sur_la_ligne_de_sa_sortie_et_refuse_les_anciennes_voies(client):
    pid = _playlist()
    stored = {}
    for requested in ("cable", "network", "network_2"):
        response = client.post("/api/schedule", json=_payload(pid, requested))
        assert response.status_code == 200, response.text
        stored[requested] = response.json()["channel"]
    assert stored == {"cable": "cable", "network": "network", "network_2": "network_2"}
    for legacy in ("radio_cable", "radio_network", "radio_network_2", "radio", "zzz"):
        assert client.post("/api/schedule", json=_payload(pid, legacy)).status_code == 422, legacy


def test_filtres_de_liste_par_sortie_refusent_les_anciennes_voies(client):
    pid = _playlist()
    client.post("/api/schedule", json=_payload(pid, "cable"))
    client.post("/api/schedule", json=_payload(pid, "network_2"))
    by_channel = lambda ch: [s["channel"] for s in client.get("/api/schedule", params={"channel": ch}).json()]
    assert by_channel("cable") == ["cable"]
    assert by_channel("network_2") == ["network_2"]
    for legacy in ("radio_cable", "radio_network_2", "radio", "zzz"):
        assert client.get("/api/schedule", params={"channel": legacy}).status_code == 422, legacy
    assert len(client.get("/api/schedule").json()) == 2


def test_lancement_radio_reseau_demarre_et_radio_cable_ramene_l_ecran_cable_sur_radio(client):
    pid = _playlist()
    assert client.get("/api/outputs/cable").json()["mode"] != "radio"
    db = SessionLocal()
    try:
        asyncio.run(launch_target(db, ScheduleTargetType.radio_playlist, pid, "network_2"))
        asyncio.run(launch_target(db, ScheduleTargetType.radio_playlist, pid, "cable"))
    finally:
        db.close()
    network, cable = get_radio_manager("radio_network_2"), get_radio_manager("radio_cable")
    assert network.state["state"] == "playing"
    assert client.get("/api/outputs/cable").json()["mode"] == "radio"
    assert cable.state["state"] == "playing" and cable.state["playlist_id"] == pid
    assert client.get("/api/outputs/network").json()["mode"] != "radio"


def test_la_bascule_planifiee_coupe_la_video_du_cable(client):
    from app.playback.manager import get_playback_manager

    pid = _playlist()
    manager = get_playback_manager("cable")
    asyncio.run(manager.load(1, "Cours", 600.0, None, None))
    assert manager.snapshot()["current_video"]
    db = SessionLocal()
    try:
        asyncio.run(launch_target(db, ScheduleTargetType.radio_playlist, pid, "cable"))
    finally:
        db.close()
    assert not get_playback_manager("cable").snapshot()["current_video"]


def test_le_mode_coach_garde_la_priorite_sur_une_programmation_radio_cable(client):
    from app.playback.manager import get_playback_manager

    pid = _playlist()
    manager = get_playback_manager("cable")
    original = manager.snapshot

    def coach_snapshot():
        return {**original(), "state": "coach_mode"}

    manager.snapshot = coach_snapshot  # type: ignore[method-assign]
    try:
        db = SessionLocal()
        try:
            asyncio.run(launch_target(db, ScheduleTargetType.radio_playlist, pid, "cable"))
        finally:
            db.close()
    finally:
        manager.snapshot = original  # type: ignore[method-assign]
    assert client.get("/api/outputs/cable").json()["mode"] != "radio"
    cable = get_radio_manager("radio_cable")
    assert cable.state["state"] == "paused" and cable.state["playlist_id"] == pid


def test_lancement_radio_cable_joue_quand_la_sortie_cable_est_sur_radio(client):
    pid = _playlist()
    client.put("/api/outputs/cable/mode", json={"mode": "radio"})
    db = SessionLocal()
    try:
        asyncio.run(launch_target(db, ScheduleTargetType.radio_playlist, pid, "cable"))
    finally:
        db.close()
    assert get_radio_manager("radio_cable").state["state"] == "playing"


def test_fin_de_fenetre_revient_a_l_ambiance_de_la_sortie_visee_seulement(client):
    pid = _playlist()
    db = SessionLocal()
    try:
        db.query(RadioPlaylist).filter(RadioPlaylist.id == pid).update({"is_default": True})
        schedule = Schedule(target_type=ScheduleTargetType.radio_playlist, target_id=pid,
                            schedule_type=ScheduleType.recurring, recurrence_rule='{"days_of_week":[0],"time":"08:00","end_time":"10:00"}',
                            channel="network_2")
        db.add(schedule)
        db.commit()
        schedule_id = schedule.id
    finally:
        db.close()
    asyncio.run(fire_schedule_end(schedule_id))
    assert get_radio_manager("radio_network_2").state["state"] == "playing"
    assert get_radio_manager("radio_cable").state["state"] == "idle"
