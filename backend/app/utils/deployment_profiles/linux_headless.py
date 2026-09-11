"""Handler du profil `linux-headless` (l'appliance Debian existante,
`install.sh`) — comportement inchangé par rapport à ce qui existait avant
PortabiliteCrossPlatformX : `sudo systemctl restart`, enveloppe de
désinstallation `systemd-run`, mise à jour via `git pull`."""

import logging
import subprocess
from pathlib import Path

from app.utils.deployment import (
    BACKEND_SERVICE_UNIT,
    KIOSK_SERVICE_UNIT,
    ProfileHandler,
)

logger = logging.getLogger(__name__)

UNINSTALL_WRAPPER = Path("/usr/local/sbin/bobine-uninstall")


class LinuxHeadlessHandler(ProfileHandler):
    profile = "linux-headless"

    def restart_services(self) -> None:
        # Redémarrage asynchrone et détaché (réf. retour utilisateur "relancer
        # le service lors de la mise à jour sans intervention manuelle") :
        # Exécuter `systemctl restart bobine-backend` de façon synchrone dans
        # le processus Python coupe le process avant la fin de la requête HTTP
        # et peut bloquer. L'enveloppe détachée (start_new_session=True) avec
        # un délai de 1 seconde permet à l'API de répondre 200 OK et de clore
        # ses connexions avant le rechargement effectif des services systemd.
        cmd = (
            "sleep 1 && "
            "(sudo /usr/bin/systemctl restart bobine-kiosk.service || sudo systemctl restart bobine-kiosk.service || true) && "
            "(sudo /usr/bin/systemctl restart bobine-backend.service || sudo systemctl restart bobine-backend.service || true)"
        )
        try:
            subprocess.Popen(["sh", "-c", cmd], start_new_session=True)
            logger.info("Redémarrage asynchrone des services programmé (bobine-kiosk, bobine-backend)")
        except Exception as e:
            logger.error(f"Échec de programmation du redémarrage : {e}")

    def can_self_uninstall(self) -> bool:
        return True

    def start_uninstall(self) -> None:
        subprocess.Popen(["sudo", str(UNINSTALL_WRAPPER)], start_new_session=True)
        logger.info("Désinstallation déclenchée (enveloppe systemd-run détachée).")

    def uninstall_instructions(self) -> str:
        # Non utilisé : can_self_uninstall() est True pour ce profil.
        return ""

    def supports_git_versioning(self) -> bool:
        return True

    def apply_update(self, target_tag: str | None = None, download_url: str | None = None) -> None:
        repo_dir = Path(__file__).resolve().parent.parent.parent.parent
        if target_tag:
            # Épingle le checkout sur le tag ciblé plutôt qu'un `git pull`
            # aveugle sur la branche courante (réf. mission "canal Stable/
            # Bêta") : seule façon de supporter un vrai retour en arrière
            # (ex. Bêta -> dernière Stable, un tag ANTÉRIEUR que `--ff-only`
            # refuserait). HEAD détaché assumé — cette machine est une cible
            # de déploiement, jamais un poste de développement git sur ce
            # dépôt. --force : le canal Bêta est un tag UNIQUE et mobile
            # ("beta", jamais un nouveau tag par itération) — sans --force,
            # un fetch classique refuse de mettre à jour un tag local dont
            # la cible distante a bougé depuis le dernier fetch.
            subprocess.run(["git", "fetch", "--tags", "--force"], cwd=repo_dir, capture_output=True, text=True, timeout=45, check=True)
            res = subprocess.run(
                ["git", "checkout", target_tag],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=45,
            )
            logger.info(f"git checkout {target_tag} résultat : {res.stdout or res.stderr}")
        else:
            # Repli historique (aucun tag résolu côté appelant) : suit la
            # branche courante par avance rapide uniquement.
            res = subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=45,
            )
            logger.info(f"git pull résultat : {res.stdout}")
        self.restart_services()
