"""Android refuse un APK au versionCode inférieur (UpdateManager.validatePackage)
mais seulement après 46 à 69 Mo de téléchargement. Le versionCode des builds de
la CI vaut `git rev-list --count` : le backend compare donc les commits (API de
comparaison GitHub) AVANT de proposer, de télécharger ou de planifier."""

import asyncio
import urllib.error

import pytest
from fastapi import HTTPException

from app.routers import updates


@pytest.fixture(autouse=True)
def _cache_vide():
    updates._COMMIT_DISTANCE_CACHE.clear()
    yield
    updates._COMMIT_DISTANCE_CACHE.clear()


def _local(commit="a910129"):
    return {
        "current_version": "V5.0.6-canary", "current_tag": "canary",
        "current_commit": commit, "local_rolling_channel": "canary",
    }


def _comparaison(monkeypatch, ahead=0, behind=0, erreur=None):
    appels = []

    def faux(url, etag=None):
        appels.append(url)
        if erreur:
            raise erreur
        return 200, {"ahead_by": ahead, "behind_by": behind, "status": "x"}, None

    monkeypatch.setattr(updates, "_github_get", faux)
    return appels


def _eval(profile, local, release, channel="beta"):
    evaluation = updates._evaluate_update(channel, local, release)
    return asyncio.run(updates._refuse_android_downgrade(profile, local, release, evaluation))


BETA = {"tag_name": "beta", "target_commitish": "f2d46a79" + "0" * 32}
STABLE = {"tag_name": "V5.0.5", "target_commitish": "main"}


def test_canary_vers_beta_plus_ancienne_est_bloque(monkeypatch):
    appels = _comparaison(monkeypatch, ahead=0, behind=32)
    r = _eval("android", _local(), BETA)
    assert r["has_update"] is False and r["is_downgrade"] is True and r["downgrade_blocked"] is True
    # SHA de la release (tag mobile), pas le nom de tag
    assert appels == [f"{updates._COMPARE_URL}/a910129...{BETA['target_commitish']}"]


def test_canary_vers_stable_plus_ancienne_compare_sur_le_tag(monkeypatch):
    appels = _comparaison(monkeypatch, ahead=0, behind=33)
    r = _eval("android", _local(), STABLE, channel="stable")
    assert r["has_update"] is False and r["downgrade_blocked"] is True
    assert appels == [f"{updates._COMPARE_URL}/a910129...V5.0.5"]


def test_cible_plus_recente_reste_proposee(monkeypatch):
    _comparaison(monkeypatch, ahead=5, behind=0)
    r = _eval("android", _local(), BETA)
    assert r["has_update"] is True and not r.get("downgrade_blocked")


def test_historique_divergent_se_juge_sur_le_nombre_de_commits(monkeypatch):
    # versionCode cible - versionCode local = ahead_by - behind_by
    _comparaison(monkeypatch, ahead=3, behind=4)
    assert _eval("android", _local(), BETA)["downgrade_blocked"] is True
    updates._COMMIT_DISTANCE_CACHE.clear()
    _comparaison(monkeypatch, ahead=4, behind=4)
    assert _eval("android", _local(), BETA)["has_update"] is True


def test_comparaison_impossible_laisse_la_validation_apres_telechargement(monkeypatch):
    _comparaison(monkeypatch, erreur=urllib.error.URLError("hors ligne"))
    r = _eval("android", _local(), BETA)
    assert r["has_update"] is True and not r.get("downgrade_blocked")
    assert updates._COMMIT_DISTANCE_CACHE == {}  # un échec n'est jamais mémorisé


def test_commit_local_inconnu_ne_declenche_aucune_requete(monkeypatch):
    appels = _comparaison(monkeypatch, behind=10)
    r = updates._evaluate_update("beta", _local("unknown"), BETA)
    assert asyncio.run(updates._refuse_android_downgrade("android", _local("unknown"), BETA, r)) == r
    assert appels == []


@pytest.mark.parametrize("profile", ["windows", "macos", "linux-desktop", "linux-headless"])
def test_autres_profils_ne_sont_pas_concernes(monkeypatch, profile):
    appels = _comparaison(monkeypatch, behind=32)
    r = _eval(profile, _local(), BETA)
    assert r["has_update"] is True
    assert appels == []


def test_resultat_mis_en_cache(monkeypatch):
    appels = _comparaison(monkeypatch, behind=32)
    _eval("android", _local(), BETA)
    _eval("android", _local(), BETA)
    assert len(appels) == 1


# --- bout en bout : check, apply et planification -----------------------------

class _Handler:
    def is_store_managed(self): return False
    def can_auto_apply(self): return True
    def can_schedule_auto_apply(self): return True
    def supports_git_versioning(self): return False
    def asset_variant(self): return None


@pytest.fixture
def android_beta(monkeypatch):
    release = {
        **BETA, "html_url": "https://example.invalid/r",
        "assets": [{
            "name": "Bobine-beta.apk", "size": 46_000_000, "digest": "sha256:" + "a" * 64,
            "browser_download_url": "https://example.invalid/Bobine-beta.apk",
        }],
    }

    async def fetch(channel, force=False):
        return release, None

    monkeypatch.setattr(updates, "_fetch_release_for_channel", fetch)
    monkeypatch.setattr(updates, "_get_update_channel", lambda db: "beta")
    monkeypatch.setattr(updates, "_get_local_version_info", lambda: _local())
    monkeypatch.setattr(updates, "get_deployment_profile", lambda: "android")
    monkeypatch.setattr(updates, "get_profile_handler", lambda: _Handler())
    monkeypatch.setattr(updates, "is_running", lambda: False)
    return release


def test_check_ne_propose_pas_le_retour_en_arriere(monkeypatch, android_beta):
    _comparaison(monkeypatch, behind=32)
    r = asyncio.run(updates.check_updates(db=None))
    assert r["has_update"] is False and r["is_downgrade"] is True
    assert "plus ancienne" in r["message"]


def test_check_propose_la_mise_a_jour_montante(monkeypatch, android_beta):
    _comparaison(monkeypatch, ahead=2)
    r = asyncio.run(updates.check_updates(db=None))
    assert r["has_update"] is True and "message" not in r


def test_apply_refuse_avant_tout_telechargement(monkeypatch, android_beta):
    _comparaison(monkeypatch, behind=32)
    lances = []
    monkeypatch.setattr(updates, "run_update_pipeline", lambda *a: lances.append(a))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(updates.apply_update(background_tasks=None, db=None))
    assert exc.value.status_code == 400 and "plus ancienne" in exc.value.detail
    assert lances == []


def test_planification_ne_telecharge_pas(monkeypatch, android_beta):
    _comparaison(monkeypatch, behind=32)
    lances = []

    async def pipeline(*a):
        lances.append(a)

    monkeypatch.setattr(updates, "run_update_pipeline", pipeline)
    asyncio.run(updates.run_scheduled_update_if_available(db=None))
    assert lances == []


def test_planification_telecharge_une_mise_a_jour_montante(monkeypatch, android_beta):
    _comparaison(monkeypatch, ahead=2)
    lances = []

    async def pipeline(*a):
        lances.append(a)

    monkeypatch.setattr(updates, "run_update_pipeline", pipeline)
    monkeypatch.setattr(updates, "log_activity", lambda *a, **k: None)
    asyncio.run(updates.run_scheduled_update_if_available(db=None))
    assert len(lances) == 1
