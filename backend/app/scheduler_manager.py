import json
import logging
from datetime import date, datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from sqlalchemy.orm import Session
from tzlocal import get_localzone

from app.database import SessionLocal
from app.models import (
    OverrideAction,
    Playlist,
    PlaybackState,
    RadioPlaylist,
    RadioTrack,
    Schedule,
    ScheduleOverride,
    ScheduleTargetType,
    ScheduleType,
    Setting,
    Video,
)
from app.playback_manager import PlaybackStateEnum, get_playback_manager
from app.utils.hardware_info import purge_expired_logs_and_metrics, record_hardware_snapshot

logger = logging.getLogger(__name__)

# Le planning représente le programme réel d'une salle physique : les horaires
# saisis par l'utilisateur (ex. "RPM tous les mardis 18h00") sont des heures
# locales de la salle. On ancre donc le scheduler sur le fuseau local de la
# machine plutôt que UTC, pour que les récurrences restent correctes après un
# changement d'heure été/hiver (F5.5 : fonctionnement horloge locale).
LOCAL_TZ = get_localzone()

# Filet de sécurité anti-boucle infinie lors du déroulé d'une récurrence sur
# une plage de dates (ne devrait jamais être atteint en usage normal : une
# programmation hebdomadaire sur une plage d'un an ne produit que ~52 occurrences).
_MAX_OCCURRENCES_PER_SCHEDULE = 1000

# Tolérance de retard APScheduler (réf. sync_schedule_job, misfire_grace_time)
# ET marge de recalage du jour civil dans fire_schedule ci-dessous : les DEUX
# doivent rester identiques (correctif "recherche d'exception en course avec
# la marge de tolérance de retard"), sinon une programmation proche de minuit
# qui se déclenche avec quelques secondes de retard (redémarrage, contention)
# chercherait par erreur l'override du jour SUIVANT au lieu de celui
# réellement visé.
MISFIRE_GRACE_SECONDS = 60

_scheduler: AsyncIOScheduler | None = None


def _job_id(schedule_id: int) -> str:
    return f"schedule-{schedule_id}"


def _job_id_end(schedule_id: int) -> str:
    return f"schedule-{schedule_id}-end"


