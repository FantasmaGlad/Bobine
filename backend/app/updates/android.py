"""Android interdit un retour à une version plus ancienne sans désinstaller l'application."""
import asyncio
from typing import Any
from app.updates.github import commit_distance_blocking
from app.updates.versions import release_target_ref


ANDROID_DOWNGRADE_MESSAGE = (
    "Cette version est plus ancienne que celle installée : Android interdit tout retour "
    "en arrière sans désinstaller l'application, ce qui effacerait ses données. "
    "Patientez jusqu'à la prochaine version de ce canal."
)


async def refuse_android_downgrade(
    profile: str, local: dict[str, Any], release_data: dict[str, Any], evaluation: dict[str, Any]
) -> dict[str, Any]:
    """Android refuse d'installer un APK dont le versionCode est inférieur à celui installé (`UpdateManager.validatePackage`), mais seulement APRÈS le téléchargement de 46 à 69 Mo : passer de Canary (la plus récente) à Bêta ou Stable s'annonçait donc comme une mise à jour."""
    if profile != "android" or not evaluation["has_update"]:
        return evaluation
    local_commit, ref = local.get("current_commit") or "", release_target_ref(release_data)
    if local_commit in ("", "unknown") or not ref:
        return evaluation
    loop = asyncio.get_running_loop()
    distance = await loop.run_in_executor(None, commit_distance_blocking, local_commit, ref)
    if distance is None or distance >= 0:
        return evaluation
    return {**evaluation, "has_update": False, "is_downgrade": True, "downgrade_blocked": True}
