"""Canal du build et icônes par canal pour les outils de construction.

Aucune règle n'est écrite ici : le registre des canaux et la règle « canal d'un build d'après
le suffixe de VERSION » vivent dans backend/app/release_channel.py (source unique), chargé par
son chemin (il n'importe que la bibliothèque standard). Ce module en est l'adaptateur pour :

  - les `.spec` PyInstaller (windows, macos, linux) :
        sys.path.insert(0, str(SPEC_DIR.parent / "common")); import channel
  - les scripts shell de paquetage, via la ligne de commande :
        python3 packaging/common/channel.py channel-of-version 5.0.5+canary.42   ->  canary
        python3 packaging/common/channel.py build-channel [dépôt]                ->  canal de VERSION
        python3 packaging/common/channel.py split-version 5.0.5+canary.42        ->  « base canal numéro »
        python3 packaging/common/channel.py is-channel canary                    ->  code 0 si c'est un canal
        python3 packaging/common/channel.py is-rolling beta                      ->  code 0 si c'est un canal rolling

Le canal du BUILD fixe l'icône de l'exécutable / de l'installeur / du bundle. Il est distinct du
canal choisi à l'exécution (barre système, logo, favicon), pour lequel les icônes de TOUS les
canaux sont embarquées (`runtime_icon_datas`).
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from functools import lru_cache
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=None)
def _registry(repo_dir: str):
    path = Path(repo_dir) / "backend" / "app" / "release_channel.py"
    spec = importlib.util.spec_from_file_location("bobine_release_channel", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # requis par @dataclass pour résoudre ses annotations
    spec.loader.exec_module(module)
    return module


def channels(repo_dir: Path = REPO_DIR) -> tuple[str, ...]:
    return _registry(str(repo_dir)).CHANNEL_IDS


def channel_of_version(version: str, repo_dir: Path = REPO_DIR) -> str:
    return _registry(str(repo_dir)).build_channel_of_version(version)


def build_channel(repo_dir: Path = REPO_DIR) -> str:
    """Canal du build en cours, d'après le fichier VERSION (la CI y ajoute le suffixe avant PyInstaller)."""
    registry = _registry(str(repo_dir))
    version_file = Path(repo_dir) / "VERSION"
    if not version_file.exists():
        return registry.DEFAULT_CHANNEL
    return registry.build_channel_of_version(version_file.read_text(encoding="utf-8").strip())


def runtime_icon_datas(repo_dir: Path = REPO_DIR) -> list[tuple[str, str]]:
    """Icônes embarquées à plat à côté de l'exécutable (ou dans Contents/Resources sur macOS) :
    la barre système en choisit une d'après le canal courant (backend/app/desktop/channel_icon.py).
    `logo_bobine_icon.png` reste le dernier recours."""
    images = Path(repo_dir) / "Assets" / "Images"
    names = ["logo_bobine_icon.png"] + [f"logo_bobine_icon_{channel}.png" for channel in channels(repo_dir)]
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


def _main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "channel-of-version":
        print(channel_of_version(argv[2]))
        return 0
    if argv[1:2] == ["build-channel"] and len(argv) in (2, 3):
        print(build_channel(Path(argv[2]) if len(argv) == 3 else REPO_DIR))
        return 0
    if len(argv) == 3 and argv[1] == "split-version":
        try:
            parsed = _registry(str(REPO_DIR)).parse_package_version(argv[2])
        except ValueError as exc:
            print(f"Erreur: {exc}", file=sys.stderr)
            return 1
        print(parsed.base, parsed.channel, parsed.build or "")
        return 0
    if len(argv) == 3 and argv[1] == "is-channel":
        return 0 if _registry(str(REPO_DIR)).normalize(argv[2]) == argv[2] else 1
    if len(argv) == 3 and argv[1] == "is-rolling":
        return 0 if argv[2] in _registry(str(REPO_DIR)).ROLLING_CHANNEL_IDS else 1
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