def ensure_utc(value: datetime) -> datetime:
    """
    SQLite ne conserve pas le fuseau des datetimes stockés : une valeur aware
    écrite en base est relue *naïve* par SQLAlchemy, alors qu'elle représente
    toujours un instant UTC (convention utilisée dans tout le schéma —
    imported_at, created_at, etc.). On la retague donc systématiquement avant
    toute comparaison ou sérialisation, plutôt que de la laisser se comparer
    silencieusement de travers avec un datetime.now(timezone.utc) frais.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _build_cron_trigger(schedule: Schedule) -> CronTrigger:
    rule = json.loads(schedule.recurrence_rule)
    days = ",".join(str(d) for d in rule["days_of_week"])
    hour, minute = (int(part) for part in rule["time"].split(":"))
    return CronTrigger(day_of_week=days, hour=hour, minute=minute, timezone=LOCAL_TZ)


def resolve_target_title(
    db: Session, target_type: ScheduleTargetType, target_id: int
) -> tuple[str | None, str | None]:
    """Titre + programme d'une cible de programmation, pour l'affichage (planning, overrides)."""
    if target_type == ScheduleTargetType.video:
        video = db.query(Video).filter(Video.id == target_id).first()
        return (video.title, video.program) if video else (None, None)
    if target_type == ScheduleTargetType.radio_playlist:
        radio_playlist = db.query(RadioPlaylist).filter(RadioPlaylist.id == target_id).first()
        return (radio_playlist.name, None) if radio_playlist else (None, None)
    playlist = db.query(Playlist).filter(Playlist.id == target_id).first()
    return (playlist.name, None) if playlist else (None, None)


def expand_occurrences(
    db: Session, schedules: list[Schedule], start: datetime, end: datetime
) -> list[dict]:
    """
    Développe une liste de programmations actives en occurrences concrètes
    dans l'intervalle [start, end], overrides résolus (réf. F5.2/F5.4, UX3.14-16).

    Les occurrences annulées sont *incluses* dans le résultat (avec le titre
    d'origine) plutôt qu'omises : le planning doit pouvoir les afficher barrées
    (UX3.15), pas simplement les faire disparaître.
    """
    if not schedules:
        return []

    schedule_ids = [s.id for s in schedules]
    overrides = (
        db.query(ScheduleOverride).filter(ScheduleOverride.schedule_id.in_(schedule_ids)).all()
    )
    overrides_by_key: dict[tuple[int, date], ScheduleOverride] = {
        (o.schedule_id, o.occurrence_date.date()): o for o in overrides
    }

    results: list[dict] = []
    for schedule in schedules:
        if schedule.schedule_type == ScheduleType.once:
            run_at = ensure_utc(schedule.run_at) if schedule.run_at else None
            if run_at and start <= run_at <= end:
                title, program = resolve_target_title(db, schedule.target_type, schedule.target_id)
                results.append(
                    {
                        "schedule_id": schedule.id,
                        "channel": schedule.channel or "cable",
                        "schedule_type": schedule.schedule_type,
                        "run_at": run_at,
                        "target_type": schedule.target_type,
                        "target_id": schedule.target_id,
                        "title": title,
                        "program": program,
                        "is_override": False,
                        "override_action": None,
                        "override_id": None,
                    }
                )
            continue

        trigger = _build_cron_trigger(schedule)
        fire_time = trigger.get_next_fire_time(None, start)
        guard = 0
        while fire_time is not None and fire_time <= end and guard < _MAX_OCCURRENCES_PER_SCHEDULE:
            guard += 1
            override = overrides_by_key.get((schedule.id, fire_time.date()))

            if override is not None and override.action == OverrideAction.cancelled:
                title, program = resolve_target_title(db, schedule.target_type, schedule.target_id)
                results.append(
                    {
                        "schedule_id": schedule.id,
                        "channel": schedule.channel or "cable",
                        "schedule_type": schedule.schedule_type,
                        "run_at": fire_time,
                        "target_type": schedule.target_type,
                        "target_id": schedule.target_id,
                        "title": title,
                        "program": program,
                        "is_override": True,
                        "override_action": OverrideAction.cancelled,
                        "override_id": override.id,
                    }
                )
            elif override is not None and override.action == OverrideAction.replaced:
                title, program = resolve_target_title(
                    db, override.replacement_target_type, override.replacement_target_id
                )
                results.append(
                    {
                        "schedule_id": schedule.id,
                        "channel": schedule.channel or "cable",
                        "schedule_type": schedule.schedule_type,
                        "run_at": fire_time,
                        "target_type": override.replacement_target_type,
                        "target_id": override.replacement_target_id,
                        "title": title,
                        "program": program,
                        "is_override": True,
                        "override_action": OverrideAction.replaced,
                        "override_id": override.id,
                    }
                )
            else:
                title, program = resolve_target_title(db, schedule.target_type, schedule.target_id)
                results.append(
                    {
                        "schedule_id": schedule.id,
                        "channel": schedule.channel or "cable",
                        "schedule_type": schedule.schedule_type,
                        "run_at": fire_time,
                        "target_type": schedule.target_type,
                        "target_id": schedule.target_id,
                        "title": title,
                        "program": program,
                        "is_override": False,
                        "override_action": None,
                        "override_id": None,
                    }
                )

            fire_time = trigger.get_next_fire_time(fire_time, fire_time)

    results.sort(key=lambda o: o["run_at"])
    return results


def _radio_track_dict(track) -> dict:
    """Même forme que routers/playback.py::_radio_track_dict — dupliqué
    volontairement plutôt que partagé entre les deux modules (fonction
    minuscule, évite un couplage supplémentaire sur un fichier partagé et
    sensible)."""
    return {
        "id": track.id,
        "title": track.title,
        "artist": track.artist,
        "album": track.album,
        "duration_seconds": track.duration_seconds,
        "cover_url": f"/radio/tracks/{track.id}/cover" if track.cover_path else None,
    }


async def _launch_radio_target(db: Session, playlist_id: int) -> None:
    """Lance une playlist radio EN BOUCLE (réf. lot L7, D9) : utilisé aussi
    bien par l'auto-boot (ambiance par défaut) que par une programmation
    Planning radio (fenêtre ou 24/7) — les deux doivent boucler plutôt que
    s'arrêter en silence en fin de playlist."""
    from app.radio_manager import get_radio_manager

    playlist = db.query(RadioPlaylist).filter(RadioPlaylist.id == playlist_id).first()
    if not playlist:
        logger.warning(f"Cible programmée introuvable : playlist radio {playlist_id}")
        return
    sorted_items = sorted(playlist.items, key=lambda item: item.position)
    tracks = [_radio_track_dict(item.track) for item in sorted_items if item.track]
    if not tracks:
        logger.warning(f"Playlist radio {playlist_id} vide, rien à lancer")
        return
    await get_radio_manager().load_playlist(playlist.id, playlist.name, tracks, repeat="playlist")


async def _launch_radio_shuffle_all(db: Session) -> str | None:
    """Ambiance par défaut « de secours » : joue TOUTE la bibliothèque radio,
    mélangée et en boucle infinie. Utilisé quand AUCUNE RadioPlaylist n'est
    marquée `is_default`, pour ne jamais laisser la radio muette (réf. demande
    user : « éviter de devoir créer une playlist et de se retrouver sans
    musique »).

    Playlist VIRTUELLE (playlist_id=None, comme la commande `radio_shuffle_all`
    de routers/playback.py) : rien n'est persisté en base, la liste est
    recomposée à chaque lancement — elle reflète donc toujours l'état courant de
    la bibliothèque, sans playlist figée à resynchroniser à chaque import.
    Renvoie le nom lancé, ou None si la bibliothèque est vide."""
    from app.radio_manager import get_radio_manager

    tracks = [_radio_track_dict(t) for t in db.query(RadioTrack).all()]
    if not tracks:
        return None
    # shuffle=True + repeat="playlist" : aléatoire ET boucle infinie (deux
    # réglages indépendants côté RadioPlaybackManager), comme `radio_shuffle_all`.
    await get_radio_manager().load_playlist(
        None, "Toute la bibliothèque", tracks, shuffle=True, repeat="playlist",
    )
    return "Toute la bibliothèque"


async def autostart_default_radio_playlist() -> None:
    """Auto-démarrage au boot (réf. lot L7, D10) : si le canal radio est au
    repos et `radio_autostart_on_boot` est actif, charge la playlist
    d'ambiance par défaut. À appeler une fois au démarrage du service — si
    une lecture est déjà en cours (ex. relancée par une commande arrivée
    entre-temps), l'état n'est plus "idle" et cet appel ne fait rien.

    CORRECTIF historique (réf. « musiques qui switchent/se chevauchent en
    permanence », avant PortabiliteCrossPlatformX Lot 0) : avec 4 workers
    uvicorn, cette fonction était appelée par CHACUN à son propre démarrage,
    calculant chacun son propre tirage aléatoire — d'où des changements de
    piste qui semblaient incessants. Process unique depuis le Lot 0 (voir
    `docs/ARCHITECTURE.md` §2) : `main.py` n'appelle plus
    cette fonction qu'une seule fois, le problème ne peut plus se poser."""
    from app.config import settings as runtime_settings
    from app.radio_manager import get_radio_manager

    if not runtime_settings.radio_autostart_on_boot:
        return
    manager = get_radio_manager()
    if manager.state["state"] != "idle":
        return
    db = SessionLocal()
    try:
        default_playlist = db.query(RadioPlaylist).filter(RadioPlaylist.is_default == True).first()  # noqa: E712
        if default_playlist:
            logger.info(f"Auto-démarrage radio : playlist d'ambiance par défaut « {default_playlist.name} »")
            await _launch_radio_target(db, default_playlist.id)
        else:
            # Aucune playlist marquée par défaut : plutôt que de rester muet, on
            # démarre toute la bibliothèque en aléatoire/boucle (réf. demande
            # user). Overridable : dès qu'une playlist est marquée `is_default`,
            # la branche ci-dessus reprend la priorité au prochain démarrage.
            if await _launch_radio_shuffle_all(db):
                logger.info("Auto-démarrage radio : aucune playlist par défaut → toute la bibliothèque en aléatoire")
            else:
                logger.info("Auto-démarrage radio : bibliothèque vide, rien à lancer")
    finally:
        db.close()


async def _revert_radio_to_default(db: Session) -> None:
    """Fin de fenêtre radio (réf. lot L7, D9) : retour à la playlist d'ambiance
    par défaut, ou arrêt si aucune n'est définie."""
    from app.radio_manager import get_radio_manager

    default_playlist = db.query(RadioPlaylist).filter(RadioPlaylist.is_default == True).first()  # noqa: E712
    if default_playlist:
        await _launch_radio_target(db, default_playlist.id)
    else:
        # Même repli qu'à l'auto-boot : fin de fenêtre radio → toute la
        # bibliothèque en aléatoire plutôt que le silence ; stop seulement si la
        # bibliothèque est vide.
        if not await _launch_radio_shuffle_all(db):
            await get_radio_manager().stop()


async def _launch_target(
    db: Session, target_type: ScheduleTargetType, target_id: int, channel: str = "cable"
) -> None:
    """Lance la cible d'une programmation sur l'état de lecture de SON canal
    (réf. mission "tableaux de bord Câblé / Réseau" : un planning par canal,
    zéro interférence entre les deux lectures)."""
    if target_type == ScheduleTargetType.radio_playlist:
        # 3e canal radio (réf. lot L7), sous-système totalement indépendant
        # (D8) : aucune des règles de conflit câblé/réseau ci-dessous ne
        # s'applique — pas de mode coach, pas de "lecture manuelle en cours".
        await _launch_radio_target(db, target_id)
        return

    manager = get_playback_manager(channel)
    current = manager.snapshot()

    # F10.7 — priorité au mode audio coach : contrairement à F5.3, la
    # programmation n'est PAS prioritaire ici. Le coach anime un cours en
    # physique ; une programmation automatique ne doit surtout pas lui couper
    # le son. On n'appelle jamais _launch_target dans ce cas : la cible est
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
            f"Programmation ({target_type.value} {target_id}) reportée : mode audio coach actif (réf. F10.7)"
        )
        return

    # Réf. correctif "état interrompu incorrect pendant l'attente entre deux
    # vidéos d'une playlist" : `current_video` reste renseigné (celui qui
    # vient de se terminer) pendant `playlist_waiting`, comme le sont déjà
    # obligées de le vérifier PlaybackManager.play/pause/seek/report_position
    # — sans cette même exclusion ici, une programmation qui se déclenche
    # exactement dans cette fenêtre de quelques secondes croit qu'une "vidéo
    # manuelle" est active et sauvegarde une fausse interruption pointant sur
    # la vidéo déjà terminée (position ≈ sa fin, rien de sensé à reprendre).
    manual_video_active = current["current_video"] is not None and current["state"] not in (
        PlaybackStateEnum.waiting.value,
        PlaybackStateEnum.offline.value,
        PlaybackStateEnum.playlist_waiting.value,
    )

    # Règle de conflit RÉSEAU (retour utilisateur 2026-07-21) : sur ce canal,
    # un lancement manuel en cours gagne toujours — une programmation qui
    # arrive en même temps est simplement annulée, sans jamais interrompre la
    # lecture manuelle. Contraire à F5.3 (câblé) ci-dessous : le réseau sert
    # des appareils individuels lancés à la demande, pas le planning de la
    # salle physique, donc la priorité s'inverse.
    if channel == "network" and manual_video_active:
        logger.info(
            f"Programmation ({target_type.value} {target_id}) annulée : lecture manuelle en cours sur le "
            "canal réseau (priorité au manuel, réf. retour utilisateur 2026-07-21)"
        )
        return

    # F5.3 — règle de conflit CÂBLÉ : la programmation est prioritaire sur une
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
        thumb = video.thumbnail_path.split("/")[-1] if video.thumbnail_path else None
        await manager.load(
            video.id, video.title, video.duration_seconds, video.program, thumbnail_url=thumb,
            description=video.description, audio_channels=video.audio_channels, audio_codec=video.audio_codec,
            fps=video.fps, bitrate_kbps=video.bitrate_kbps, width=video.width, height=video.height,
            launch_type="schedule",
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
                "thumbnail_url": item.video.thumbnail_path.split("/")[-1] if item.video.thumbnail_path else None,
                "description": item.video.description,
                "audio_channels": item.video.audio_channels,
                "audio_codec": item.video.audio_codec,
                "fps": item.video.fps,
                "bitrate_kbps": item.video.bitrate_kbps,
                "width": item.video.width,
                "height": item.video.height,
            }
            for item in sorted_items
        ]
        await manager.load_playlist(playlist.id, playlist.name, items_data)


