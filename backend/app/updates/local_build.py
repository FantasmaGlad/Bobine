"""Version, tag, commit et canal du build installé."""
import re
import subprocess
from pathlib import Path
from typing import Any
from sqlalchemy.orm import Session
from app.models import Setting
from app.utils.deployment import (
    get_profile_handler,
    resolve_update_channel,
)
from app import release_channel
from app.utils.version import (
    get_app_commit,
    get_app_tag,
    get_app_version,
)
from app.updates.versions import STABLE_TAG_RE, parse_version


def get_update_channel(db: Session) -> str:
    row = db.query(Setting).filter(Setting.key == "update_channel").first()
    # Réglage absent ou invalide : le canal par lequel l'application a été installée.
    return resolve_update_channel(row.value if row else None).effective


def git_lines(args: list[str], repo_dir: Path) -> list[str]:
    """Sortie ligne par ligne d'une commande git en lecture seule, liste vide
    en cas d'échec — jamais d'exception : ce code sert à de l'AFFICHAGE."""
    try:
        res = subprocess.run(
            ["git", *args], cwd=repo_dir, capture_output=True, text=True, timeout=3, check=True,
        )
        return [line.strip() for line in res.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def rolling_build_info(channel: release_channel.ReleaseChannel, commit: str) -> dict[str, Any]:
    """Construit le résultat de `get_local_version_info()` pour un build posé
    sur le tag mobile (rolling) d'un canal — factorisé pour servir tous les
    canaux rolling du registre sans dupliquer la logique de version affichée."""
    base = get_app_version().lstrip("vV")
    version = f"V{base}" if "-" in base else f"V{base}-{channel.version_suffix}"
    return {
        "current_version": version, "current_tag": channel.release_tag, "current_commit": commit,
        "local_rolling_channel": channel.id,
    }


def get_local_version_info() -> dict[str, Any]:
    """Détermine la version, le commit et la NATURE (stable/bêta/canary) du
    build local.

    N'exécute `git` que sur les profils dont le dossier d'installation est
    un vrai checkout (aujourd'hui : l'appliance headless seule) — un paquet
    figé (`.exe`, `.app`, `.deb`) n'a pas de `.git` et ces appels
    échoueraient systématiquement en pure perte.

    `local_rolling_channel` (id d'un canal rolling du registre, ou None si Stable) distingue
    un build non-Stable d'une Stable de même numéro de base : sans ça, un
    utilisateur Bêta/Canary qui repasse sur le canal Stable ne se voyait
    JAMAIS proposer la Stable (même base, ou base inférieure), contrairement
    à la promesse affichée dans Réglages."""
    commit = get_app_commit()
    tag = get_app_tag()

    if not get_profile_handler().supports_git_versioning():
        return {
            "current_version": tag, "current_tag": tag, "current_commit": commit,
            "local_rolling_channel": release_channel.rolling_channel_of_version(),
        }

    repo_dir = Path(__file__).resolve().parents[2]  # dossier backend, dans le dépôt git
    head = git_lines(["rev-parse", "--short", "HEAD"], repo_dir)
    if head:
        commit = head[0]

    # Tags posés EXACTEMENT sur le commit courant : seule source fiable pour
    # savoir si ce checkout EST une Stable (tag strict Vx.y.z) ou un canal
    # rolling (tag mobile du canal) — `git describe` seul tranche
    # arbitrairement quand plusieurs tags pointent le même commit (cas
    # courant juste après la promotion d'une Bêta/Canary en Stable).
    tags_here = git_lines(["tag", "--points-at", "HEAD"], repo_dir)
    stable_here = sorted((t for t in tags_here if STABLE_TAG_RE.match(t)), key=parse_version)
    if stable_here:
        version = stable_here[-1]
        return {
            "current_version": version, "current_tag": version, "current_commit": commit,
            "local_rolling_channel": None,
        }
    # Si plusieurs tags mobiles pointent le même commit (rare : juste après une promotion
    # Canary -> Bêta), le premier du registre l'emporte (Bêta : publication manuelle, donc
    # l'action la plus délibérée, avant la Canary automatique à chaque push).
    for channel in release_channel.CHANNELS:
        if channel.rolling and channel.release_tag in tags_here:
            return rolling_build_info(channel, commit)

    described = git_lines(["describe", "--tags", "--always"], repo_dir)
    if described:
        tag = described[0]

    # Version de base (ex: 'V3.0.0-10-gfedd080' -> 'V3.0.0')
    base_version = tag.split("-")[0] if "-" in tag else tag
    if not base_version.upper().startswith("V"):
        base_version = f"V{base_version}"

    # Si le tag résolu n'est pas un semver valide (ex: simple SHA de commit
    # '92e2c85' en cas de clone superficiel shallow/CI sans fetch des tags),
    # repli systématique sur la source de vérité VERSION/get_app_tag().
    if not re.match(r"^V?\d+(\.\d+)+", base_version, re.IGNORECASE):
        base_version = get_app_tag()

    return {
        "current_version": base_version,
        "current_tag": tag,
        "current_commit": commit,
        "local_rolling_channel": None,
    }
