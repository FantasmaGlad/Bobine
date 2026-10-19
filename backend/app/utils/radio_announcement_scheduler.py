"""Moteur des règles temporelles de rappels : « toutes les X minutes » et « à heures fixes ». La règle
« toutes les N musiques » est vérifiée ailleurs, à chaque fin de piste
 — elle n'a rien de temporel.

Boucle asyncio légère (même patron que RadioPlaybackManager._position_broadcast_loop)
plutôt qu'APScheduler : les règles sont peu nombreuses, vérifiées à intervalle
grossier (10 s, largement suffisant pour une granularité à la minute), et
n'ont pas besoin de jobs persistés/replanifiés comme le Planning.
"""
import asyncio
import json
import logging
import time
from datetime import datetime

from sqlalchemy import func
from tzlocal import get_localzone

from app.database import SessionLocal
from app.models import RadioAnnouncement, RadioAnnouncementRule, RadioAnnouncementRuleType
from app.radio_manager import rule_targets_output

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 10.0
LOCAL_TZ = get_localzone()

_task: asyncio.Task | None = None
# Dernier déclenchement de chaque règle « toutes les X minutes » (monotonic,
# insensible aux sauts d'horloge) — initialisé au moment où la règle est VUE
# pour la première fois plutôt qu'à 0, pour ne pas déclencher immédiatement
# toutes les règles existantes au redémarrage du service.
# Clé = (règle, sortie radio) : une règle « les deux sorties » déclenche
# indépendamment sur chaque moteur.
_last_minutes_fire: dict[tuple[int, str], float] = {}
# Dernière minute déclenchée pour chaque règle « heures fixes » (clé
# "YYYY-MM-DD HH:MM"), pour ne tirer qu'une fois par horaire programmé même
# si la boucle repasse plusieurs fois dans la même minute.
_last_fixed_fire: dict[tuple[int, str], str] = {}


def start_radio_announcement_scheduler() -> None:
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_loop())


async def stop_radio_announcement_scheduler() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None


async def _loop() -> None:
    try:
        while True:
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)
            try:
                await _check_rules()
            except Exception as e:
                logger.error(f"Vérification des règles de rappels échouée : {e}", exc_info=True)
    except asyncio.CancelledError:
        pass


async def _check_rules() -> None:
    from app.radio_manager import get_all_radio_managers

    # Chaque sortie radio a son propre moteur : ses règles (cible = cette sortie
    # ou « les deux ») sont évaluées et déclenchées indépendamment.
    for manager in get_all_radio_managers().values():
        await _check_rules_for(manager)


async def _check_rules_for(manager) -> None:
    # Un rappel est déjà en cours (quel que soit son mode) : ne pas en
    # empiler un second par-dessus.
    if manager.state.get("current_announcement"):
        return

    db = SessionLocal()
    try:
        rules = [
            rule
            for rule in (
                db.query(RadioAnnouncementRule)
                .filter(
                    RadioAnnouncementRule.enabled == True,  # noqa: E712
                    RadioAnnouncementRule.rule_type.in_(
                        [RadioAnnouncementRuleType.every_x_minutes, RadioAnnouncementRuleType.fixed_times]
                    ),
                )
                .all()
            )
            if rule_targets_output(rule.target, manager.channel)
        ]
        if not rules:
            return

        now_monotonic = time.monotonic()
        now_local = datetime.now(LOCAL_TZ)
        due_rule: RadioAnnouncementRule | None = None

        for rule in rules:
            fire_key = (rule.id, manager.channel)
            if rule.rule_type == RadioAnnouncementRuleType.every_x_minutes:
                last = _last_minutes_fire.setdefault(fire_key, now_monotonic)
                if now_monotonic - last >= (rule.interval_minutes or 0) * 60:
                    _last_minutes_fire[fire_key] = now_monotonic
                    due_rule = rule
                    break
            elif rule.rule_type == RadioAnnouncementRuleType.fixed_times:
                times = json.loads(rule.times_of_day) if rule.times_of_day else []
                hhmm = now_local.strftime("%H:%M")
                minute_key = f"{now_local.date()} {hhmm}"
                if hhmm in times and _last_fixed_fire.get(fire_key) != minute_key:
                    _last_fixed_fire[fire_key] = minute_key
                    due_rule = rule
                    break

        if due_rule is None:
            return

        announcement = (
            db.query(RadioAnnouncement)
            .filter(RadioAnnouncement.enabled == True)  # noqa: E712
            .order_by(func.random())
            .first()
        )
        if not announcement:
            return
        await manager.play_announcement(
            {"id": announcement.id, "description": announcement.description}, mode="duck",
        )
    finally:
        db.close()
