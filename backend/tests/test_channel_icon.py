"""Icône de la barre système selon le canal : détection du canal (API > indice
d'installation > Stable), ordre de recherche des fichiers, repli. Aucun réseau, aucun
affichage : tout est injecté (cf. app/desktop/channel_icon.py)."""

from pathlib import Path

import pytest
from PIL import Image

from app.desktop import channel_icon
from app.utils.version import (
    DEFAULT_RELEASE_CHANNEL,
    RELEASE_CHANNELS,
    build_channel_of_version,
    normalize_release_channel,
)


def _settings(channel):
    return lambda: {"update_channel": channel}


def _boom():
    raise OSError("backend injoignable")


def test_api_est_la_source_de_verite_meme_si_l_indice_d_installation_diverge(tmp_path):
    hint = tmp_path / "update-channel"
    hint.write_text("stable\n", encoding="utf-8")
    assert channel_icon.detect_channel(_settings("canary"), hint) == "canary"


def test_indice_d_installation_utilise_quand_le_backend_ne_repond_pas(tmp_path):
    hint = tmp_path / "update-channel"
    hint.write_text(" Beta \n", encoding="utf-8")
    assert channel_icon.detect_channel(_boom, hint) == "beta"


@pytest.mark.parametrize("answer", [None, {}, {"update_channel": "nightly"}, {"update_channel": 3}])
def test_reponse_inutilisable_retombe_sur_l_indice_puis_stable(tmp_path, answer):
    assert channel_icon.detect_channel(lambda: answer, tmp_path / "absent") == DEFAULT_RELEASE_CHANNEL


def test_indice_invalide_ignore(tmp_path):
    hint = tmp_path / "update-channel"
    hint.write_text("nightly", encoding="utf-8")
    assert channel_icon.detect_channel(_boom, hint) == "stable"


def test_candidats_icone_du_canal_avant_icone_par_defaut_a_chaque_emplacement():
    exe, images = Path("/opt/bobine"), Path("/repo/Assets/Images")
    names = [(p.parent, p.name) for p in channel_icon.icon_candidates("beta", exe, images)]
    assert names == [
        (exe, "logo_bobine_icon_beta.png"),
        (exe, "logo_bobine_icon.png"),
        (exe.parent / "Resources", "logo_bobine_icon_beta.png"),
        (exe.parent / "Resources", "logo_bobine_icon.png"),
        (images, "logo_bobine_icon_beta.png"),
        (images, "logo_bobine_icon.png"),
    ]


def _write_icon(path: Path, color):
    image = Image.new("RGBA", (40, 20), (0, 0, 0, 0))
    image.paste(Image.new("RGBA", (30, 10), color), (5, 5))
    image.save(path)


def test_chargement_prend_l_icone_du_canal_et_la_rend_carree(tmp_path):
    _write_icon(tmp_path / "logo_bobine_icon_canary.png", (255, 200, 0, 255))
    _write_icon(tmp_path / "logo_bobine_icon.png", (200, 200, 200, 255))
    image = channel_icon.load_tray_image("canary", channel_icon.icon_candidates("canary", tmp_path, tmp_path / "x"))
    assert image.size == (channel_icon.TRAY_ICON_SIZE,) * 2
    assert image.getpixel((32, 32))[:3] == (255, 200, 0)


def test_repli_sur_l_icone_par_defaut_si_celle_du_canal_manque(tmp_path):
    _write_icon(tmp_path / "logo_bobine_icon.png", (200, 200, 200, 255))
    image = channel_icon.load_tray_image("beta", channel_icon.icon_candidates("beta", tmp_path, tmp_path / "x"))
    assert image.getpixel((32, 32))[:3] == (200, 200, 200)


def test_fichier_illisible_saute_vers_le_candidat_suivant(tmp_path):
    (tmp_path / "logo_bobine_icon_beta.png").write_bytes(b"pas une image")
    _write_icon(tmp_path / "logo_bobine_icon.png", (1, 2, 3, 255))
    image = channel_icon.load_tray_image("beta", channel_icon.icon_candidates("beta", tmp_path, tmp_path / "x"))
    assert image.getpixel((32, 32))[:3] == (1, 2, 3)


def test_icone_de_repli_quand_aucun_fichier(tmp_path):
    image = channel_icon.load_tray_image("stable", channel_icon.icon_candidates("stable", tmp_path, tmp_path))
    assert image.size == (channel_icon.TRAY_ICON_SIZE,) * 2


@pytest.mark.parametrize(
    ("version", "expected"),
    [("5.0.5", "stable"), ("5.0.5-beta", "beta"), ("V5.0.5-canary", "canary"), ("5.0.5~beta", "beta"),
     ("5.0.5-rc1", "stable"), ("", "stable")],
)
def test_canal_du_build_deduit_du_suffixe_de_version(version, expected):
    assert build_channel_of_version(version) == expected


def test_registre_des_canaux():
    assert RELEASE_CHANNELS == ("stable", "beta", "canary")
    assert normalize_release_channel(" CANARY ") == "canary"
    assert normalize_release_channel("nightly") is None
    assert normalize_release_channel(None) is None
