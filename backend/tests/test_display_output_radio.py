"""Sortie câblée commutable en Radio : validation par canal de diffusion, coupure de la
vidéo, reprise ou démarrage de l'ambiance du moteur radio câblé, pause au retour,
verrou des lancements vidéo, ambiance par défaut et rappels par sortie."""

import asyncio
import json
import os

# Base de test isolée AVANT tout import de l'application (comme les autres tests).
os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"
os.environ["BOBINE_MEDIA_DIR"] = "data/test_videos"
os.environ["BOBINE_WATCH_DIR"] = "data/test_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_thumbnails"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    ImportSource,
    RadioAnnouncement,
    RadioAnnouncementRule,
    RadioAnnouncementRuleType,
    RadioPlaylist,
    RadioPlaylistItem,
    RadioTrack,
    Setting,
)
from app.radio_manager import get_radio_manager, rule_targets_output  # noqa: E402
from app.routers.playback import _due_wait_end_announcement  # noqa: E402
from app.scheduler_manager import (  # noqa: E402
    _revert_radio_to_default,
    resolve_radio_default_playlist,
    start_radio_ambiance,
)

SETTING_KEYS = (
    "display_output_cable", "display_output_network",
    "radio_default_playlist_id_radio_cable", "radio_default_playlist_id_radio_network",
)


def _reset_engines():
    for channel in ("radio_cable", "radio_network"):
        asyncio.run(get_radio_manager(channel).stop())


def _clean_db():
    db = SessionLocal()
    try:
        db.query(Setting).filter(Setting.key.in_(SETTING_KEYS)).delete(synchronize_session=False)
        db.query(RadioAnnouncementRule).delete()
        db.query(RadioAnnouncement).delete()
        db.query(RadioPlaylistItem).delete()
        db.query(RadioPlaylist).delete()
        db.query(RadioTrack).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        _clean_db()
        _reset_engines()
        yield c
        _clean_db()
        _reset_engines()


def _seed_library(playlists=("Ambiance",), default=None):
    """Deux morceaux et des playlists nommées ; `default` = nom de la playlist is_default."""
    db = SessionLocal()
    try:
        tracks = [
            RadioTrack(file_path=f"/tmp/test-radio-{i}.mp3", title=f"Morceau {i}", duration_seconds=120.0,
                       source=ImportSource.upload)
            for i in (1, 2)
        ]
        db.add_all(tracks)
        db.commit()
        ids = {}
        for name in playlists:
            playlist = RadioPlaylist(name=name, is_default=(name == default))
            db.add(playlist)
            db.commit()
            for position, track in enumerate(tracks):
                db.add(RadioPlaylistItem(playlist_id=playlist.id, radio_track_id=track.id, position=position))
            db.commit()
            ids[name] = playlist.id
        return ids
    finally:
        db.close()


def _put_output(client, channel, output):
    return client.put("/api/settings/display-output", json={"channel": channel, "output": output})


def test_le_cable_accepte_radio_et_le_reseau_le_refuse(client):
    assert _put_output(client, "cable", "radio").status_code == 200
    assert client.get("/api/settings/display-output").json()["cable"] == "radio"
    refused = _put_output(client, "network", "radio")
    assert refused.status_code == 400
    assert client.get("/api/settings/display-output").json()["network"] != "radio"
    assert _put_output(client, "cable", "n'importe quoi").status_code == 400


def test_la_valeur_radio_stockee_l_emporte_sur_la_regle_dual_screen(client):
    client.put("/api/settings", json={"display_mode_setting": "dual_screen"})
    try:
        _put_output(client, "cable", "radio")
        assert client.get("/api/settings/display-output").json()["cable"] == "radio"
    finally:
        client.put("/api/settings", json={"display_mode_setting": "auto"})


def test_la_bascule_vers_radio_demarre_l_ambiance_si_le_moteur_est_a_l_arret(client):
    _seed_library(("Ambiance", "Salle"), default="Ambiance")
    cable = get_radio_manager("radio_cable")
    assert cable.state["state"] == "idle"
    _put_output(client, "cable", "radio")
    assert cable.state["state"] == "playing"
    assert cable.state["playlist_name"] == "Ambiance"
    # La sortie réseau n'est pas touchée.
    assert get_radio_manager("radio_network").state["state"] == "idle"


