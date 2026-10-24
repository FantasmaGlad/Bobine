#!/usr/bin/env python3
"""Propage le registre des canaux (backend/app/release_channel.py) vers les langages qui ne
peuvent pas l'importer. Aucun de ces fichiers ne se modifie à la main.

    python3 scripts/sync_release_channels.py            # écrit les fichiers générés
    python3 scripts/sync_release_channels.py --check    # échoue si l'un d'eux est périmé

  - android/release-channels.json : lu par android/app/build.gradle.kts (canal du build, champs
    BuildConfig) ;
  - frontend/src/lib/releaseChannels.generated.ts : lu par frontend/src/lib/releaseChannel.ts.

Les consommateurs écrits à la main (ressources Android, écran de démarrage Kotlin) sont vérifiés
contre le registre par backend/tests/test_release_channels_wiring.py.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
ANDROID_JSON = REPO_DIR / "android" / "release-channels.json"
FRONTEND_TS = REPO_DIR / "frontend" / "src" / "lib" / "releaseChannels.generated.ts"
REGISTRY_PATH = REPO_DIR / "backend" / "app" / "release_channel.py"


def load_registry():
    spec = importlib.util.spec_from_file_location("bobine_release_channel", REGISTRY_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # requis par @dataclass
    spec.loader.exec_module(module)
    return module


def render_android_json(registry) -> str:
    payload = {
        "_comment": "Généré par scripts/sync_release_channels.py depuis backend/app/release_channel.py — ne pas modifier.",
        "default": registry.DEFAULT_CHANNEL,
        "channels": [
            {"id": c.id, "versionSuffix": c.version_suffix, "releaseTag": c.release_tag} for c in registry.CHANNELS
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def render_frontend_ts(registry) -> str:
    ids = ", ".join(f'"{channel_id}"' for channel_id in registry.CHANNEL_IDS)
    rolling = ", ".join(f'"{channel_id}"' for channel_id in registry.ROLLING_CHANNEL_IDS)
    return (
        "// Généré par scripts/sync_release_channels.py depuis backend/app/release_channel.py.\n"
        "// Ne pas modifier à la main : ajouter un canal commence dans le registre du backend.\n"
        f"export const RELEASE_CHANNELS = [{ids}] as const;\n"
        f'export const DEFAULT_RELEASE_CHANNEL = "{registry.DEFAULT_CHANNEL}" as const;\n'
        f"export const ROLLING_RELEASE_CHANNELS = [{rolling}] as const;\n"
    )


def outputs() -> dict[Path, str]:
    registry = load_registry()
    return {ANDROID_JSON: render_android_json(registry), FRONTEND_TS: render_frontend_ts(registry)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="échoue si un fichier généré est absent ou périmé")
    args = parser.parse_args(argv)
    expected = outputs()
    if args.check:
        stale = [p for p, text in expected.items() if not p.exists() or p.read_text(encoding="utf-8") != text]
        for path in stale:
            print(f"périmé : {path.relative_to(REPO_DIR)} — relancer scripts/sync_release_channels.py", file=sys.stderr)
        return 1 if stale else 0
    for path, text in expected.items():
        path.write_text(text, encoding="utf-8")
        print(f"écrit : {path.relative_to(REPO_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
