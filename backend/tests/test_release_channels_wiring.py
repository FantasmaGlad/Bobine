"""Garde-fou de l'architecture des canaux de diffusion : UN registre (app/release_channel.py), des
consommateurs qui en DÉRIVENT. Ce test échoue dès qu'un consommateur réécrit une liste ou une règle
de canaux au lieu de la lire, ou qu'un fichier généré est périmé.

  registre Python ──┬── backend (réglages, mises à jour, barre système) : import direct
                    ├── specs PyInstaller, scripts de paquetage, générateur d'icônes : chargé par son chemin
                    ├── android/release-channels.json ──── Gradle ──── BuildConfig ──── Kotlin
                    └── frontend/src/lib/releaseChannels.generated.ts ──── interface web

Guide : Assets/Images/channel-icons/README.md.
"""

import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from app import release_channel

REPO = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (REPO / relative).read_text(encoding="utf-8")


def _code_lines(relative: str, comment_prefixes=("//", "*", "/*")) -> list[str]:
    return [
        line for line in _read(relative).splitlines()
        if line.strip() and not line.strip().startswith(comment_prefixes)
    ]


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, REPO / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# --- Fichiers générés -------------------------------------------------------------------------


def test_fichiers_generes_a_jour():
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "sync_release_channels.py"), "--check"], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


# --- Adaptateurs de construction : aucune règle recopiée ---------------------------------------


def test_le_generateur_d_icones_et_le_paquetage_lisent_le_registre():
    generator = _load("generate_channel_icons", "scripts/generate_channel_icons.py")
    packaging = _load("bobine_packaging_channel", "packaging/common/channel.py")
    assert tuple(generator.CHANNELS) == release_channel.CHANNEL_IDS
    assert generator.DEFAULT_CHANNEL == release_channel.DEFAULT_CHANNEL
    assert tuple(packaging.channels()) == release_channel.CHANNEL_IDS


