"""Exécution d'une commande de lecture vidéo ou audio sur le moteur de son canal."""

import logging
from datetime import datetime

from fastapi import WebSocket
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.routes.settings.display import get_display_output_value
from app.models import (
    AudioCourse,
    AudioPlaylist,
    Background,
    Playlist,
    Video,
)
from app.playback_manager import DEFAULT_CHANNEL, get_playback_manager
from app.radio_manager import (
    is_radio_channel,
    normalize_radio_channel,
)
from app.utils import video_sound
from app.utils.activity_log import log_activity
from app.utils.importer import is_image_background
from app.utils.playback_session_tracker import (
    close_playback_session,
    start_playback_session,
    update_playback_session_progress,
)
from app.utils.ws_manager import manager as ws_manager

from .cinema import _apply_cinema_command_to_clock, _cinema_clock_for, _cinema_launched_video
from .core import CommandRejected, _cinema_sessions, _not_found, _reject_unavailable, _resolve_channel
from .media_items import _build_audio_playlist_tracks, _build_playlist_video_items, _load_audio_course_into_manager, _thumbnail_filename
from .radio_commands import _handle_radio_command

logger = logging.getLogger(__name__)


def _log_track_if_changed(db: Session, manager, index_before: int | None) -> None:
    """Journalise l'entrée en lecture d'une nouvelle
    piste, uniquement si l'index a effectivement changé (une commande peut ne
    rien faire — dernière piste déjà atteinte, mode manuel après une fin de
    piste — auquel cas rien n'a été "lancé")."""
    index_after = manager.state.get("audio_track_index")
    if index_after is None or index_after == index_before:
        return
    tracks = manager.state.get("audio_tracks")
    if tracks and 0 <= index_after < len(tracks):
        # `_log_track_if_changed` elle-même reste synchrone (pas
        # d'`await` disponible dans ses appelants directs sans les rendre
        # tous async) — ses appelants (ci-dessous) invoquent DÉSORMAIS
        # cette fonction via run_in_threadpool plutôt que directement.
        log_activity(db, "audio_track_started", tracks[index_after]["title"])


async def _ensure_not_locked(db: Session, command: str, channel: str) -> None:
    """
    Verrou du mode cinéma, PAR CANAL : un lancement manuel cible désormais l'état de lecture d'UN
    canal précis. Si CE canal est en mode cinéma (libre-service), sa lecture
    pilotée ne serait visible nulle part — le laisser passer démarrerait une
    vidéo fantôme en arrière-plan. L'autre canal n'entre plus en ligne de
    compte : il a son propre état. Rejet renvoyé UNIQUEMENT à l'émetteur
    (pas de broadcast) pour que l'admin puisse afficher un avertissement.
    """
    # lecture DB sortie de la boucle — appelée par CHAQUE
    # commande load*, potentiellement en concurrence avec un flux vidéo
    # actif (stream_*) qui sature déjà le disque/FUSE.
    output = await run_in_threadpool(get_display_output_value, db, channel)
    if output not in ("cinema", "radio"):
        return
    # Même logique pour la radio : sortie câblée basculée sur Radio = aucun écran
    # vidéo pour afficher le lancement, il serait lui aussi « fantôme ».
    reason = "cinema_locked" if output == "cinema" else "radio_locked"
    logger.info(f"Commande {command} ignorée : le canal '{channel}' est en mode {output} (verrouillé)")
    raise CommandRejected(reason, channel, f"Le canal {channel} affiche le mode {output} : aucun écran vidéo ne montrerait ce lancement.")


