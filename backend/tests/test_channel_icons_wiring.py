"""Garde-fou du câblage des icônes par canal (Stable / Bêta / Canary) sur TOUTES les plateformes.

Ce test ne vérifie pas un comportement : il échoue quand une des implémentations du
mécanisme diverge des autres, avant que la divergence n'atteigne une release. Guide du
mécanisme : Assets/Images/channel-icons/README.md.

  - même liste de canaux dans le backend, le générateur, le frontend, Android et le paquetage ;
  - même règle « canal du build d'après le suffixe de version » dans Python, shell et Gradle ;
  - fichiers générés présents, à jour et attribués au bon canal ;
  - chaque plateforme embarque / installe l'icône qu'il faut (specs PyInstaller, paquets
    Linux, Inno Setup, ressources Android).
"""

import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from app.desktop import channel_icon
from app.utils.version import RELEASE_CHANNELS, build_channel_of_version

REPO = Path(__file__).resolve().parents[2]
CHANNELS = list(RELEASE_CHANNELS)

# Version -> canal du build. Table partagée par toutes les implémentations de la règle.
VERSION_CASES = {
    "5.0.5": "stable",
    "V5.0.5": "stable",
    "5.0.5-beta": "beta",
    "5.0.5-canary": "canary",
    "5.0.5~beta": "beta",
    "5.0.5+canary.42": "canary",  # champ Version: d'un .deb (shell uniquement : pas une VERSION)
    "5.0.5-nightly": "stable",
    "5.0.5-rc1": "stable",
}


def _read(relative: str) -> str:
    return (REPO / relative).read_text(encoding="utf-8")


def _load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, REPO / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generator():
    return _load_module("generate_channel_icons", "scripts/generate_channel_icons.py")


@pytest.fixture(scope="module")
def spec_helper():
    return _load_module("bobine_packaging_channel", "packaging/common/channel.py")


# --- Registre des canaux ------------------------------------------------------------------


def test_registre_identique_dans_le_generateur_et_le_helper_de_paquetage(generator, spec_helper):
    assert list(generator.CHANNELS) == CHANNELS
    assert list(spec_helper.CHANNELS) == CHANNELS
    assert generator.DEFAULT_CHANNEL == spec_helper.DEFAULT_CHANNEL == "stable"


def test_registre_identique_dans_le_frontend():
    source = _read("frontend/src/lib/releaseChannel.ts")
    declared = re.search(r"RELEASE_CHANNELS\s*=\s*\[([^\]]+)\]", source).group(1)
    assert re.findall(r'"(\w+)"', declared) == CHANNELS


def test_registre_identique_dans_android():
    gradle = _read("android/app/build.gradle.kts")
    assert re.search(r"releaseChannels\s*=\s*listOf\(([^)]*)\)", gradle).group(1).replace('"', "").replace(" ", "").split(",") == CHANNELS
    prefs = _read("android/app/src/main/java/com/bobine/app/NativeBridge.kt")
    assert re.findall(r'"(\w+)"', re.search(r"VALID\s*=\s*setOf\(([^)]*)\)", prefs).group(1)) == CHANNELS
    splash = _read("android/app/src/main/java/com/bobine/app/SplashChannel.kt")
    for channel in CHANNELS:
        assert f"R.drawable.bobine_splash_logo_{channel}" in splash


def test_registre_identique_dans_le_shell_de_paquetage():
    assert re.search(r"\(beta\|canary\)", _read("packaging/common/channel.sh"))


# --- Règle « canal du build d'après la version » -------------------------------------------


