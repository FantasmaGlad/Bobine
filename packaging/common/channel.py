"""Canal du build et icônes par canal, pour les fichiers `.spec` PyInstaller.

Importé par packaging/{windows,macos,linux}/bobine.spec :

    sys.path.insert(0, str(SPEC_DIR.parent / "common"))
    import channel

Le canal du BUILD se lit dans le fichier `VERSION` de la racine : la CI y ajoute le suffixe
« -beta » ou « -canary » avant PyInstaller (cf. .github/workflows/ci.yml, étape « Identifiants
de build »), rien pour une Stable. C'est la même règle que
`backend/app/utils/version.py::build_channel_of_version` ; elle est volontairement
recopiée ici car un spec ne peut pas importer le backend, et
backend/tests/test_channel_icons_wiring.py vérifie que les deux restent identiques.

Ce canal fixe l'icône de l'exécutable / de l'installeur / du bundle. Il est distinct du canal
CHOISI à l'exécution (barre système, logo, favicon), pour lequel les trois icônes de canal
sont toujours embarquées (`runtime_icon_datas`).
"""

from __future__ import annotations

import shutil
from pathlib import Path

CHANNELS = ("stable", "beta", "canary")
DEFAULT_CHANNEL = "stable"


def channel_of_version(version: str) -> str:
    """« 5.0.5-canary » -> canary ; « 5.0.5~beta » -> beta ; tout autre suffixe ou aucun -> stable."""
    candidate = version.strip().lstrip("vV")
    suffix = candidate.replace("~", "-").partition("-")[2].lower()
    return suffix if suffix in ("beta", "canary") else DEFAULT_CHANNEL


def build_channel(repo_dir: Path) -> str:
    version_file = Path(repo_dir) / "VERSION"
    if not version_file.exists():
        return DEFAULT_CHANNEL
    return channel_of_version(version_file.read_text(encoding="utf-8"))


def runtime_icon_datas(repo_dir: Path) -> list[tuple[str, str]]:
    """Icônes embarquées à plat à côté de l'exécutable (ou dans Contents/Resources sur
    macOS) : la barre système en choisit une d'après le canal courant
    (backend/app/desktop/channel_icon.py). `logo_bobine_icon.png` reste le dernier recours."""
    images = Path(repo_dir) / "Assets" / "Images"
    names = ["logo_bobine_icon.png"] + [f"logo_bobine_icon_{channel}.png" for channel in CHANNELS]
    missing = [name for name in names if not (images / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"Icônes absentes dans Assets/Images : {', '.join(missing)} — lancer scripts/generate_channel_icons.py"
        )
    return [(str(images / name), ".") for name in names]


def stage_icon(source: Path, work_dir: Path, fixed_name: str) -> str:
    """Copie `source` sous un nom FIXE dans `work_dir` et renvoie le chemin copié.

    PyInstaller embarque une icône sous le nom du fichier source ; les outils en aval
    (Info.plist `CFBundleIconFile`, contrôle de la CI) attendent un nom stable quel que
    soit le canal, d'où cette copie."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    destination = work_dir / fixed_name
    shutil.copyfile(source, destination)
    return str(destination)
