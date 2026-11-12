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
    """Lance la cible d'une programmation sur l'état de lecture de SON canal (un planning par canal, zéro interférence entre les deux lectures)."""
    if target_type == ScheduleTargetType.radio_playlist:
        radio_channel = normalize_radio_channel(channel)
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

    if scheduled_target_unavailable(db, target_type, target_id):
        logger.warning(f"Programmation ({target_type.value} {target_id}) non lancée : support externe indisponible")
        from app.utils.activity_log import log_activity

        log_activity(db, "schedule_media_unavailable", f"{target_type.value} {target_id}")
        return

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

    manual_video_active = (
        current["current_video"] is not None
        and current["state"] not in (
            PlaybackStateEnum.waiting.value,
            PlaybackStateEnum.offline.value,
            PlaybackStateEnum.playlist_waiting.value,
        )
        and not current.get("scheduled_launch", False)
    )

    if channel == "network" and manual_video_active:
        logger.info(
            f"Programmation ({target_type.value} {target_id}) annulée : lecture manuelle en cours sur le "
            "canal réseau (priorité au manuel)"
        )
        return

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
            if item.video.available
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

    scheduled_launch_store.remember(
        db, channel, target_type.value, target_id, resumed_from or datetime.now(timezone.utc)
    )
    manager.note_scheduled_launch_recorded()


async def fire_schedule(schedule_id: int) -> None:
    """Callback APScheduler déclenché à l'heure d'une programmation."""
    db = SessionLocal()
    try:
        schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        if not schedule or not schedule.active:
            return

        target_type, target_id = schedule.target_type, schedule.target_id

        if schedule.schedule_type == ScheduleType.recurring:
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
            schedule.active = False
            db.commit()

        await launch_target(db, target_type, target_id, schedule.channel or "cable")
    finally:
        db.close()


async def fire_schedule_end(schedule_id: int) -> None:
    """Callback APScheduler déclenché à la FIN d'une fenêtre radio : retour à la playlist d'ambiance par défaut."""
    db = SessionLocal()
    try:
        schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        if not schedule or not schedule.active:
            return
        await _revert_radio_to_default(db, normalize_radio_channel(schedule.channel))
    finally:
        db.close()
