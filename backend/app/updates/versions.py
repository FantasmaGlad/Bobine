"""Comparaison pure entre le build installé et une release."""
import re
from typing import Any
from app.release_channel import ROLLING_CHANNEL_IDS


STABLE_TAG_RE = re.compile(r"^V\d+\.\d+\.\d+$")


SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")


def parse_version(version_str: str) -> tuple[tuple[int, int, int], tuple]:
    """Parse une chaîne 'V3.0.1' ou 'V3.0.1-beta.2' en clé de tri conforme à la précédence semver : à base MAJOR.MINOR.PATCH égale, une version SANS pre-release est toujours postérieure à une version AVEC pre-release, et deux pre-releases se comparent identifiant par identifiant (numérique si possible, sinon lexical — les identifiants numériques ont une précédence inférieure aux alphanumériques, comme le veut semver)."""
    s = (version_str or "").strip()
    if s[:1] in ("v", "V"):
        s = s[1:]
    base_part, _, prerelease_part = s.partition("-")
    base_numbers = [int(n) for n in re.findall(r"\d+", base_part)[:3]]
    base_numbers += [0] * (3 - len(base_numbers))
    base = (base_numbers[0], base_numbers[1], base_numbers[2])

    if not prerelease_part:
        return base, (1,)

    parsed_ids: tuple = tuple(
        (0, int(part)) if part.isdigit() else (1, part)
        for part in prerelease_part.split(".")
        if part
    )
    return base, (0, *parsed_ids)


def short_sha(sha: str | None, length: int = 7) -> str:
    return (sha or "")[:length]


def commit_based_update(local_commit: str, release_data: dict[str, Any]) -> bool:
    """Un canal rolling (Bêta curée ou Canary) n'a pas de numéro de version qui avance à chaque build (tag fixe) — la comparaison porte donc sur le COMMIT plutôt que sur une version sémantique."""
    remote_commit = short_sha(release_data.get("target_commitish"))
    if not remote_commit or local_commit in ("unknown", ""):
        return False
    return not remote_commit.startswith(local_commit) and not local_commit.startswith(remote_commit)


def rolling_tag_update(local_commit: str, release_data: dict[str, Any], tag_name: str) -> dict[str, Any]:
    """Décision pour un canal rolling (Bêta curée ou Canary), paramétrée par le nom du tag mobile concerné — voir `commit_based_update`."""
    remote_short = short_sha(release_data.get("target_commitish"))
    return {
        "has_update": commit_based_update(local_commit, release_data),
        "is_downgrade": False,
        "latest_version": f"{tag_name} ({remote_short})" if remote_short else tag_name,
    }


def evaluate_update(channel: str, local: dict[str, Any], release_data: dict[str, Any]) -> dict[str, Any]:
    """Décision pure (aucun I/O, testable) : y a-t-il quelque chose à installer pour ce canal, et est-ce un retour en arrière ?"""
    if channel in ROLLING_CHANNEL_IDS:
        return rolling_tag_update(local["current_commit"], release_data, channel)
    latest_tag = release_data.get("tag_name") or ""
    latest, current = parse_version(latest_tag), parse_version(local["current_version"])
    if latest > current:
        return {"has_update": True, "is_downgrade": False, "latest_version": latest_tag}
    if local.get("local_rolling_channel") and latest != current:
        return {"has_update": True, "is_downgrade": True, "latest_version": latest_tag}
    return {"has_update": False, "is_downgrade": False, "latest_version": latest_tag}


def release_target_ref(release_data: dict[str, Any]) -> str | None:
    """Référence git à comparer au build local : le SHA de la release s'il est connu (tag mobile d'un canal rolling), sinon son tag (Stable)."""
    commitish = (release_data.get("target_commitish") or "").lower()
    if SHA_RE.match(commitish):
        return commitish
    tag = release_data.get("tag_name") or ""
    return tag or None