async def fire_schedule(schedule_id: int) -> None:
    """Callback APScheduler déclenché à l'heure d'une programmation.

    Avant PortabiliteCrossPlatformX Lot 0, un verrou distribué Redis
    dédoublonnait ce déclenchement entre les 4 workers uvicorn, chacun ayant
    son propre AsyncIOScheduler armé sur la même règle cron. Process unique
    depuis ce lot : un seul AsyncIOScheduler existe, plus de doublon possible
    par construction (voir `docs/ARCHITECTURE.md` §2)."""
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
            # Recalé de MISFIRE_GRACE_SECONDS avant de prendre le jour civil
            # (réf. correctif "recherche d'exception en course avec la marge
            # de tolérance de retard") : ce callback peut s'exécuter jusqu'à
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

        await _launch_target(db, target_type, target_id, schedule.channel or "cable")
    finally:
        db.close()


async def fire_schedule_end(schedule_id: int) -> None:
    """Callback APScheduler déclenché à la FIN d'une fenêtre radio (réf. lot
    L7, D9/A1) : retour à la playlist d'ambiance par défaut. N'existe que pour
    les programmations radio récurrentes avec `end_time` (pas de mode 24/7,
    pas de programmation ponctuelle — cf. _sync_end_job)."""
    db = SessionLocal()
    try:
        schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        if not schedule or not schedule.active:
            return
        await _revert_radio_to_default(db)
    finally:
        db.close()


