"""Commandes de la radio : pistes, fins de piste, rappels vocaux."""

import logging

from fastapi import WebSocket
from sqlalchemy.orm import Session

from app.devices.service import PLAYER_ROUTE_STATUSES
from app.devices.service import service as devices_service
from app.models import (
    RadioAnnouncement,
    RadioAnnouncementRule,
    RadioAnnouncementRuleType,
    RadioPlaylist,
    RadioTrack,
)
from app.radio_manager import (
    get_radio_manager,
    rule_targets_output,
)
from app.scheduling.radio import radio_track_dict
from app.utils import radio_commands
from app.utils.activity_log import log_activity
from app.utils.radio_mix import sanitize_levels
from app.utils.ws_manager import manager as ws_manager

from .core import CommandRejected, _not_found, _reject_unavailable

logger = logging.getLogger(__name__)


async def _handle_radio_track_ended(manager, db, client_ts, track_id: int | None) -> None:
    """Fin de piste radio, IDEMPOTENTE : chaque page /radio l'envoie, et le serveur
    peut l'avoir déjà enchaînée. Un signal périmé (autre piste que la courante) est
    ignoré AVANT de compter la piste, sans quoi un doublon faussait aussi la règle
    « toutes les N musiques »."""
    current = manager.state.get("current_track")
    if track_id is not None and current is not None and current.get("id") != track_id:
        return
    # Règle « toutes les N musiques » : vérifiée ICI (accès
    # DB), pas dans le manager (état pur). Si due, le rappel se joue AVANT
    # l'avancement (attente-fin), qui reprendra à sa fin (`announcement_ended`).
    manager.state["tracks_since_announcement"] = manager.state.get("tracks_since_announcement", 0) + 1
    due = _due_wait_end_announcement(db, manager)
    if due:
        await manager.play_announcement(
            {"id": due.id, "description": due.description}, mode="wait_end",
            client_ts=client_ts, deferred_advance=True,
        )
    else:
        await manager.track_ended(client_ts, track_id=track_id)


async def _radio_track_end_fallback(radio_channel: str, track_id: int | None) -> None:
    """Fin de piste déclenchée par l'horloge serveur (aucun poste ne l'a signalée) :
    même chemin que la commande, avec sa propre session de base de données."""
    from app.database import SessionLocal

    with SessionLocal() as db:
        await _handle_radio_track_ended(get_radio_manager(radio_channel), db, None, track_id)