@pytest.mark.parametrize(("version", "expected"), [(v, c) for v, c in VERSION_CASES.items() if "+" not in v])
def test_regle_du_canal_du_build_python(version, expected, spec_helper):
    assert build_channel_of_version(version) == expected
    assert spec_helper.channel_of_version(version) == expected


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash absent")
@pytest.mark.parametrize(("version", "expected"), list(VERSION_CASES.items()))
def test_regle_du_canal_du_build_shell(version, expected):
    out = subprocess.run(
        ["bash", "-c", f'source "{REPO}/packaging/common/channel.sh"; bobine_channel_of_version "$1"', "_", version],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert out == expected


def test_regle_du_canal_du_build_gradle():
    """Gradle n'est pas exécutable ici : on vérifie que la règle y est écrite comme en Python
    (suffixe après « - » ou « ~ », seuls beta et canary reconnus, sinon stable)."""
    gradle = _read("android/app/build.gradle.kts")
    assert "replace('~', '-').substringAfter('-', \"\")" in gradle
    assert 'listOf("beta", "canary")' in gradle
    assert '?: "stable"' in gradle


# --- Fichiers générés -----------------------------------------------------------------------


def test_fichiers_generes_presents_et_a_jour(generator):
    stale = [o.path for o in generator.all_outputs() if not generator._is_current(o, REPO / o.path)]
    assert not stale, "relancer scripts/generate_channel_icons.py : " + ", ".join(stale)


def test_aucun_fichier_historique_non_genere_ne_traine():
    for legacy in (
        "packaging/windows/bobine.ico",
        "packaging/macos/bobine.icns",
        "packaging/linux/icons/hicolor",
        "packaging/linux/icons/pixmaps",
    ):
        assert not (REPO / legacy).exists(), f"{legacy} est remplacé par les icônes par canal"
    assert not list((REPO / "android/app/src/main/res").glob("mipmap-*dpi/ic_launcher_foreground.png"))


def _blueness(path: Path) -> float:
    """Écart moyen bleu - rouge sur les pixels opaques et assez saturés (le ruban)."""
    image = Image.open(path).convert("RGBA")
    raw = image.tobytes()
    pixels = zip(raw[0::4], raw[1::4], raw[2::4], raw[3::4])
    values = [b - r for r, g, b, a in pixels if a > 200 and max(r, g, b) - min(r, g, b) > 80]
    return sum(values) / len(values) if values else 0.0


@pytest.mark.parametrize(
    "template",
    [
        "Assets/Images/logo_bobine_icon_{c}.png",
        "frontend/public/logo-{c}.png",
        "frontend/public/favicon-{c}.png",
        "assistant/ui/assets/channel-{c}.png",
        "packaging/linux/icons/{c}/hicolor/256x256/apps/com.bobine.app.png",
        "android/app/src/channel-{c}/res/mipmap-xxxhdpi/ic_launcher_foreground.png",
        "android/app/src/main/res/drawable-nodpi/bobine_splash_logo_{c}.png",
    ],
)
def test_chaque_fichier_porte_la_teinte_de_son_canal(template):
    """Stable = ruban neutre, Bêta = bleu, Canary = or : détecte une icône copiée sous le mauvais canal."""
    stable, beta, canary = (_blueness(REPO / template.format(c=c)) for c in ("stable", "beta", "canary"))
    assert beta > 40, "le ruban bêta doit être bleu"
    assert canary < -40, "le ruban canary doit être doré (rouge > bleu)"
    assert abs(stable) < 25, "le ruban stable doit rester neutre"


def test_icone_par_defaut_historique_est_la_stable():
    assert (REPO / "Assets/Images/logo_bobine_icon.png").read_bytes() != b""
    default = Image.open(REPO / "Assets/Images/logo_bobine_icon.png").convert("RGBA")
    stable = Image.open(REPO / "Assets/Images/logo_bobine_icon_stable.png").convert("RGBA")
    assert default.tobytes() == stable.tobytes()


# --- Embarquement par plateforme -------------------------------------------------------------


def test_les_specs_embarquent_les_icones_de_canal_de_la_barre_systeme(spec_helper):
    datas = spec_helper.runtime_icon_datas(REPO)
    assert sorted(Path(src).name for src, _ in datas) == sorted(
        ["logo_bobine_icon.png"] + [f"logo_bobine_icon_{c}.png" for c in CHANNELS]
    )
    assert all(Path(src).exists() and dest == "." for src, dest in datas)
    for spec in ("windows", "macos", "linux"):
        assert "channel.runtime_icon_datas(REPO_DIR)" in _read(f"packaging/{spec}/bobine.spec")


def test_nom_de_fichier_d_icone_du_tray_identique_au_helper_de_paquetage(spec_helper):
    for channel in CHANNELS:
        assert channel_icon.channel_icon_filename(channel) == f"logo_bobine_icon_{channel}.png"
    assert channel_icon.DEFAULT_ICON_FILENAME == "logo_bobine_icon.png"


def test_icone_d_executable_windows_et_du_bundle_macos_suivent_le_canal_du_build():
    windows = _read("packaging/windows/bobine.spec")
    assert 'f"bobine-{BUILD_CHANNEL}.ico"' in windows and 'stage_icon(Path(ICON_PATH), Path(WORKPATH), "bobine.ico")' in windows
    macos = _read("packaging/macos/bobine.spec")
    assert 'f"bobine-{BUILD_CHANNEL}.icns"' in macos and '"bobine.icns"' in macos
    assert '"CFBundleIconFile": "bobine.icns"' in macos
    # L'installeur Inno Setup reprend l'icône choisie par le .spec : aucune règle de canal en double.
    assert r"SetupIconFile={#MyDistDir}\bobine.ico" in _read("packaging/windows/bobine.iss")
    for channel in CHANNELS:
        assert (REPO / f"packaging/windows/bobine-{channel}.ico").exists()
        assert (REPO / f"packaging/macos/bobine-{channel}.icns").exists()


def test_les_paquets_linux_installent_les_icones_via_le_script_commun():
    for script in ("packaging/linux/build_deb.sh", "packaging/common/stage_root.sh"):
        text = _read(script)
        assert "source" in text and "channel.sh" in text, script
        assert 'install_channel_icons "$(bobine_channel_of_version "${VERSION}")"' in text, script


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash absent")
@pytest.mark.parametrize("channel", CHANNELS)
def test_arborescence_installee_identique_pour_chaque_canal_et_couverte_par_le_rpm(channel, tmp_path):
    subprocess.run(
        ["bash", "-c", f'source "{REPO}/packaging/common/channel.sh"; install_channel_icons {channel} "{REPO}/packaging/linux/icons" "{tmp_path}"'],
        check=True,
    )
    installed = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*") if p.is_file())
    sizes = [16, 24, 32, 48, 64, 128, 256, 512]
    expected = sorted(
        [f"usr/share/icons/hicolor/{s}x{s}/apps/{n}.png" for s in sizes for n in ("bobine", "com.bobine.app")]
        + [f"usr/share/pixmaps/{n}.png" for n in ("bobine", "com.bobine.app")]
    )
    assert installed == expected
    # Le %files du RPM liste des motifs : tout fichier installé doit y être couvert, sinon rpmbuild
    # échoue (« Installed (but unpackaged) file(s) found »).
    spec = _read("packaging/rpm/bobine.spec")
    patterns = [line.strip() for line in spec.splitlines() if line.strip().startswith("/usr/share/icons/hicolor/") or line.strip().startswith("/usr/share/pixmaps")]
    assert patterns, "motifs d'icônes introuvables dans %files"
    import fnmatch

    for relative in installed:
        assert any(fnmatch.fnmatch("/" + relative, pattern) for pattern in patterns), f"/{relative} absent de %files"


def test_android_fournit_icone_et_banniere_pour_chaque_canal():
    for channel in CHANNELS:
        for density in ("mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi"):
            assert (REPO / f"android/app/src/channel-{channel}/res/mipmap-{density}/ic_launcher_foreground.png").exists()
        assert (REPO / f"android/app/src/tv-channel-{channel}/res/drawable/banner_bobine_tv.png").exists()
    gradle = _read("android/app/build.gradle.kts")
    assert 'getByName("main").res.srcDir("src/channel-$bobineChannel/res")' in gradle
    assert 'getByName("tv").res.srcDir("src/tv-channel-$bobineChannel/res")' in gradle
    # Le fond et la forme adaptative restent communs : un seul ic_launcher.xml, aucune copie par canal.
    assert (REPO / "android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml").exists()
    assert not list((REPO / "android/app/src").glob("channel-*/res/mipmap-anydpi-v26"))