def sync_schedule_job(schedule: Schedule) -> None:
    """(Ré)enregistre le job APScheduler d'une programmation, ou le retire si
    elle est inactive/déjà passée. Appelé après chaque création/mise à jour."""
    if _scheduler is None:
        logger.debug(f"Scheduler non démarré : synchronisation ignorée ({_job_id(schedule.id)})")
        return

    job_id = _job_id(schedule.id)

    if not schedule.active:
        remove_schedule_job(schedule.id)
        return

    try:
        if schedule.schedule_type == ScheduleType.once:
            run_at = ensure_utc(schedule.run_at) if schedule.run_at else None
            if not run_at or run_at <= datetime.now(timezone.utc):
                remove_schedule_job(schedule.id)
                return
            trigger = DateTrigger(run_date=run_at)
        else:
            trigger = _build_cron_trigger(schedule)
    except Exception as e:
        # Réf. correctif "json.loads non protégé sur une ligne malformée peut
        # interrompre toute la boucle de resynchronisation au démarrage" :
        # start_scheduler() appelle sync_schedule_job() pour CHAQUE
        # programmation active dans une simple boucle for — une seule ligne
        # corrompue (recurrence_rule invalide après une édition manuelle en
        # base, par ex.) levait une exception qui remontait jusqu'à
        # start_scheduler(), empêchant TOUTES les programmations suivantes de
        # la boucle d'être rechargées, et donc le démarrage même du backend
        # (appelé depuis le lifespan FastAPI, jamais protégé). On ignore
        # cette seule programmation, en le signalant clairement.
        logger.error(f"Programmation {schedule.id} ignorée : règle de récurrence invalide ({e})")
        remove_schedule_job(schedule.id)
        return

    _scheduler.add_job(
        fire_schedule,
        trigger=trigger,
        id=job_id,
        args=[schedule.id],
        replace_existing=True,
        # Tolère un redémarrage court du backend à cheval sur l'heure de
        # déclenchement (le mini PC peut redémarrer) sans pour autant rejouer
        # une programmation manquée depuis des heures.
        misfire_grace_time=MISFIRE_GRACE_SECONDS,
    )
    _sync_end_job(schedule)


