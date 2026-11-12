"""Mise à jour automatique planifiée, jamais pendant une lecture."""
import logging
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from app.utils.activity_log import log_activity
from app.utils.deployment import (
    get_deployment_profile,
    get_profile_handler,
)
from app.updates.orchestrator import (
    is_running,
    run_update_pipeline,
)
from app.updates.android import refuse_android_downgrade
from app.updates.assets import resolve_asset
from app.updates.github import fetch_release_for_channel
from app.updates.local_build import get_local_version_info, get_update_channel
from app.updates.versions import evaluate_update


logger = logging.getLogger(__name__)


def something_is_playing() -> bool:
    """Vrai si un canal vidéo ou une sortie radio joue : une mise à jour planifiée ne coupe jamais une séance."""
    from app.playback.constants import PlaybackStateEnum
    from app.playback.manager import get_all_playback_managers
    from app.radio_manager import get_all_radio_managers

    try:
        playback, radios = get_all_playback_managers(), get_all_radio_managers()
    except RuntimeError:  # moteurs pas encore initialisés : rien ne peut jouer
        return False
    for manager in playback.values():
        state = manager.state.get("state")
        if state in (PlaybackStateEnum.playing.value, PlaybackStateEnum.coach_mode.value) or manager.state.get("audio_playing"):
            return True
    return any(radio.state.get("state") in ("playing", "announcing") for radio in radios.values())


async def run_scheduled_update_if_available(db: Session) -> None:
    """Appelée par `scheduling` au créneau planifié (Réglages → Mise
    à jour automatique). Vérifie d'abord qu'une mise à jour existe RÉELLEMENT
    avant de déclencher quoi que ce soit — contrairement au bouton manuel,
    personne ne clique ici, donc pas de retour utilisateur immédiat en cas
    de "rien à faire" à gérer, juste un silence normal dans les journaux.
    Un retour en arrière (Bêta/Canary -> Stable plus ancienne) n'est JAMAIS
    déclenché sans clic : la planification n'installe que des mises à jour
    montantes."""
    handler = get_profile_handler()
    if not handler.can_schedule_auto_apply() or is_running():
        return
    if something_is_playing():
        logger.info("Mise à jour planifiée reportée : une lecture est en cours.")
        return
    channel = get_update_channel(db)
    release_data, _ = await fetch_release_for_channel(channel, force=True)
    if not release_data:
        return
    # Jusqu'à quatre appels `git` synchrones : hors de la boucle d'évènements.
    local_info = await run_in_threadpool(get_local_version_info)
    profile = get_deployment_profile()
    evaluation = await refuse_android_downgrade(
        profile, local_info, release_data, evaluate_update(channel, local_info, release_data)
    )
    if not evaluation["has_update"] or evaluation["is_downgrade"]:
        return

    target_tag = release_data.get("tag_name") or None
    asset = resolve_asset(profile, release_data, handler.asset_variant())
    if not handler.supports_git_versioning() and not (asset["download_url"] and asset["asset_digest"]):
        logger.warning("Mise à jour planifiée ignorée : paquet ou empreinte introuvable pour ce profil dans la release.")
        return
    log_activity(db, "update_apply", f"Mise à jour planifiée déclenchée (cible : {target_tag or 'branche courante'})")
    await run_update_pipeline(target_tag, asset["download_url"], asset["asset_digest"], "scheduled")