def test_la_bascule_vers_radio_reprend_une_lecture_en_pause_sans_la_relancer(client):
    ids = _seed_library(("Ambiance", "Salle"), default="Ambiance")
    db = SessionLocal()
    try:
        asyncio.run(start_radio_ambiance(db, "radio_cable"))
    finally:
        db.close()
    cable = get_radio_manager("radio_cable")
    asyncio.run(cable.jump_to(1))
    asyncio.run(cable.pause())
    assert cable.state["state"] == "paused"
    _put_output(client, "cable", "radio")
    assert cable.state["state"] == "playing"
    assert cable.state["index"] == 1  # reprise, pas de rechargement de l'ambiance
    assert ids["Ambiance"] == cable.state["playlist_id"]


def test_la_bascule_vers_radio_ne_touche_pas_une_lecture_en_cours(client):
    _seed_library(("Ambiance",), default="Ambiance")
    cable = get_radio_manager("radio_cable")
    db = SessionLocal()
    try:
        asyncio.run(start_radio_ambiance(db, "radio_cable"))
    finally:
        db.close()
    asyncio.run(cable.next_track())
    index = cable.state["index"]
    _put_output(client, "cable", "radio")
    assert cable.state["state"] == "playing"
    assert cable.state["index"] == index


def test_le_retour_vers_kiosk_ou_cinema_met_la_radio_cable_en_pause(client):
    _seed_library(("Ambiance",), default="Ambiance")
    cable = get_radio_manager("radio_cable")
    _put_output(client, "cable", "radio")
    assert cable.state["state"] == "playing"
    _put_output(client, "cable", "kiosk")
    assert cable.state["state"] == "paused"
    assert cable.state["order"], "la file est conservée pour une reprise instantanée"
    _put_output(client, "cable", "radio")
    assert cable.state["state"] == "playing"
    _put_output(client, "cable", "cinema")
    assert cable.state["state"] == "paused"


def test_un_changement_sans_rapport_avec_la_radio_ne_met_pas_la_radio_en_pause(client):
    _seed_library(("Ambiance",), default="Ambiance")
    network = get_radio_manager("radio_network")
    db = SessionLocal()
    try:
        asyncio.run(start_radio_ambiance(db, "radio_network"))
    finally:
        db.close()
    _put_output(client, "cable", "kiosk")
    _put_output(client, "cable", "cinema")
    _put_output(client, "network", "cinema")
    assert network.state["state"] == "playing"


def test_la_bascule_vers_radio_coupe_la_video_du_cable(client):
    from app.playback_manager import get_playback_manager

    manager = get_playback_manager("cable")
    asyncio.run(manager.load(1, "Cours", 600.0, None, None))
    assert manager.snapshot()["current_video"]
    _put_output(client, "cable", "radio")
    assert not get_playback_manager("cable").snapshot()["current_video"]


def test_un_lancement_video_est_verrouille_quand_le_cable_est_en_radio(client):
    _put_output(client, "cable", "radio")
    with client.websocket_connect("/ws/playback") as ws:
        ws.send_json({"command": "load", "params": {"channel": "cable", "video_id": 1}})
        message = ws.receive_json()
        while message.get("event") != "command_rejected":
            message = ws.receive_json()
        assert message["reason"] == "radio_locked"
        assert message["channel"] == "cable"


# --- Ambiance par défaut -------------------------------------------------------
def test_ambiance_par_defaut_reglage_propre_puis_is_default_puis_bibliotheque(client):
    ids = _seed_library(("Ambiance", "Salle"), default="Ambiance")
    db = SessionLocal()
    try:
        # 1. Aucun choix propre : la playlist is_default sert les deux sorties.
        assert resolve_radio_default_playlist(db, "radio_cable").id == ids["Ambiance"]
        assert resolve_radio_default_playlist(db, "radio_network").id == ids["Ambiance"]
        # 2. Choix propre à la sortie câblée.
        response = client.put("/api/radio/default-playlist", json={"channel": "radio_cable", "playlist_id": ids["Salle"]})
        assert response.status_code == 200
        assert resolve_radio_default_playlist(db, "radio_cable").id == ids["Salle"]
        assert resolve_radio_default_playlist(db, "radio_network").id == ids["Ambiance"]
        data = client.get("/api/radio/default-playlist").json()
        assert data["radio_cable"] == {"override_playlist_id": ids["Salle"], "effective_playlist_id": ids["Salle"]}
        assert data["radio_network"]["override_playlist_id"] is None
        # 3. Effacer le choix : retour à is_default.
        client.put("/api/radio/default-playlist", json={"channel": "radio_cable", "playlist_id": None})
        assert resolve_radio_default_playlist(db, "radio_cable").id == ids["Ambiance"]
    finally:
        db.close()


