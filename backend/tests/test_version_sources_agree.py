import re
from pathlib import Path

from app.utils import version

REPO = Path(__file__).resolve().parents[2]
CURRENT = (REPO / "VERSION").read_text(encoding="utf-8").strip()


def _read(relative: str) -> str:
    return (REPO / relative).read_text(encoding="utf-8")


def test_version_est_un_numero_de_base_sans_suffixe_de_canal():
    assert re.fullmatch(r"\d+\.\d+\.\d+", CURRENT), CURRENT


def test_repli_du_backend():
    assert version._FALLBACK_VERSION == CURRENT


def test_repli_de_l_installeur_windows():
    assert re.search(r'#define MyAppVersion "([^"]+)"', _read("packaging/windows/bobine.iss")).group(1) == CURRENT


def test_repli_de_gradle():
    assert re.search(r'readText\(\)\.trim\(\) else "([^"]+)"', _read("android/app/build.gradle.kts")).group(1) == CURRENT


def test_derniere_release_du_metainfo_appstream():
    first = re.search(r'<release version="([^"]+)"', _read("packaging/linux/bobine.metainfo.xml")).group(1)
    assert first == CURRENT


def test_repli_de_l_installeur_autonome():
    assert re.search(r'SCRIPT_VERSION=.*echo "([^\"]+)"', _read("install.sh")).group(1) == CURRENT
