"""Planning à quatre voies : les deux sorties radio ont chacune leur voie, l'ancienne voie
« radio » reste acceptée et migre vers la sortie réseau, un lancement visant la radio câblée
ne bascule jamais l'écran câblé."""

import asyncio
import os

# Base de test isolée AVANT tout import de l'application (comme les autres tests).
os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal, _migrate_schedule_radio_channel_to_network  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
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
from app.radio_manager import get_radio_manager  # noqa: E402
from app.scheduler_manager import _launch_target, fire_schedule_end  # noqa: E402


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
    for channel in ("radio_cable", "radio_network"):
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
    _migrate_schedule_radio_channel_to_network()
    _migrate_schedule_radio_channel_to_network()  # idempotente
    db = SessionLocal()
    try:
        channels = sorted(s.channel for s in db.query(Schedule).all())
    finally:
        db.close()
    assert channels == ["cable", "network", "radio_cable", "radio_network"]


def test_creation_sur_chaque_voie_radio_et_alias_historique(client):
    pid = _playlist()
    stored = {}
    for requested in ("radio_cable", "radio_network", "radio"):
        response = client.post("/api/schedule", json=_payload(pid, requested))
        assert response.status_code == 200, response.text
        stored[requested] = response.json()["channel"]
    assert stored == {"radio_cable": "radio_cable", "radio_network": "radio_network", "radio": "radio_network"}


def test_une_cible_radio_ne_vit_jamais_sur_une_voie_video_et_inversement(client):
    pid = _playlist()
    assert client.post("/api/schedule", json=_payload(pid, "cable")).json()["channel"] == "radio_network"
    assert client.post("/api/schedule", json=_payload(pid, "zzz")).json()["channel"] == "radio_network"


def test_filtres_de_liste_par_voie_avec_alias(client):
    pid = _playlist()
    client.post("/api/schedule", json=_payload(pid, "radio_cable"))
    client.post("/api/schedule", json=_payload(pid, "radio_network"))
    by_channel = lambda ch: [s["channel"] for s in client.get("/api/schedule", params={"channel": ch}).json()]  # noqa: E731
    assert by_channel("radio_cable") == ["radio_cable"]
    assert by_channel("radio_network") == ["radio_network"]
    assert by_channel("radio") == ["radio_network"]  # ancien lien /schedule?channel=radio
    assert len(client.get("/api/schedule").json()) == 2


def test_lancement_radio_reseau_demarre_et_radio_cable_hors_radio_charge_en_pause(client):
    pid = _playlist()
    db = SessionLocal()
    try:
        asyncio.run(_launch_target(db, ScheduleTargetType.radio_playlist, pid, "radio_network"))
        asyncio.run(_launch_target(db, ScheduleTargetType.radio_playlist, pid, "radio_cable"))
    finally:
        db.close()
    network, cable = get_radio_manager("radio_network"), get_radio_manager("radio_cable")
    assert network.state["state"] == "playing"
    # La sortie câblée n'est pas sur Radio : chargée en pause, sans basculer la sortie.
    assert cable.state["state"] == "paused" and cable.state["playing"] is False
    assert cable.state["playlist_id"] == pid
    assert client.get("/api/settings/display-output").json()["cable"] != "radio"


def test_lancement_radio_cable_joue_quand_la_sortie_cable_est_sur_radio(client):
    pid = _playlist()
    client.put("/api/settings/display-output", json={"channel": "cable", "output": "radio"})
    db = SessionLocal()
    try:
        asyncio.run(_launch_target(db, ScheduleTargetType.radio_playlist, pid, "radio_cable"))
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
                            channel="radio_network")
        db.add(schedule)
        db.commit()
        schedule_id = schedule.id
    finally:
        db.close()
    asyncio.run(fire_schedule_end(schedule_id))
    assert get_radio_manager("radio_network").state["state"] == "playing"
    assert get_radio_manager("radio_cable").state["state"] == "idle"
