#!/usr/bin/env python3
"""Écrit la référence de la commande bobine et de l'API (docs/reference/), ou vérifie qu'elle est à jour (--check)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import warnings
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
TARGET = REPO_DIR / "docs" / "reference"


def _render(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def build() -> dict[str, str]:
    sys.path.insert(0, str(REPO_DIR / "backend"))
    warnings.filterwarnings("ignore")
    logging.disable(logging.CRITICAL)
    from app.cli import build_parser
    from app.main import app
    from app.reference.api import api_reference
    from app.reference.cli import cli_reference

    return {"cli.json": _render(cli_reference(build_parser())), "api.json": _render(api_reference(app.openapi()))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = []
    for name, content in build().items():
        path = TARGET / name
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                stale.append(name)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"écrit : {path.relative_to(REPO_DIR)}")
    if stale:
        print(f"périmé : {', '.join(stale)} : relancer scripts/export_reference.py", file=sys.stderr)
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