async def execute_command(
    message: dict,
    db: Session,
    websocket: WebSocket | None = None,
    is_kiosk: bool = False,
    default_channel: str = DEFAULT_CHANNEL,
) -> None:
    """Point d'entrée unique d'une commande de lecture, commun au WebSocket et à la façade REST. Lève
    `CommandRejected` ; un paramètre de mauvais type devient un refus `invalid_params`, pas une erreur."""
    try:
        await _handle_command(message, db, websocket, is_kiosk=is_kiosk, default_channel=default_channel)
    except (TypeError, ValueError) as exc:
        raw_channel = (message.get("params") or {}).get("channel") or default_channel
        raise CommandRejected("invalid_params", str(raw_channel), f"Paramètres invalides : {exc}", 422) from exc


async def _handle_command(
    message: dict,
    db: Session,
    websocket: WebSocket | None = None,
    is_kiosk: bool = False,
    default_channel: str = DEFAULT_CHANNEL,
) -> None:
    command = message.get("command")
    params = message.get("params") or {}
    client_ts = params.get("client_ts")

    if command == "pong":
        # Réponse du client à notre keepalive — pas un
        # ordre de lecture, ne fait qu'acter que la connexion est vivante.
        # Traité avant toute résolution de canal : ne concerne aucun des
        # gestionnaires d'état.
        if websocket is not None:
            ws_manager.note_pong(websocket)
        return

    # Canal ciblé par la commande : porté par chaque commande des tableaux de bord ; un kiosk,
    # lui, agit toujours sur le canal déclaré à son identify. Absent ou
    # invalide = canal câblé (compatibilité anciens clients).
    raw_channel = params.get("channel") or default_channel
    if is_radio_channel(raw_channel):
        # Sortie radio, moteur INDÉPENDANT par sortie : vocabulaire de
        # commandes propre (radio_*), géré séparément plutôt que dans la
        # chaîne câblé/réseau ci-dessous.
        await _handle_radio_command(
            command, params, client_ts, db, websocket, is_kiosk,
            radio_channel=normalize_radio_channel(raw_channel),
        )
        return

    channel = _resolve_channel(raw_channel)
    manager = get_playback_manager(channel)

    if command == "load":
        await _ensure_not_locked(db, command, channel)
        video_id = params.get("video_id")
        video = await run_in_threadpool(lambda: db.query(Video).filter(Video.id == video_id).first())
        if not video:
            raise _not_found(command, channel, f"Vidéo {video_id}")
        if not video.available:
            await _reject_unavailable(command, channel, video.title, db)
        await manager.load(
            video.id, video.title, video.duration_seconds, video.program, client_ts,
            release=video.release, thumbnail_url=_thumbnail_filename(video.thumbnail_path),
            description=video.description, audio_channels=video.audio_channels,
            audio_codec=video.audio_codec, fps=video.fps, bitrate_kbps=video.bitrate_kbps,
            width=video.width, height=video.height,
        )
        await run_in_threadpool(log_activity, db, "video_started", video.title)
    elif command == "load_background":
        background_id = params.get("background_id")
        background = await run_in_threadpool(lambda: db.query(Background).filter(Background.id == background_id).first())
        if not background:
            raise _not_found(command, channel, f"Fond animé {background_id}")
        await manager.load_background(
            background.id, background.title, is_image_background(background.file_path), client_ts
        )
        await run_in_threadpool(log_activity, db, "background_started", background.title)
    elif command == "load_audio_course":
        # Mode coach réservé au CANAL CÂBLÉ : le coach anime un cours dans la salle physique,
        # ça n'a pas de sens sur le canal réseau — la commande y est rejetée.
        if channel != "cable":
            logger.info("Commande load_audio_course ignorée : le mode coach est réservé au canal câblé")
            raise CommandRejected("coach_cable_only", channel, "Le mode coach est réservé au canal câblé.")
        await _ensure_not_locked(db, command, channel)
        course_id = params.get("audio_course_id")
        course = await run_in_threadpool(lambda: db.query(AudioCourse).filter(AudioCourse.id == course_id).first())
        if not course:
            raise _not_found(command, channel, f"Cours audio {course_id}")
        if not await run_in_threadpool(lambda: course.available):
            await _reject_unavailable(command, channel, course.title, db)
        await _load_audio_course_into_manager(
            course, manager, db,
            chain_mode=params.get("chain_mode"),
            chain_timer_seconds=params.get("chain_timer_seconds"),
            client_ts=client_ts,
        )
        await run_in_threadpool(log_activity, db, "audio_course_started", course.title)
    elif command == "load_audio_playlist":
        # Même restriction que load_audio_course : une playlist audio anime le mode coach,
        # réservé au canal câblé.
        if channel != "cable":
            logger.info("Commande load_audio_playlist ignorée : le mode coach est réservé au canal câblé")
            raise CommandRejected("coach_cable_only", channel, "Le mode coach est réservé au canal câblé.")
        await _ensure_not_locked(db, command, channel)
        audio_playlist_id = params.get("audio_playlist_id")
        audio_playlist = await run_in_threadpool(
            lambda: db.query(AudioPlaylist).filter(AudioPlaylist.id == audio_playlist_id).first()
        )
        if not audio_playlist:
            raise _not_found(command, channel, f"Playlist audio {audio_playlist_id}")
        # `item.track`/
        # `item.background` sont des relations ORM paresseuses — chaque
        # accès peut déclencher sa propre requête SQL synchrone. Regroupées
        # dans un seul aller-retour au threadpool plutôt que par élément.
        tracks_data = await run_in_threadpool(_build_audio_playlist_tracks, audio_playlist)
        await manager.load_audio_playlist(
            audio_playlist.id, audio_playlist.name, tracks_data,
            chain_mode=params.get("chain_mode"),
            chain_timer_seconds=params.get("chain_timer_seconds"),
            client_ts=client_ts,
        )
        log_activity(db, "audio_playlist_started", audio_playlist.name)
    elif command == "audio_set_background":
        # Changement de fond EN DIRECT pendant le mode coach :
        # background_id nul retire le fond en cours (aucun fond).
        background_id = params.get("background_id")
        title, is_image = None, False
        if background_id:
            background = db.query(Background).filter(Background.id == background_id).first()
            if not background:
                raise _not_found(command, channel, f"Fond animé {background_id}")
            title, is_image = background.title, is_image_background(background.file_path)
        await manager.audio_set_background(background_id, title, is_image, client_ts)
    elif command == "audio_next_track":
        index_before = manager.state.get("audio_track_index")
        await manager.audio_next_track(client_ts)
        await run_in_threadpool(_log_track_if_changed, db, manager, index_before)
    elif command == "audio_previous_track":
        index_before = manager.state.get("audio_track_index")
        await manager.audio_previous_track(client_ts)
        await run_in_threadpool(_log_track_if_changed, db, manager, index_before)
    elif command == "audio_restart_track":
        await manager.audio_restart_track(client_ts)
    elif command == "audio_jump_to_track":
        index_before = manager.state.get("audio_track_index")
        await manager.audio_jump_to_track(int(params.get("index", 0)), client_ts)
        await run_in_threadpool(_log_track_if_changed, db, manager, index_before)
    elif command == "audio_set_chain_mode":
        await manager.audio_set_chain_mode(params.get("mode", "auto"), client_ts)
    elif command == "audio_set_chain_timer":
        await manager.audio_set_chain_timer(float(params.get("seconds", 20)), client_ts)
    elif command == "audio_report_position":
        # Même règle que report_position : seul le kiosk primaire rapporte.
        if is_kiosk and websocket is not None and not ws_manager.is_primary_kiosk(websocket):
            return
        await manager.audio_report_position(float(params.get("position_seconds", 0)))
    elif command == "audio_track_ended":
        index_before = manager.state.get("audio_track_index")
        raw_index = params.get("track_index")
        track_index = raw_index if isinstance(raw_index, int) and not isinstance(raw_index, bool) else None
        await manager.audio_track_ended(client_ts, track_index=track_index)
        # Couvre aussi bien l'enchaînement auto/minuterie que la
        # navigation manuelle ci-dessus : dans les deux cas l'index de piste a
        # changé, seul cas où une NOUVELLE piste a réellement été lancée.
        await run_in_threadpool(_log_track_if_changed, db, manager, index_before)
    elif command == "load_playlist":
        await _ensure_not_locked(db, command, channel)
        playlist_id = params.get("playlist_id")
        playlist = await run_in_threadpool(lambda: db.query(Playlist).filter(Playlist.id == playlist_id).first())
        if not playlist:
            raise _not_found(command, channel, f"Playlist {playlist_id}")
        items_data = await run_in_threadpool(_build_playlist_video_items, playlist)
        if not items_data and await run_in_threadpool(lambda: bool(playlist.items)):
            await _reject_unavailable(command, channel, playlist.name, db)
        await manager.load_playlist(
            playlist.id, playlist.name, items_data, client_ts
        )
        await run_in_threadpool(log_activity, db, "playlist_started", playlist.name)
    elif command == "play":
        await manager.play(client_ts)
    elif command == "pause":
        await manager.pause(client_ts)
    elif command == "stop":
        # Évènement "annulation" : n'a de sens comme évènement que s'il y avait
        # effectivement quelque chose en cours à interrompre.
        current = manager.snapshot()
        if current["current_video"] or current["current_background"] or current["current_audio_course"]:
            title = (
                (current["current_video"] or {}).get("title")
                or (current["current_background"] or {}).get("title")
                or (current["current_audio_course"] or {}).get("title")
            )
            await run_in_threadpool(log_activity, db, "playback_stopped", title)
        await manager.stop(client_ts)
    elif command == "seek":
        await manager.seek(float(params.get("position_seconds", 0)), client_ts)
    elif command == "volume":
        await manager.set_volume(params.get("volume", 100), client_ts)
    elif command == "speed":
        await manager.set_speed(params.get("speed", 1.0), client_ts)
    elif command == "set_sound":
        # Réglages de son de CE canal : bornés (jamais d'erreur), champs absents inchangés ; persistés puis diffusés.
        await video_sound.apply_video_sound(db, manager, params.get("sound"), client_ts)
    elif command == "set_subtitle":
        await manager.set_subtitle(params.get("subtitle"), client_ts)
    elif command == "next_video":
        await manager.next_video(client_ts)
    elif command == "previous_video":
        await manager.previous_video(client_ts)
    elif command == "skip_waiting":
        await manager.skip_waiting(client_ts)
    elif command == "video_ended":
        # Évènement "vidéos jouées (fin)" : capturé AVANT l'appel, `video_ended()`
        # vide `current_video` (arrêt standard ou avance de playlist).
        title = (manager.state.get("current_video") or {}).get("title")
        raw_video_id = params.get("video_id")
        ended_video_id = int(raw_video_id) if isinstance(raw_video_id, (int, float, str)) and str(raw_video_id).lstrip("-").isdigit() else None
        current_id = (manager.state.get("current_video") or {}).get("id")
        was_current = manager.state["state"] == "playing" and (ended_video_id is None or ended_video_id == current_id)
        await manager.video_ended(client_ts, video_id=ended_video_id)
        if title and was_current:
            await run_in_threadpool(log_activity, db, "video_ended", title)
    elif command == "report_position":
        # Seul le kiosk primaire a autorité sur la position de lecture : les kiosks miroirs sont ignorés pour éviter les
        # conflits de position entre plusieurs kiosks simultanés.
        if is_kiosk and websocket is not None and not ws_manager.is_primary_kiosk(websocket):
            return
        await manager.report_position(float(params.get("position_seconds", 0)))
    elif command == "cinema_report":
        # Supervision du mode cinéma : la lecture cinéma est LOCALE
        # à chaque appareil (jamais dans le playback_manager), mais la page
        # /cinema remonte périodiquement ce qu'elle joue pour que les
        # tableaux de bord du canal l'affichent. Simple relais, aucun état
        # serveur : si la page cinéma se ferme, ses rapports cessent et le
        # tableau de bord efface l'affichage après un délai sans nouvelles.
        pos = float(params.get("position_seconds") or 0)
        dur = float(params.get("duration_seconds") or 0)
        vid = params.get("video_id")
        is_playing = bool(params.get("playing"))

        # Suivi de session SQLite pour /cinema
        if is_playing and vid:
            if channel not in _cinema_sessions:
                sess_id = await run_in_threadpool(
                    start_playback_session, db, int(vid), channel, "cinema", dur
                )
                if sess_id:
                    _cinema_sessions[channel] = sess_id
            else:
                await run_in_threadpool(
                    update_playback_session_progress, db, _cinema_sessions[channel], pos
                )
        elif not params.get("title") and channel in _cinema_sessions:
            sess_id = _cinema_sessions.pop(channel)
            await run_in_threadpool(close_playback_session, db, sess_id, pos)

        await ws_manager.broadcast({
            "event": "cinema_state",
            "channel": channel,
            "data": {
                "title": params.get("title"),
                "program": params.get("program"),
                "position_seconds": pos,
                "duration_seconds": dur,
                "playing": is_playing,
                "video_id": vid,
                "reported_at": datetime.now().timestamp(),
            },
        })
    elif command == "cinema_command":
        # Pendant depuis l'admin : play/pause/seek/stop appliqué par les
        # pages /cinema du canal (toutes — sur le câblé il n'y a qu'un seul
        # écran, cas d'usage principal). "stop" ramène à la grille de choix.
        # "launch" : émis par
        # /grid (écran de sélection découplé, tablette Android) pour lancer
        # un cours précis sur le(s) /cinema du canal — jamais émis par le
        # profil desktop existant, sans effet tant que /grid n'est pas utilisé.
        action = params.get("action")
        if action not in ("play", "pause", "seek", "stop", "launch"):
            raise CommandRejected("invalid_params", channel, f"Action cinéma inconnue : {action} (play, pause, seek, stop, launch).", 422)

        # Gestion des sessions de lecture sur commande directe
        if action == "launch" and params.get("video_id"):
            vid = int(params.get("video_id"))
            if channel in _cinema_sessions:
                old_id = _cinema_sessions.pop(channel)
                await run_in_threadpool(close_playback_session, db, old_id)
            launch_type = "grid" if params.get("source") == "grid" or not is_kiosk else "cinema"
            sess_id = await run_in_threadpool(
                start_playback_session, db, vid, channel, launch_type, float(params.get("duration_seconds") or 0)
            )
            if sess_id:
                _cinema_sessions[channel] = sess_id
        elif action == "stop" and channel in _cinema_sessions:
            sess_id = _cinema_sessions.pop(channel)
            pos = float(params.get("position_seconds") or 0)
            await run_in_threadpool(close_playback_session, db, sess_id, pos)

        _apply_cinema_command_to_clock(channel, action, params)
        cmd_payload = {
            "event": "cinema_command",
            "channel": channel,
            "action": action,
            "position_seconds": float(params.get("position_seconds") or 0),
            "video_id": params.get("video_id"),
        }
        launched = _cinema_launched_video.get(channel)
        if launched is not None and action != "stop":
            # Ancre d'horloge du cours lancé par ordre + son identifiant : les pages
            # qui jouent CE cours s'y calent.
            cmd_payload["clock"] = _cinema_clock_for(channel).to_dict()
            cmd_payload["clock_video_id"] = launched
        if "title" in params:
            cmd_payload["title"] = params["title"]
        if "duration_seconds" in params:
            cmd_payload["duration_seconds"] = params["duration_seconds"]

        await ws_manager.broadcast(cmd_payload)
    else:
        logger.warning(f"Commande WebSocket inconnue reçue : {command}")
        raise CommandRejected("unknown_command", channel, f"Commande inconnue : {command}.", 400)
