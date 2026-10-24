"""Signature de la liste des empreintes d'une release (scripts/ci/sign-release-checksums.sh) et contrôle de complétude.

Une clé éphémère remplace la clé de production : le script lit son empreinte dans BOBINE_SIGNING_FINGERPRINT.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SIGN = ROOT / "scripts" / "ci" / "sign-release-checksums.sh"
VERIFY = ROOT / "scripts" / "ci" / "verify-release-assets.sh"

pytestmark = pytest.mark.skipif(shutil.which("gpg") is None or shutil.which("sha256sum") is None, reason="gpg et sha256sum requis")


@pytest.fixture()
def signing_env(tmp_path):
    home = tmp_path / "gnupg"
    home.mkdir(mode=0o700)
    env = {**os.environ, "GNUPGHOME": str(home)}
    subprocess.run(["gpg", "--batch", "--passphrase", "", "--quick-gen-key", "Test <test@example.invalid>", "rsa2048", "sign", "never"], env=env, check=True, capture_output=True)
    listing = subprocess.run(["gpg", "--batch", "--with-colons", "--list-secret-keys"], env=env, check=True, capture_output=True, text=True).stdout
    fingerprint = next(line.split(":")[9] for line in listing.splitlines() if line.startswith("fpr:"))
    return {**env, "BOBINE_SIGNING_FINGERPRINT": fingerprint}


def _release(tmp_path):
    directory = tmp_path / "release-assets"
    directory.mkdir()
    for name, content in {"Bobine-Setup-9.9.9.exe": b"exe", "bobine_9.9.9_amd64.deb": b"deb", "install.sh": b"#!/bin/sh\n"}.items():
        (directory / name).write_bytes(content)
    return directory


def test_la_liste_est_signee_et_verifiable(tmp_path, signing_env):
    directory = _release(tmp_path)
    subprocess.run(["bash", str(SIGN), str(directory)], env=signing_env, check=True, capture_output=True)
    lines = (directory / "SHA256SUMS").read_text().splitlines()
    assert [line.split("  ")[1] for line in lines] == ["Bobine-Setup-9.9.9.exe", "bobine_9.9.9_amd64.deb", "install.sh"]
    assert (directory / "SHA256SUMS.asc").read_text().startswith("-----BEGIN PGP SIGNATURE-----")
    # Ce que fera l'utilisateur : vérifier la signature, puis les empreintes.
    subprocess.run(["gpg", "--batch", "--verify", "SHA256SUMS.asc", "SHA256SUMS"], cwd=directory, env=signing_env, check=True, capture_output=True)
    subprocess.run(["sha256sum", "--check", "--strict", "SHA256SUMS"], cwd=directory, check=True, capture_output=True)


def test_un_fichier_modifie_est_detecte(tmp_path, signing_env):
    directory = _release(tmp_path)
    subprocess.run(["bash", str(SIGN), str(directory)], env=signing_env, check=True, capture_output=True)
    (directory / "bobine_9.9.9_amd64.deb").write_bytes(b"altere")
    result = subprocess.run(["sha256sum", "--check", "--strict", "SHA256SUMS"], cwd=directory, capture_output=True, text=True)
    assert result.returncode != 0


def test_une_liste_alteree_invalide_la_signature(tmp_path, signing_env):
    directory = _release(tmp_path)
    subprocess.run(["bash", str(SIGN), str(directory)], env=signing_env, check=True, capture_output=True)
    sums = directory / "SHA256SUMS"
    sums.write_text(sums.read_text().replace("0", "1", 1))
    result = subprocess.run(["gpg", "--batch", "--verify", "SHA256SUMS.asc", "SHA256SUMS"], cwd=directory, env=signing_env, capture_output=True, text=True)
    assert result.returncode != 0


def test_une_cle_inattendue_est_refusee(tmp_path, signing_env):
    directory = _release(tmp_path)
    env = {**signing_env, "BOBINE_SIGNING_FINGERPRINT": "A" * 40}
    result = subprocess.run(["bash", str(SIGN), str(directory)], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert not (directory / "SHA256SUMS").exists()


def test_la_verification_de_completude_exige_la_liste(tmp_path):
    # Un dossier sans SHA256SUMS ni signature est refusé avant toute vérification d'empreinte.
    directory = _release(tmp_path)
    result = subprocess.run(["bash", str(VERIFY), str(directory), "9.9.9"], capture_output=True, text=True)
    assert result.returncode != 0
    assert "SHA256SUMS" in result.stdout + result.stderr
