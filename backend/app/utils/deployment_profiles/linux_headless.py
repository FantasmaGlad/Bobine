"""Handler du profil `linux-headless` (l'appliance Debian existante,
`install.sh`) : `sudo systemctl restart`, enveloppe de désinstallation
`systemd-run`, mise à jour via `git checkout`/`git pull`."""

import logging
import subprocess
from pathlib import Path
from typing import Callable

from app.utils.deployment import (
    BACKEND_SERVICE_UNIT,
    KIOSK_SERVICE_UNIT,
    ProfileHandler,
)
from app.utils.update_orchestrator import run_checked

logger = logging.getLogger(__name__)

UNINSTALL_WRAPPER = Path("/usr/local/sbin/bobine-uninstall")

_NOOP_REPORT: Callable[..., None] = lambda *a, **k: None  # noqa: E731


def _repo_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent


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

    def _restart_services_checked(self, report: Callable[..., None]) -> None:
        """Variante utilisée par `apply_update()` : contrairement à
        `restart_services()` (fire-and-forget, adaptée au bouton
        "Réinitialiser" appelé depuis une requête HTTP qui doit répondre
        avant que son propre process ne soit redémarré), le pipeline de
        mise à jour tourne déjà dans un thread détaché de la requête HTTP
        — rien n'empêche ici de vérifier réellement que chaque service
        redevient actif, et de le signaler explicitement en cas d'échec au
        lieu d'un `... || true` qui masque tout problème (sudoers cassé,
        unité désactivée, etc.)."""
        report("restarting", message="Redémarrage des services…")
        for unit in (KIOSK_SERVICE_UNIT, BACKEND_SERVICE_UNIT):
            try:
                run_checked(["sudo", "systemctl", "restart", unit], timeout=20)
            except Exception as e:
                raise RuntimeError(f"Échec du redémarrage de {unit} : {e}") from e
            try:
                is_active = run_checked(["systemctl", "is-active", unit], timeout=10)
                if is_active.stdout.strip() != "active":
                    raise RuntimeError(f"{unit} redémarré mais n'est pas actif ({is_active.stdout.strip()})")
            except Exception as e:
                raise RuntimeError(f"Échec de vérification de {unit} après redémarrage : {e}") from e

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

    def can_schedule_auto_apply(self) -> bool:
        # Cible de production principale, checkout + réinstallation des
        # dépendances + reconstruction du frontend + vérification du
        # redémarrage — le chemin le plus éprouvé, éligible en premier à
        # la planification automatique.
        return True

    def apply_update(
        self,
        target_tag: str | None = None,
        download_url: str | None = None,
        asset_digest: str | None = None,
        report: Callable[..., None] | None = None,
    ) -> None:
        report = report or _NOOP_REPORT
        repo_dir = _repo_dir()

        report("checking", message="Récupération de la nouvelle version…")
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
            run_checked(["git", "fetch", "--tags", "--force"], cwd=repo_dir, timeout=45)
            # `check=True` implicite via `run_checked` : contrairement à
            # l'ancien code, un checkout qui échoue (arbre de travail sale,
            # permissions, réseau coupé en cours de fetch) lève désormais
            # une exception AVANT tout redémarrage de service — évite de
            # redémarrer "pour rien" sur l'ancienne version en laissant
            # croire à une mise à jour qui n'a jamais eu lieu.
            run_checked(["git", "checkout", target_tag], cwd=repo_dir, timeout=45)
            logger.info(f"git checkout {target_tag} effectué avec succès.")
        else:
            # Repli historique (aucun tag résolu côté appelant) : suit la
            # branche courante par avance rapide uniquement.
            run_checked(["git", "pull", "--ff-only"], cwd=repo_dir, timeout=45)
            logger.info("git pull --ff-only effectué avec succès.")

        # Réinstallation des dépendances Python et reconstruction du
        # frontend : `frontend/out` (servi statiquement par le backend)
        # est gitignoré et NE fait donc jamais partie d'un `git checkout`
        # — sans cette étape, l'interface servie restait celle d'AVANT la
        # mise à jour même après un `git checkout` réussi. `pip install`
        # est réexécuté systématiquement (coût de quelques secondes tout
        # au plus si `requirements.txt` n'a pas changé, pip ne réinstalle
        # alors rien) plutôt que de tenter une détection de changement
        # fragile.
        venv_pip = repo_dir / "backend" / ".venv" / "bin" / "pip"
        if venv_pip.exists():
            report("installing", message="Mise à jour des dépendances serveur…")
            run_checked(
                [str(venv_pip), "install", "-q", "-r", str(repo_dir / "backend" / "requirements.txt")],
                timeout=180,
            )
        else:
            logger.warning(f"Environnement virtuel introuvable ({venv_pip}) — étape pip ignorée.")

        report("installing", message="Reconstruction de l'interface…")
        run_checked(["npm", "ci", "--no-audit", "--no-fund"], cwd=repo_dir / "frontend", timeout=300)
        run_checked(["npm", "run", "build"], cwd=repo_dir / "frontend", timeout=300)

        self._restart_services_checked(report)