def _sync_end_job(schedule: Schedule) -> None:
    """(Ré)enregistre le job de FIN de fenêtre radio (réf. lot L7), ou le
    retire s'il ne s'applique pas. Portée volontairement restreinte aux
    programmations radio RÉCURRENTES : une fenêtre ponctuelle (schedule_type
    "once") ne revient pas automatiquement au défaut — limitation assumée
    pour ce lot, le cas d'usage principal (programmation hebdomadaire d'une
    salle) est récurrent. Fenêtres à cheval sur minuit non prises en charge
    (cf. routers/schedule.py::_validate_and_normalize)."""
    if _scheduler is None:
        return
    applicable = (
        schedule.active
        and schedule.target_type == ScheduleTargetType.radio_playlist
        and schedule.schedule_type == ScheduleType.recurring
    )
    if not applicable:
        remove_end_schedule_job(schedule.id)
        return

    try:
        rule = json.loads(schedule.recurrence_rule)
    except (TypeError, ValueError):
        remove_end_schedule_job(schedule.id)
        return

    end_time = rule.get("end_time")
    if rule.get("mode") == "24_7" or not end_time:
        remove_end_schedule_job(schedule.id)
        return

    days = ",".join(str(d) for d in rule["days_of_week"])
    hour, minute = (int(part) for part in end_time.split(":"))
    trigger = CronTrigger(day_of_week=days, hour=hour, minute=minute, timezone=LOCAL_TZ)
    _scheduler.add_job(
        fire_schedule_end,
        trigger=trigger,
        id=_job_id_end(schedule.id),
        args=[schedule.id],
        replace_existing=True,
        misfire_grace_time=MISFIRE_GRACE_SECONDS,
    )