async def _handle_radio_command(
    command: str, params: dict, client_ts, db: Session,
    websocket: WebSocket | None = None, is_kiosk: bool = False,
    radio_channel: str | None = None,
) -> None:
    """Commandes d'une sortie radio : vocabulaire propre (radio_*), séparé de la chaîne câblé/
    réseau ci-dessus car le RadioPlaybackManager n'a pas la même sémantique
    d'état (playlist de morceaux plutôt que vidéo/cours). `radio_channel`
    désigne le moteur visé (sortie réseau si absent, comme l'ancien poste unique)."""
    manager = get_radio_manager(radio_channel)

    if command == "load_radio_playlist":
        playlist_id = params.get("playlist_id")
        playlist = db.query(RadioPlaylist).filter(RadioPlaylist.id == playlist_id).first()
        if not playlist:
            raise _not_found(command, manager.channel, f"Playlist radio {playlist_id}")
        sorted_items = sorted(playlist.items, key=lambda item: item.position)
        tracks = [radio_track_dict(item.track) for item in sorted_items if item.track and item.track.available]
        # repeat="playlist" comme le chargement planifié "ambiance 24/7" : une radio n'a pas vocation à
        # s'arrêter en silence en fin de liste — correctif "le mode aléatoire
        # n'est pas infini" (shuffle et repeat sont deux réglages indépendants
        # côté RadioPlaybackManager, l'un n'implique pas l'autre). Le DJ garde
        # la main pour repasser en "off" via le bouton dédié après coup.
        await manager.load_playlist(
            playlist.id, playlist.name, tracks, shuffle=params.get("shuffle"), client_ts=client_ts,
            repeat="playlist",
        )
        log_activity(db, "radio_playlist_started", playlist.name)
    elif command == "radio_shuffle_all":
        # Lecture aléatoire de TOUTE la bibliothèque, sans playlist : playlist_id=None, tous les morceaux mélangés à la volée.
        tracks = [radio_track_dict(t) for t in db.query(RadioTrack).all() if t.available]
        if not tracks:
            logger.info("Commande radio_shuffle_all : bibliothèque radio vide")
            raise CommandRejected("empty_library", manager.channel, "La bibliothèque radio ne contient aucun morceau disponible.")
        # repeat="playlist" : même correctif que load_radio_playlist ci-dessus
        # — "toute la bibliothèque en aléatoire" doit boucler indéfiniment, pas
        # s'arrêter après un seul passage.
        await manager.load_playlist(
            None, "Toute la bibliothèque", tracks, shuffle=True, client_ts=client_ts, repeat="playlist",
        )
        log_activity(db, "radio_shuffle_all_started", f"{len(tracks)} morceau(x)")
    elif command == "play":
        await manager.play(client_ts)
    elif command == "pause":
        await manager.pause(client_ts)
    elif command == "stop":
        await manager.stop(client_ts)
    elif command == "radio_next_track":
        await manager.next_track(client_ts)
    elif command == "radio_previous_track":
        await manager.previous_track(client_ts)
    elif command == "radio_jump_to_track":
        await manager.jump_to(int(params.get("index", 0)), client_ts)
    elif command == "radio_seek":
        await manager.seek(float(params.get("position_seconds", 0)), client_ts)
    elif command == "volume":
        await manager.set_volume(params.get("volume", 100), client_ts)
    elif command == "radio_set_sound":
        # Réglages de son de CETTE sortie : bornés (jamais d'erreur sur une valeur
        # aberrante), les champs absents gardent leur valeur courante; persistés
        # puis diffusés avec l'état du moteur.
        await radio_commands.apply_sound(db, manager, params.get("sound"), client_ts)
    elif command == "radio_report_route":
        # Résultat de l'application de la route audio par ce lecteur (lib/audioRoute.ts) : mémorisé tel quel pour
        # l'interface Périphériques et pour décider si le serveur doit déplacer le flux. Valeur inconnue = « error ».
        status = params.get("status") if params.get("status") in PLAYER_ROUTE_STATUSES else "error"
        if websocket is not None and ws_manager.set_route_report(websocket, {"status": status}):
            devices_service.note_player_report(manager.channel)
    elif command == "radio_meter":
        # Une interface de mixage est ouverte : le lecteur mesure ses niveaux (bail de quelques secondes, renouvelé par l'interface).
        await manager.request_meter()
    elif command == "radio_report_levels":
        # Niveaux du vumètre : seul le lecteur primaire de la sortie les rapporte (comme la position).
        if websocket is None or not ws_manager.is_primary_kiosk(websocket):
            return
        await manager.relay_levels(sanitize_levels(params.get("levels")))
    elif command == "radio_set_shuffle":
        await manager.set_shuffle(bool(params.get("on")), client_ts)
    elif command == "radio_set_repeat":
        await manager.set_repeat(params.get("mode", "off"), client_ts)
    elif command == "radio_add_to_queue":
        track = db.query(RadioTrack).filter(RadioTrack.id == params.get("track_id")).first()
        if not track:
            raise _not_found(command, manager.channel, f"Morceau {params.get('track_id')}")
        if not track.available:
            await _reject_unavailable(command, manager.channel, track.title, db)
        await manager.add_to_queue(radio_track_dict(track), client_ts)
    elif command == "radio_play_next":
        track = db.query(RadioTrack).filter(RadioTrack.id == params.get("track_id")).first()
        if not track:
            raise _not_found(command, manager.channel, f"Morceau {params.get('track_id')}")
        if not track.available:
            await _reject_unavailable(command, manager.channel, track.title, db)
        await manager.play_next(radio_track_dict(track), client_ts)
    elif command == "radio_move_in_queue":
        # Réordonne la file « À suivre » (glisser-déposer) : seules les pistes À VENIR bougent.
        await manager.move_in_order(
            int(params.get("from_index", -1)), int(params.get("to_index", -1)), client_ts,
        )
    elif command == "radio_remove_from_queue":
        await manager.remove_from_order(int(params.get("index", -1)), client_ts)
    elif command == "radio_track_ended":
        # Règle « toutes les N musiques » : vérifiée
        # ICI (accès DB), pas dans le manager (état pur) — même partage des
        # responsabilités que scheduling et app/playback. Si due, le
        # rappel se joue AVANT l'avancement (attente-fin), qui reprendra à sa
        # fin (`announcement_ended`, deferred_advance=True) plutôt que tout
        # de suite.
        raw_track_id = params.get("track_id")
        track_id = raw_track_id if isinstance(raw_track_id, int) and not isinstance(raw_track_id, bool) else None
        await _handle_radio_track_ended(manager, db, client_ts, track_id)
    elif command == "radio_play_announcement":
        # Déclenchement manuel depuis /radio (bouton rappel) — toujours en
        # mode « duck », null = tirage aléatoire.
        announcement = radio_commands.resolve_announcement(db, params.get("announcement_id"))
        if not announcement:
            raise _not_found(command, manager.channel, "Rappel")
        await radio_commands.play_announcement_now(db, [manager], announcement, client_ts)
    elif command == "announcement_ended":
        await manager.announcement_ended(client_ts)
    elif command == "report_position":
        # Même règle que report_position câblé/réseau : seul le
        # poste /radio primaire (identify role=kiosk channel=radio) a
        # autorité sur la position — un éventuel second onglet /radio ouvert
        # par erreur reste miroir et ne doit pas contredire le rapport du
        # premier.
        if is_kiosk and websocket is not None and not ws_manager.is_primary_kiosk(websocket):
            return
        await manager.report_position(float(params.get("position_seconds", 0)))
    else:
        logger.warning(f"Commande radio WebSocket inconnue reçue : {command}")
        raise CommandRejected("unknown_command", manager.channel, f"Commande radio inconnue : {command}.", 400)


def _due_wait_end_announcement(db: Session, manager) -> RadioAnnouncement | None:
    """Règle « toutes les N musiques » due : compare le compteur
    (déjà incrémenté par l'appelant) au seuil de la règle enregistrée la plus
    stricte. Renvoie un rappel tiré au hasard si une règle active est
    satisfaite, sinon None."""
    count = manager.state.get("tracks_since_announcement", 0)
    rules = (
        db.query(RadioAnnouncementRule)
        .filter(
            RadioAnnouncementRule.enabled == True,  # noqa: E712
            RadioAnnouncementRule.rule_type == RadioAnnouncementRuleType.every_n_tracks,
        )
        .all()
    )
    # Règles propres à la sortie de CE moteur (ou aux deux sorties) : le compteur
    # `tracks_since_announcement` est lui-même par moteur.
    if not any(
        count >= (rule.n_tracks or 1) and rule_targets_output(rule.target, manager.channel) for rule in rules
    ):
        return None
    return radio_commands.resolve_announcement(db, None)
