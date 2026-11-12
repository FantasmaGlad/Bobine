"""Lancement d'une cible programmée sur son canal, règles de priorité entre programmation, lecture manuelle et coach."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import (
    OverrideAction,
    PlaybackState,
    Playlist,
    Schedule,
    ScheduleOverride,
    ScheduleTargetType,
    ScheduleType,
    Video,
)
from app.playback.constants import PlaybackStateEnum
from app.playback.manager import get_playback_manager
from app.radio_manager import normalize_radio_channel
from app.scheduling import launch_store as scheduled_launch_store
from app.scheduling.offsets import playback_offset, playlist_resume_point

from .occurrences import LOCAL_TZ
from .radio import _launch_radio_target, _radio_output_is_audible, _revert_radio_to_default

logger = logging.getLogger(__name__)


# Tolérance de retard APScheduler
# ET marge de recalage du jour civil dans fire_schedule ci-dessous : les DEUX
# doivent rester identiques (correctif "recherche d'exception en course avec
# la marge de tolérance de retard"), sinon une programmation proche de minuit
# qui se déclenche avec quelques secondes de retard (redémarrage, contention)
# chercherait par erreur l'override du jour SUIVANT au lieu de celui
# réellement visé.
MISFIRE_GRACE_SECONDS = 60


def scheduled_target_unavailable(db: Session, target_type: ScheduleTargetType, target_id: int) -> bool:
    """Vrai si la cible vidéo/playlist d'une programmation n'a AUCUN média lisible (support externe absent)."""
    if target_type == ScheduleTargetType.video:
        video = db.query(Video).filter(Video.id == target_id).first()
        return video is not None and not video.available
    if target_type == ScheduleTargetType.playlist:
        playlist = db.query(Playlist).filter(Playlist.id == target_id).first()
        if playlist is None or not playlist.items:
            return False
        return not any(item.video.available for item in playlist.items if item.video)
    return False


async def launch_target(
    db: Session, target_type: ScheduleTargetType, target_id: int, channel: str = "cable",
    resumed_from: datetime | None = None,
) -> None:
    """Lance la cible d'une programmation sur l'état de lecture de SON canal
    (un planning par canal, zéro interférence entre les deux lectures).

    `resumed_from` : heure du lancement d'origine quand le serveur reprend une programmation après un
    redémarrage ; la lecture démarre alors à la position qu'elle aurait atteinte sans la coupure."""
    if target_type == ScheduleTargetType.radio_playlist:
        # 3e canal radio, sous-système totalement indépendant : aucune des règles de conflit câblé/réseau ci-dessous ne
        # s'applique — pas de mode coach, pas de "lecture manuelle en cours".
        radio_channel = normalize_radio_channel(channel)
        # Une programmation « radio câblée » doit SE FAIRE ENTENDRE : si l'écran câblé n'est pas sur
        # Radio, elle l'y ramène (comme un clic sur « Radio », la vidéo en cours est arrêtée — le
        # dernier bloc qui démarre l'emporte, règle du planning). Seul le mode coach garde la priorité :
        # on ne coupe jamais une séance en direct, la playlist est alors chargée en pause et journalisée.
        paused = False
        if not _radio_output_is_audible(db, radio_channel):
            if get_playback_manager("cable").snapshot()["state"] == PlaybackStateEnum.coach_mode.value:
                paused = True
                logger.info(
                    f"Programmation radio ({radio_channel}) : mode coach actif, playlist chargée en pause "
                    "sans basculer l'écran câblé"
                )
            else:
                from app.api.routes.settings.display import apply_display_output

                logger.info(f"Programmation radio ({radio_channel}) : l'écran câblé passe sur Radio")
                await apply_display_output(db, "cable", "radio", activate_radio=False)
        await _launch_radio_target(db, target_id, radio_channel, start_paused=paused)
        return

    manager = get_playback_manager(channel)
    current = manager.snapshot()

    # Média sur un support externe débranché : on ne lance rien et on n'interrompt SURTOUT pas la lecture en cours.
    if scheduled_target_unavailable(db, target_type, target_id):
        logger.warning(f"Programmation ({target_type.value} {target_id}) non lancée : support externe indisponible")
        from app.utils.activity_log import log_activity

        log_activity(db, "schedule_media_unavailable", f"{target_type.value} {target_id}")
        return

    # Priorité au mode audio coach : contrairement au canal câblé, la
    # programmation n'est PAS prioritaire ici. Le coach anime un cours en
    # physique ; une programmation automatique ne doit surtout pas lui couper
    # le son. On n'appelle jamais launch_target dans ce cas : la cible est
    # mémorisée telle quelle (pas de position, elle n'a jamais démarré) pour
    # une relance manuelle ultérieure depuis l'UI, et on s'arrête là.
    # (Ne peut concerner que le canal câblé, seul à porter le mode coach.)
    if current["state"] == PlaybackStateEnum.coach_mode.value:
        db.query(PlaybackState).filter(PlaybackState.channel == channel).delete()
        db.add(
            PlaybackState(
                target_type=target_type.value,
                target_id=target_id,
                cause="coach_priority",
                channel=channel,
            )
        )
        db.commit()
        logger.info(
            f"Programmation ({target_type.value} {target_id}) reportée : mode audio coach actif"
        )
        return

    # `current_video` reste renseigné (celui qui
    # vient de se terminer) pendant `playlist_waiting`, comme le sont déjà
    # obligées de le vérifier PlaybackManager.play/pause/seek/report_position
    # — sans cette même exclusion ici, une programmation qui se déclenche
    # exactement dans cette fenêtre de quelques secondes croit qu'une "vidéo
    # manuelle" est active et sauvegarde une fausse interruption pointant sur
    # la vidéo déjà terminée (position ≈ sa fin, rien de sensé à reprendre).
    # `scheduled_launch` (posé
    # par PlaybackManager.load/load_playlist quand appelés avec scheduled=
    # True, cf. ci-dessous) distingue une vraie lecture manuelle d'un
    # reliquat de programmation encore en cours — sans quoi la règle réseau
    # "le manuel gagne toujours" plus bas s'appliquait aussi à tort à un
    # chevauchement programmation vs programmation, annulant silencieusement
    # la seconde au lieu de la laisser couper proprement la première.
    manual_video_active = (
        current["current_video"] is not None
        and current["state"] not in (
            PlaybackStateEnum.waiting.value,
            PlaybackStateEnum.offline.value,
            PlaybackStateEnum.playlist_waiting.value,
        )
        and not current.get("scheduled_launch", False)
    )

    # Règle de conflit RÉSEAU (retour utilisateur 2026-07-21) : sur ce canal,
    # un lancement manuel en cours gagne toujours — une programmation qui
    # arrive en même temps est simplement annulée, sans jamais interrompre la
    # lecture manuelle. Contraire à la règle du canal câblé ci-dessous : le réseau sert
    # des appareils individuels lancés à la demande, pas le planning de la
    # salle physique, donc la priorité s'inverse.
    if channel == "network" and manual_video_active:
        logger.info(
            f"Programmation ({target_type.value} {target_id}) annulée : lecture manuelle en cours sur le "
            "canal réseau (priorité au manuel)"
        )
        return

    # Règle de conflit CÂBLÉ : la programmation est prioritaire sur une
    # lecture manuelle en cours. On ne la reprend jamais automatiquement ;
    # on mémorise juste sa position pour une relance manuelle depuis l'UI
    # (endpoints /api/playback/interrupted*). Une seule interruption "en
    # attente de reprise" à la fois PAR CANAL : la précédente (non reprise)
    # du même canal est purgée.
    if manual_video_active:
        db.query(PlaybackState).filter(PlaybackState.channel == channel).delete()
        db.add(
            PlaybackState(
                video_id=current["current_video"]["id"],
                position_seconds=current["position_seconds"],
                cause="schedule",
                channel=channel,
            )
        )
        db.commit()

    if target_type == ScheduleTargetType.video:
        video = db.query(Video).filter(Video.id == target_id).first()
        if not video:
            logger.warning(f"Cible programmée introuvable : vidéo {target_id}")
            return
        start_position = 0.0
        if resumed_from is not None:
            offset = playback_offset(resumed_from, datetime.now(timezone.utc), video.duration_seconds)
            if offset is None:
                logger.info(f"Reprise ({channel}) : la vidéo {target_id} est terminée, rien à relancer")
                scheduled_launch_store.close(db, channel)
                return
            start_position = offset
        thumb = video.thumbnail_path.split("/")[-1] if video.thumbnail_path else None
        await manager.load(
            video.id, video.title, video.duration_seconds, video.program, thumbnail_url=thumb, release=video.release,
            description=video.description, audio_channels=video.audio_channels, audio_codec=video.audio_codec,
            fps=video.fps, bitrate_kbps=video.bitrate_kbps, width=video.width, height=video.height,
            launch_type="schedule", scheduled=True, start_position=start_position,
        )
    else:
        playlist = db.query(Playlist).filter(Playlist.id == target_id).first()
        if not playlist:
            logger.warning(f"Cible programmée introuvable : playlist {target_id}")
            return
        sorted_items = sorted(playlist.items, key=lambda item: item.position)
        items_data = [
            {
                "id": item.video.id,
                "title": item.video.title,
                "duration_seconds": item.video.duration_seconds,
                "program": item.video.program,
                "release": item.video.release,
                "thumbnail_url": item.video.thumbnail_path.split("/")[-1] if item.video.thumbnail_path else None,
                "description": item.video.description,
                "audio_channels": item.video.audio_channels,
                "audio_codec": item.video.audio_codec,
                "fps": item.video.fps,
                "bitrate_kbps": item.video.bitrate_kbps,
                "width": item.video.width,
                "height": item.video.height,
                "storage_id": item.video.storage_id,
            }
            for item in sorted_items
            if item.video.available  # les médias d'un support débranché sont sautés
        ]
        start_index, start_position = 0, 0.0
        if resumed_from is not None:
            elapsed = (datetime.now(timezone.utc) - resumed_from).total_seconds()
            point = playlist_resume_point(
                [item["duration_seconds"] for item in items_data], float(settings.wait_time_between_courses), elapsed
            )
            if point is None:
                logger.info(f"Reprise ({channel}) : la playlist {target_id} est terminée, rien à relancer")
                scheduled_launch_store.close(db, channel)
                return
            start_index, start_position = point
        await manager.load_playlist(
            playlist.id, playlist.name, items_data, scheduled=True, start_index=start_index, start_position=start_position
        )

    # Mémorisé pour qu'un redémarrage du serveur reprenne ce cours à la bonne position (`scheduling/resume.py`).
    scheduled_launch_store.remember(
        db, channel, target_type.value, target_id, resumed_from or datetime.now(timezone.utc)
    )
    manager.note_scheduled_launch_recorded()