def remove_end_schedule_job(schedule_id: int) -> None:
    if _scheduler is None:
        return
    if _scheduler.get_job(_job_id_end(schedule_id)):
        _scheduler.remove_job(_job_id_end(schedule_id))


def remove_schedule_job(schedule_id: int) -> None:
    if _scheduler is None:
        return
    if _scheduler.get_job(_job_id(schedule_id)):
        _scheduler.remove_job(_job_id(schedule_id))
    remove_end_schedule_job(schedule_id)


def _periodic_hardware_snapshot() -> None:
    db = SessionLocal()
    try:
        record_hardware_snapshot(db)
    except Exception as e:
        logger.warning(f"Erreur enregistrement snapshot télémétrie : {e}")
    finally:
        db.close()


_AUTO_UPDATE_JOB_ID = "auto_update_check"


async def _run_auto_update_check() -> None:
    """Job planifié (Réglages → Mise à jour automatique) — `AsyncIOScheduler`
    exécute directement les callables `async def` sur sa propre boucle
    asyncio (même patron que `fire_schedule`/`_launch_target` plus haut
    dans ce fichier), aucun pont thread-safe n'est donc nécessaire ici.
    Import différé de `run_scheduled_update_if_available` : évite d'avoir à
    établir un ordre d'import entre `scheduler_manager` (importé tôt par
    `main.py`) et `routers.updates` — même précaution que `from app.models
    import Setting` un peu plus bas dans ce fichier."""
    from app.routers.updates import run_scheduled_update_if_available

    db = SessionLocal()
    try:
        await run_scheduled_update_if_available(db)
    except Exception as e:
        logger.error(f"Erreur lors de la vérification automatique de mise à jour : {e}")
    finally:
        db.close()