@pytest.mark.parametrize(
    "version", ["5.0.5", "V5.0.5", "5.0.5-beta", "5.0.5-canary", "5.0.5~beta", "5.0.5+canary.42", "5.0.5-rc1", "5.0.5-beta.2", ""]
)
def test_paquetage_et_shell_appliquent_la_meme_regle_que_le_backend(version):
    expected = release_channel.build_channel_of_version(version)
    packaging = _load("bobine_packaging_channel", "packaging/common/channel.py")
    assert packaging.channel_of_version(version) == expected
    if shutil.which("bash") and shutil.which("python3"):
        out = subprocess.run(
            ["bash", "-c", f'source "{REPO}/packaging/common/channel.sh"; bobine_channel_of_version "$1"', "_", version],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        assert out == expected


def test_aucune_regle_de_canal_reecrite_dans_les_scripts_et_specs():
    for relative in (
        "packaging/common/channel.sh", "packaging/common/channel.py", "packaging/common/stage_root.sh",
        "packaging/linux/build_deb.sh", "packaging/windows/bobine.spec", "packaging/macos/bobine.spec",
        "packaging/linux/bobine.spec", "scripts/generate_channel_icons.py",
    ):
        code = "\n".join(_code_lines(relative, ("#", "//")))
        assert not re.search(r"\(beta\|canary\)|\"canary\"|'canary'|\(canary\|beta\)", code), f"{relative} réécrit la liste des canaux"


def test_backend_n_ecrit_pas_la_liste_des_canaux_ailleurs_que_dans_le_registre():
    offenders = []
    for path in sorted((REPO / "backend" / "app").rglob("*.py")):
        if path.name == "release_channel.py":
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#")[0]
            if re.search(r"""["']canary["']""", code) and re.search(r"""["']beta["']""", code):
                offenders.append(f"{path.relative_to(REPO)}:{number}")
    # database.py : la migration historique « beta -> canary » est une donnée figée, pas une liste de canaux.
    offenders = [o for o in offenders if not o.startswith("backend/app/database.py")]
    assert not offenders, "liste de canaux écrite en dur : " + ", ".join(offenders)


# --- Android ------------------------------------------------------------------------------------


def test_gradle_lit_le_registre_sans_liste_ni_nom_de_canal_en_dur():
    code = "\n".join(_code_lines("android/app/build.gradle.kts"))
    assert 'resolve("release-channels.json")' in code
    assert not re.search(r"""["'](beta|canary)["']""", code), "nom de canal en dur dans build.gradle.kts"
    for needle in ('buildConfigField("String", "BUILD_CHANNEL"', 'buildConfigField("String", "RELEASE_CHANNELS"'):
        assert needle in code
    assert 'getByName("main").res.srcDir("src/channel-$bobineChannel/res")' in code
    assert 'getByName("tv").res.srcDir("src/tv-channel-$bobineChannel/res")' in code


def test_kotlin_derive_ses_canaux_du_registre():
    prefs = _read("android/app/src/main/java/com/bobine/app/NativeBridge.kt")
    assert "BuildConfig.RELEASE_CHANNELS" in prefs
    assert not re.search(r'setOf\("stable"', prefs), "liste de canaux écrite en dur dans UpdateChannelPref"
    splash = _read("android/app/src/main/java/com/bobine/app/SplashChannel.kt")
    assert "UpdateChannelPref.load(context) ?: BuildConfig.BUILD_CHANNEL" in splash
    # Les ressources d'écran de démarrage sont référencées statiquement (R.drawable) : une branche
    # par canal du registre, vérifiée ici puisque Kotlin ne peut pas les énumérer.
    for channel in release_channel.CHANNEL_IDS:
        assert f"R.drawable.bobine_splash_logo_{channel}" in splash, f"écran de démarrage Android manquant pour {channel}"
        assert (REPO / f"android/app/src/main/res/drawable-nodpi/bobine_splash_logo_{channel}.png").exists()


# --- Frontend ----------------------------------------------------------------------------------


def test_frontend_importe_la_liste_generee_et_ne_la_redeclare_pas():
    source = _read("frontend/src/lib/releaseChannel.ts")
    assert 'from "./releaseChannels.generated.ts"' in source
    assert not re.search(r"RELEASE_CHANNELS\s*=\s*\[", source)
    context = _read("frontend/src/lib/AppSettingsContext.tsx")
    assert not re.search(r'"stable"\s*\|\s*"beta"', context), "type de canal redéclaré dans AppSettingsContext"


# --- API de réglages ------------------------------------------------------------------------------


def test_les_reglages_exposent_origine_et_canal_d_installation():
    source = _read("backend/app/routers/settings.py")
    for key in ('"update_channel_source"', '"install_channel"'):
        assert key in source


# --- Consommateurs autonomes par nature : vérifiés contre le registre -------------------------------
# install.sh (distribué par `curl | bash`, il ne peut pas dépendre du dépôt avant de l'avoir cloné),
# l'assistant d'installation Tauri et les workflows CI ne peuvent pas importer le registre. Ils sont
# donc contrôlés ici : ajouter un canal au registre sans les mettre à jour fait échouer ce test.


def test_install_sh_connait_exactement_les_canaux_du_registre():
    source = _read("install.sh")
    usage = re.search(r"--channel=([a-z|]+)", source).group(1).split("|")
    assert usage == list(release_channel.CHANNEL_IDS)
    arms = re.findall(r"^\s*([a-z]+)\*\)\s+UPDATE_CHANNEL=\"([a-z]+)\"", source, re.M)
    assert {channel for _, channel in arms} == set(release_channel.ROLLING_CHANNEL_IDS)
    assert all(prefix == channel for prefix, channel in arms)


def test_assistant_d_installation_propose_exactement_les_canaux_du_registre():
    html = _read("assistant/ui/index.html")
    values = re.findall(r'name="update-channel"[^>]*value="([a-z]+)"', html) or re.findall(r'value="([a-z]+)"[^>]*name="update-channel"', html)
    assert values == list(release_channel.CHANNEL_IDS)
    # La mise à jour de l'assistant LUI-MÊME est volontairement limitée à Stable et Canary (outil de
    # développeur, cf. le commentaire d'app.js) : on vérifie seulement que les tags qu'il interroge
    # existent bien dans le registre.
    script = _read("assistant/ui/app.js")
    known_tags = {c.release_tag for c in release_channel.CHANNELS if c.rolling}
    assert set(re.findall(r"/releases/tags/([a-z]+)", script)) <= known_tags


def test_ci_publie_exactement_les_canaux_du_registre():
    ci = _read(".github/workflows/ci.yml")
    assigned = set(re.findall(r'^\s*CHANNEL="([a-z]+)"', ci, re.M)) - {"none"}
    assert assigned == set(release_channel.CHANNEL_IDS)
    for listing in re.findall(r"fromJSON\('(\[[^']*\])'\)", ci):
        if "canary" in listing:
            assert re.findall(r'"([a-z]+)"', listing) == list(release_channel.CHANNEL_IDS)
    play = _read(".github/workflows/play-aab.yml")
    refused = set(re.findall(r"\*-([a-z]+)\*", play))
    assert refused == {c.version_suffix for c in release_channel.CHANNELS if c.version_suffix}, "Google Play : seules les Stables sont publiées"