def test_ambiance_repli_sur_toute_la_bibliotheque_sans_playlist_par_defaut(client):
    _seed_library(("Salle",))  # aucune is_default
    db = SessionLocal()
    try:
        assert resolve_radio_default_playlist(db, "radio_cable") is None
        name = asyncio.run(start_radio_ambiance(db, "radio_cable"))
    finally:
        db.close()
    assert name == "Toute la bibliothèque"
    cable = get_radio_manager("radio_cable")
    assert cable.state["playlist_id"] is None and cable.state["shuffle"] is True


def test_default_playlist_valide_les_entrees(client):
    assert client.put("/api/radio/default-playlist", json={"channel": "radio", "playlist_id": None}).status_code == 400
    assert client.put("/api/radio/default-playlist", json={"channel": "radio_cable", "playlist_id": 999999}).status_code == 404


def test_fin_de_fenetre_recharge_en_pause_une_sortie_cable_non_basculee(client):
    _seed_library(("Ambiance",), default="Ambiance")
    db = SessionLocal()
    try:
        asyncio.run(_revert_radio_to_default(db, "radio_cable"))
        assert get_radio_manager("radio_cable").state["state"] == "paused"
        asyncio.run(_revert_radio_to_default(db, "radio_network"))
        assert get_radio_manager("radio_network").state["state"] == "playing"
    finally:
        db.close()


# --- Rappels par sortie --------------------------------------------------------
def test_cible_de_rappel_applique_a_la_bonne_sortie():
    assert rule_targets_output("radio_cable", "radio_cable")
    assert not rule_targets_output("radio_cable", "radio_network")
    assert rule_targets_output("both", "radio_cable") and rule_targets_output("both", "radio_network")
    # Une règle d'avant les deux sorties (alias ou valeur absente) vise le réseau.
    assert rule_targets_output("radio", "radio_network") and not rule_targets_output("radio", "radio_cable")
    assert rule_targets_output(None, "radio_network") and not rule_targets_output(None, "radio_cable")


def test_les_regles_de_rappel_ont_une_cible_validee_et_ancienne_valeur_reseau(client):
    base = {"rule_type": "every_n_tracks", "n_tracks": 2}
    created = client.post("/api/radio/announcement-rules", json=base)
    assert created.status_code == 201
    assert created.json()["target"] == "radio_network"  # défaut = comportement d'avant
    cable = client.post("/api/radio/announcement-rules", json={**base, "target": "radio_cable"})
    assert cable.json()["target"] == "radio_cable"
    both = client.put(f"/api/radio/announcement-rules/{cable.json()['id']}", json={**base, "target": "both"})
    assert both.json()["target"] == "both"
    assert client.post("/api/radio/announcement-rules", json={**base, "target": "zzz"}).status_code == 400
    # Mise à jour SANS cible (client en cache) : la cible existante est conservée.
    kept = client.put(f"/api/radio/announcement-rules/{cable.json()['id']}", json={**base, "enabled": False})
    assert kept.status_code == 200 and kept.json()["target"] == "both"
    listed = client.get("/api/radio/announcement-rules").json()
    assert {r["target"] for r in listed} == {"radio_network", "both"}


def test_la_regle_toutes_les_n_musiques_est_filtree_par_sortie(client):
    db = SessionLocal()
    try:
        db.add(RadioAnnouncement(file_path="/tmp/test-rappel.mp3", description="Merci", duration_seconds=3.0))
        db.add(RadioAnnouncementRule(rule_type=RadioAnnouncementRuleType.every_n_tracks, n_tracks=1, target="radio_cable"))
        db.commit()
        cable, network = get_radio_manager("radio_cable"), get_radio_manager("radio_network")
        cable.state["tracks_since_announcement"] = 5
        network.state["tracks_since_announcement"] = 5
        assert _due_wait_end_announcement(db, cable) is not None
        assert _due_wait_end_announcement(db, network) is None
    finally:
        db.close()


def test_play_now_cible_une_sortie_ou_les_deux(client):
    db = SessionLocal()
    try:
        db.add(RadioAnnouncement(file_path="/tmp/test-rappel2.mp3", description="Bonjour", duration_seconds=3.0))
        db.commit()
    finally:
        db.close()
    cable, network = get_radio_manager("radio_cable"), get_radio_manager("radio_network")
    assert client.post("/api/radio/announcements/play-now", json={"target": "radio_cable"}).status_code == 200
    assert cable.state["current_announcement"] and not network.state["current_announcement"]
    _reset_engines()
    assert client.post("/api/radio/announcements/play-now", json={}).status_code == 200
    assert network.state["current_announcement"] and not cable.state["current_announcement"]
    _reset_engines()
    assert client.post("/api/radio/announcements/play-now", json={"target": "both"}).status_code == 200
    assert cable.state["current_announcement"] and network.state["current_announcement"]