def sync_auto_update_job(enabled: bool, time_str: str) -> None:
    """(Ré)enregistre ou retire le job planifié de mise à jour automatique.
    Appelé au démarrage (lecture du réglage persisté) et à chaque
    modification du réglage depuis Réglages (cf. routers/settings.py)."""
    if _scheduler is None:
        logger.debug("Scheduler non démarré : synchronisation de la mise à jour automatique ignorée")
        return
    if not enabled:
        remove_auto_update_job()
        return
    try:
        hour, minute = (int(part) for part in time_str.split(":"))
    except (ValueError, AttributeError):
        logger.warning(f"Heure de mise à jour automatique invalide ({time_str!r}) — job non programmé")
        return
    _scheduler.add_job(
        _run_auto_update_check,
        trigger=CronTrigger(hour=hour, minute=minute, timezone=LOCAL_TZ),
        id=_AUTO_UPDATE_JOB_ID,
        replace_existing=True,
        misfire_grace_time=MISFIRE_GRACE_SECONDS,
    )
    logger.info(f"Mise à jour automatique planifiée chaque jour à {hour:02d}:{minute:02d}")


def remove_auto_update_job() -> None:
    if _scheduler is None:
        return
    if _scheduler.get_job(_AUTO_UPDATE_JOB_ID):
        _scheduler.remove_job(_AUTO_UPDATE_JOB_ID)


def _periodic_purge_logs() -> None:
    db = SessionLocal()
    try:
        row = db.query(Setting).filter(Setting.key == "logs_retention_days").first()
        retention = int(row.value) if row and row.value and row.value.isdigit() else 7
        purged = purge_expired_logs_and_metrics(db, retention)
        logger.info(f"Purge automatique effectuée : {purged}")
    except Exception as e:
        logger.warning(f"Erreur purge automatique logs : {e}")
    finally:
        db.close()


def start_scheduler() -> None:
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone=LOCAL_TZ)
    _scheduler.start()

    # Relevé télémétrie périodique (toutes les 60s)
    _scheduler.add_job(
        _periodic_hardware_snapshot,
        trigger="interval",
        seconds=60,
        id="hardware_telemetry_snapshot",
        replace_existing=True,
    )
    # Purge automatique quotidienne des logs et métriques (chaque jour à 03:00)
    _scheduler.add_job(
        _periodic_purge_logs,
        trigger=CronTrigger(hour=3, minute=0, timezone=LOCAL_TZ),
        id="purge_expired_logs",
        replace_existing=True,
    )

    db = SessionLocal()
    try:
        active_schedules = db.query(Schedule).filter(Schedule.active == True).all()  # noqa: E712
        for schedule in active_schedules:
            sync_schedule_job(schedule)
        logger.info(f"Scheduler démarré, {len(active_schedules)} programmation(s) active(s) rechargée(s)")
        # Snapshot initial
        record_hardware_snapshot(db)

        auto_update_row = db.query(Setting).filter(Setting.key == "auto_update_enabled").first()
        auto_update_time_row = db.query(Setting).filter(Setting.key == "auto_update_time").first()
        sync_auto_update_job(
            enabled=bool(auto_update_row and auto_update_row.value == "true"),
            time_str=(auto_update_time_row.value if auto_update_time_row else "03:00"),
        )
    finally:
        db.close()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