async def fire_schedule(schedule_id: int) -> None:
    """Callback APScheduler déclenché à l'heure d'une programmation.

    Un seul processus, donc un seul planificateur : aucun déclenchement en double (`docs/ARCHITECTURE.md` §1)."""
    db = SessionLocal()
    try:
        schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        if not schedule or not schedule.active:
            return

        target_type, target_id = schedule.target_type, schedule.target_id

        if schedule.schedule_type == ScheduleType.recurring:
            # Jour civil *local* : une occurrence récurrente est ancrée au
            # calendrier de la salle, pas à la date UTC (qui peut différer
            # près de minuit selon le fuseau).
            # Recalé de MISFIRE_GRACE_SECONDS avant de prendre le jour civil : ce callback peut s'exécuter jusqu'à
            # misfire_grace_time secondes après l'heure prévue (add_job
            # ci-dessous). Sans ce recalage, une programmation à 23:59:30
            # déclenchée avec 45s de retard (23:59:75 = 00:00:15) verrait
            # `date.today()` retourner le jour SUIVANT, alors que l'override
            # (annulation/remplacement) visé par l'utilisateur a été créé
            # pour le jour ORIGINALEMENT prévu.
            today = (datetime.now(LOCAL_TZ) - timedelta(seconds=MISFIRE_GRACE_SECONDS)).date()
            overrides = (
                db.query(ScheduleOverride).filter(ScheduleOverride.schedule_id == schedule.id).all()
            )
            match = next((o for o in overrides if o.occurrence_date.date() == today), None)
            if match:
                if match.action == OverrideAction.cancelled:
                    logger.info(f"Programmation {schedule.id} : occurrence du {today} annulée (override), non lancée")
                    return
                target_type, target_id = match.replacement_target_type, match.replacement_target_id
        else:
            # Une programmation ponctuelle ne se déclenche qu'une fois :
            # la désactiver évite qu'elle ne traîne comme "active" dans les
            # listes une fois passée.
            schedule.active = False
            db.commit()

        await launch_target(db, target_type, target_id, schedule.channel or "cable")
    finally:
        db.close()


async def fire_schedule_end(schedule_id: int) -> None:
    """Callback APScheduler déclenché à la FIN d'une fenêtre radio : retour à la playlist d'ambiance par défaut. N'existe que pour
    les programmations radio récurrentes avec `end_time` (pas de mode 24/7,
    pas de programmation ponctuelle — cf. _sync_end_job)."""
    db = SessionLocal()
    try:
        schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        if not schedule or not schedule.active:
            return
        await _revert_radio_to_default(db, normalize_radio_channel(schedule.channel))
    finally:
        db.close()
