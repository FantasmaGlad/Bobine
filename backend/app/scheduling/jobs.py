"""Tâches du planificateur : programmations, fins de fenêtre radio, mise à jour automatique, instantanés et purge."""

import json
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from app.database import SessionLocal
from app.hardware.telemetry import purge_expired_logs_and_metrics, record_hardware_snapshot
from app.models import (
    Schedule,
    ScheduleTargetType,
    ScheduleType,
    Setting,
)

from .launch import MISFIRE_GRACE_SECONDS, fire_schedule, fire_schedule_end
from .occurrences import LOCAL_TZ, _build_cron_trigger, ensure_utc

logger = logging.getLogger(__name__)


_scheduler: AsyncIOScheduler | None = None


def _job_id(schedule_id: int) -> str:
    return f"schedule-{schedule_id}"


def _job_id_end(schedule_id: int) -> str:
    return f"schedule-{schedule_id}-end"


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
    """(Ré)enregistre le job de FIN de fenêtre radio, ou le
    retire s'il ne s'applique pas. Portée volontairement restreinte aux
    programmations radio RÉCURRENTES : une fenêtre ponctuelle (schedule_type
    "once") ne revient pas automatiquement au défaut — limitation assumée
    pour ce lot, le cas d'usage principal (programmation hebdomadaire d'une
    salle) est récurrent. Fenêtres à cheval sur minuit non prises en charge
    (cf. api/routes/schedule.py::_validate_and_normalize)."""
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
        logger.warning("Planning %s : règle de récurrence illisible, aucune heure de fin programmée", schedule.id)
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
    from app.api.routes.updates import run_scheduled_update_if_available

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
    modification du réglage depuis Réglages (cf. api/routes/settings/)."""
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


def scheduler_running() -> bool:
    """Vrai quand le planificateur tourne : sans lui, aucune programmation ne se déclenche."""
    return _scheduler is not None and _scheduler.running


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
