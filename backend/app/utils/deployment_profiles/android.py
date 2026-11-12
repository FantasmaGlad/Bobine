"""Handler du profil `android` (app Chaquopy, voir docs/ARCHITECTURE.md)."""

import logging
import os
from typing import Callable

from app.utils.deployment import ProfileHandler, UpdateUnsupported
from app.utils import tor_proxy
from app.utils.tor_proxy import TorSession

logger = logging.getLogger(__name__)

_NOOP_REPORT: Callable[..., None] = lambda *a, **k: None  # noqa: E731


def _get_android_context():
    from com.chaquo.python import Python
    return Python.getPlatform().getApplication()


class AndroidHandler(ProfileHandler):
    profile = "android"

    async_completion = True
    _store_managed: bool | None = None

    def asset_variant(self) -> str | None:
        """"tv" si l'application tourne sous le flavor Android TV (`applicationId` = `com.bobine.app.tv`, cf."""
        try:
            return "tv" if str(_get_android_context().getPackageName()).endswith(".tv") else "mobile"
        except Exception:
            logger.warning("Impossible de lire le nom de paquet Android — APK téléphone/tablette supposé.", exc_info=True)
            return "mobile"

    def restart_services(self) -> None:
        logger.info(
            "Arrêt du process pour redémarrage (Android : relance non garantie, "
            "START_STICKY du ForegroundService seulement)."
        )
        os._exit(0)

    def restart_is_guaranteed(self) -> bool:
        return False

    def can_self_uninstall(self) -> bool:
        return True

    def start_uninstall(self) -> None:
        try:
            from java import jclass
            Uri = jclass("android.net.Uri")
            Intent = jclass("android.content.Intent")
            context = _get_android_context()
            intent = Intent(Intent.ACTION_DELETE)
            intent.setData(Uri.parse(f"package:{context.getPackageName()}"))
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(intent)
            logger.info("Dialogue système de désinstallation Android ouvert via ACTION_DELETE.")
        except Exception:
            logger.exception("Échec de l'ouverture du dialogue de désinstallation Android")
            raise

    def uninstall_instructions(self) -> str:
        return (
            "Pour désinstaller Bobine, utilisez la gestion des applications d'Android : "
            "appui long sur l'icône Bobine puis Désinstaller, ou Paramètres > Applications > Bobine > Désinstaller."
        )

    def supports_git_versioning(self) -> bool:
        return False

    def is_store_managed(self) -> bool:
        """Vrai pour le build Google Play."""
        if self._store_managed is not None:
            return self._store_managed
        try:
            from java import jclass
            self._store_managed = bool(jclass("com.bobine.app.BuildConfig").STORE_BUILD)
        except Exception:
            return False
        return self._store_managed

    @staticmethod
    def _store_call(method: str) -> dict:
        import json

        from java import jclass

        raw = getattr(jclass("com.bobine.app.StoreUpdates").INSTANCE, method)(_get_android_context())
        data = json.loads(str(raw))
        return data if isinstance(data, dict) else {"state": "unavailable"}

    def store_update_status(self) -> dict:
        if not self.is_store_managed():
            return {"state": "unavailable"}
        try:
            return self._store_call("check")
        except Exception:
            logger.warning("Lecture de l'état de mise à jour Google Play impossible", exc_info=True)
            return {"state": "unavailable"}

    def _store_action(self, method: str) -> dict:
        if not self.is_store_managed():
            raise UpdateUnsupported("Cette installation ne vient pas de Google Play.")
        try:
            result = self._store_call(method)
        except Exception as exc:
            logger.warning("Action Google Play %s impossible", method, exc_info=True)
            raise UpdateUnsupported("Google Play n'est pas joignable depuis cette application.") from exc
        if result.get("error"):
            raise UpdateUnsupported(str(result.get("message") or "Opération refusée par Google Play."))
        return result

    def store_update_start(self) -> dict:
        return self._store_action("start")

    def store_update_complete(self) -> dict:
        return self._store_action("complete")

    def store_open_listing(self) -> dict:
        return self._store_action("openListing")

    def can_auto_apply(self) -> bool:
        return not self.is_store_managed()

    def tries_port80_redirect(self) -> bool:
        return False

    def can_schedule_auto_apply(self) -> bool:
        return False

    def apply_update(
        self,
        target_tag: str | None = None,
        download_url: str | None = None,
        asset_digest: str | None = None,
        report: Callable[..., None] | None = None,
    ) -> None:
        report = report or _NOOP_REPORT
        if not download_url:
            raise UpdateUnsupported(
                "Aucun lien de téléchargement d'APK disponible pour la mise à jour."
            )
        if not asset_digest:
            raise UpdateUnsupported(
                "Empreinte SHA-256 indisponible pour l'APK — installation annulée par précaution."
            )
        report("downloading", percent=0, message="Téléchargement de l'APK sur l'appareil…")
        try:
            from java import jclass
            context = _get_android_context()
            update_mgr = jclass("com.bobine.app.UpdateManager")
            socks_proxy = TorSession().address if tor_proxy.is_enabled() else None
            update_mgr.INSTANCE.downloadAndInstall(context, download_url, asset_digest, socks_proxy)
        except Exception as exc:
            logger.exception("Échec du déclenchement de la mise à jour Android via UpdateManager")
            raise UpdateUnsupported(f"Impossible de déclencher la mise à jour Android : {exc}") from exc
