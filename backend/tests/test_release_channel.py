"""Registre et résolution des canaux de diffusion (app/release_channel.py).

Règle de fond : sans choix explicite de l'utilisateur, le canal des mises à jour ET des icônes est
celui par lequel l'application a été installée, sur toutes les plateformes et méthodes
d'installation. Un choix explicite l'emporte toujours."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import release_channel
from app.models import Base, Setting
from app.routers import settings, updates

MODULE_PATH = Path(release_channel.__file__)


# --- Registre -----------------------------------------------------------------------------------


def test_registre_coherent():
    ids = [channel.id for channel in release_channel.CHANNELS]
    assert ids == ["stable", "beta", "canary"]
    assert len(set(ids)) == len(ids)
    assert release_channel.DEFAULT_CHANNEL == ids[0]
    suffixes = [c.version_suffix for c in release_channel.CHANNELS if c.version_suffix]
    assert len(set(suffixes)) == len(suffixes), "deux canaux ne peuvent pas partager un suffixe de version"
    stable = release_channel.get("stable")
    assert stable and not stable.rolling and stable.version_suffix is None
    assert release_channel.ROLLING_CHANNEL_IDS == ("beta", "canary")
    assert all(release_channel.get(i).release_tag for i in release_channel.ROLLING_CHANNEL_IDS)


def test_module_autonome_charge_par_son_chemin_sans_le_paquet_app():
    """Les outils de construction (specs, paquetage, générateur) le chargent par son chemin : il
    ne doit rien importer d'autre que la bibliothèque standard à l'import."""
    code = (
        "import importlib.util, sys;"
        f"spec = importlib.util.spec_from_file_location('rc', r'{MODULE_PATH}');"
        "m = importlib.util.module_from_spec(spec); sys.modules['rc'] = m; spec.loader.exec_module(m);"
        "assert not any(name == 'app' or name.startswith('app.') for name in sys.modules);"
        "print(m.build_channel_of_version('5.0.5-canary'))"
    )
    result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "canary"


@pytest.mark.parametrize(("value", "expected"), [("canary", "canary"), (" BETA ", "beta"), ("nightly", None), ("", None), (None, None), (3, None)])
def test_normalize(value, expected):
    assert release_channel.normalize(value) == expected


# --- Canal d'un build d'après sa version ------------------------------------------------------------


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("5.0.5", None), ("V5.0.5", None), ("", None),
        ("5.0.5-beta", "beta"), ("5.0.5-canary", "canary"), ("V5.0.5-canary", "canary"), ("5.0.5~beta", "beta"),
        ("5.0.5+canary.42", "canary"), ("5.0.5+beta.7", "beta"),
        ("5.0.5-rc1", None), ("5.0.5-nightly", None), ("5.0.5-beta.2", None), ("5.0.5+canary", None),
    ],
)
def test_canal_d_un_build_d_apres_sa_version(version, expected):
    assert release_channel.rolling_channel_of_version(version) == expected
    assert release_channel.build_channel_of_version(version) == (expected or "stable")


# --- Canal d'installation et canal effectif ----------------------------------------------------------------


def _hint(tmp_path, content):
    path = tmp_path / "update-channel"
    path.write_text(content, encoding="utf-8")
    return path


def test_le_build_donne_le_canal_d_installation(tmp_path):
    for version, expected in (("5.0.5", "stable"), ("5.0.5-beta", "beta"), ("5.0.5-canary", "canary")):
        assert release_channel.install_channel(version, tmp_path / "absent") == expected


def test_installation_depuis_les_sources_suit_le_canal_enregistre_par_install_sh(tmp_path):
    assert release_channel.install_channel("5.0.5", _hint(tmp_path, "canary\n")) == "canary"
    assert release_channel.install_channel("5.0.5", _hint(tmp_path, " Beta ")) == "beta"


def test_le_suffixe_du_build_l_emporte_sur_le_fichier_d_installation(tmp_path):
    assert release_channel.install_channel("5.0.5-beta", _hint(tmp_path, "canary")) == "beta"


def test_un_build_fige_ignore_le_fichier_laisse_par_une_ancienne_installation(tmp_path, monkeypatch):
    monkeypatch.setattr(release_channel.sys, "frozen", True, raising=False)
    assert release_channel.install_channel("5.0.5", _hint(tmp_path, "canary")) == "stable"
    assert release_channel.install_channel("5.0.5-canary", _hint(tmp_path, "stable")) == "canary"


@pytest.mark.parametrize("content", ["nightly", "", "\x00"])
def test_fichier_d_installation_invalide_ou_absent_donne_stable(content, tmp_path):
    assert release_channel.install_channel("5.0.5", _hint(tmp_path, content)) == "stable"
    assert release_channel.install_channel("5.0.5", tmp_path / "absent") == "stable"


def test_sans_choix_le_canal_effectif_est_celui_de_l_installation(tmp_path):
    for stored in (None, "", "nightly", 7):
        choice = release_channel.resolve(stored, "5.0.5-canary", tmp_path / "absent")
        assert (choice.effective, choice.source, choice.install) == ("canary", "install", "canary")


def test_un_choix_explicite_l_emporte_et_l_installation_reste_connue(tmp_path):
    choice = release_channel.resolve("stable", "5.0.5-canary", tmp_path / "absent")
    assert (choice.effective, choice.source, choice.install) == ("stable", "user", "canary")
    choice = release_channel.resolve("beta", "5.0.5", tmp_path / "absent")
    assert (choice.effective, choice.source, choice.install) == ("beta", "user", "stable")


# --- Consommateurs : réglages et mises à jour -------------------------------------------------------


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture()
def installed_as_canary(monkeypatch):
    monkeypatch.setattr(release_channel, "_current_version", lambda: "5.0.5-canary")


def test_reglages_sans_choix_proposent_le_canal_d_installation(db, installed_as_canary):
    payload = settings.get_settings(db)
    assert (payload["update_channel"], payload["update_channel_source"], payload["install_channel"]) == ("canary", "install", "canary")


def test_reglages_choix_explicite_stable_l_emporte_sur_une_installation_canary(db, installed_as_canary):
    db.add(Setting(key="update_channel", value="stable"))
    db.commit()
    payload = settings.get_settings(db)
    assert (payload["update_channel"], payload["update_channel_source"], payload["install_channel"]) == ("stable", "user", "canary")


def test_mises_a_jour_proposees_sur_le_canal_d_installation_sans_choix(db, installed_as_canary):
    assert updates._get_update_channel(db) == "canary"
    db.add(Setting(key="update_channel", value="beta"))
    db.commit()
    assert updates._get_update_channel(db) == "beta"


def test_valeur_invalide_en_base_retombe_sur_le_canal_d_installation(db, installed_as_canary):
    db.add(Setting(key="update_channel", value="nightly"))
    db.commit()
    assert updates._get_update_channel(db) == "canary"


def test_une_stable_sans_choix_reste_sur_stable(db, monkeypatch):
    monkeypatch.setattr(release_channel, "_current_version", lambda: "5.0.5")
    monkeypatch.setattr(release_channel, "INSTALL_HINT_PATH", Path("/nonexistent/update-channel"))
    assert updates._get_update_channel(db) == "stable"


def test_urls_de_release_derivees_du_registre():
    assert set(updates._ROLLING_RELEASE_URLS) == set(release_channel.ROLLING_CHANNEL_IDS)
    for channel_id, url in updates._ROLLING_RELEASE_URLS.items():
        assert url.endswith(f"/releases/tags/{release_channel.get(channel_id).release_tag}")


# --- Build installé sur un checkout git (appliance) : le tag mobile désigne le canal ----------------


class _GitProfile:
    @staticmethod
    def supports_git_versioning():
        return True


@pytest.mark.parametrize(
    ("tags", "expected_channel", "expected_version"),
    [
        (["canary"], "canary", "V5.0.5-canary"),
        (["beta"], "beta", "V5.0.5-beta"),
        (["canary", "beta"], "beta", "V5.0.5-beta"),  # le premier du registre l'emporte
        (["V5.0.5", "canary"], None, "V5.0.5"),        # un tag Stable strict l'emporte sur un tag mobile
    ],
)
def test_checkout_git_deduit_le_canal_du_tag_mobile(monkeypatch, tags, expected_channel, expected_version):
    monkeypatch.setattr(updates, "get_profile_handler", lambda: _GitProfile())
    monkeypatch.setattr(updates, "get_app_commit", lambda: "unknown")
    monkeypatch.setattr(updates, "get_app_version", lambda: "5.0.5")
    monkeypatch.setattr(updates, "_git_lines", lambda args, cwd: ["abc1234"] if args[0] == "rev-parse" else tags)
    info = updates._get_local_version_info()
    assert info["local_rolling_channel"] == expected_channel
    assert info["current_version"] == expected_version
    if expected_channel:
        assert info["current_tag"] == release_channel.get(expected_channel).release_tag


# --- Build distribué par une boutique (Google Play) : verrouillé sur la Stable --------------------------


class _StoreProfile:
    @staticmethod
    def is_store_managed():
        return True


@pytest.fixture()
def store_build(monkeypatch):
    from app.utils import deployment

    monkeypatch.setattr(deployment, "get_profile_handler", lambda: _StoreProfile())
    monkeypatch.setattr(settings, "get_profile_handler", lambda: _StoreProfile())


def test_build_boutique_reste_sur_stable_quel_que_soit_le_reglage_enregistre(db, store_build, installed_as_canary):
    db.add(Setting(key="update_channel", value="canary"))  # p. ex. restauré d'une sauvegarde d'un APK direct
    db.commit()
    payload = settings.get_settings(db)
    assert (payload["update_channel"], payload["update_channel_source"]) == ("stable", "locked")
    assert updates._get_update_channel(db) == "stable"


def test_build_boutique_refuse_de_rejoindre_un_autre_canal(db, store_build):
    import asyncio

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as refused:
        asyncio.run(settings.update_settings(settings.SettingsUpdate(update_channel="canary"), db))
    assert refused.value.status_code == 409


def test_verrou_inactif_hors_boutique(db, installed_as_canary, monkeypatch):
    from app.utils import deployment

    class _Direct:
        @staticmethod
        def is_store_managed():
            return False

    monkeypatch.setattr(deployment, "get_profile_handler", lambda: _Direct())
    assert deployment.resolve_update_channel(None).effective == "canary"
    assert deployment.resolve_update_channel("beta").source == "user"
