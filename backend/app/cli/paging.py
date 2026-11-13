from __future__ import annotations

import argparse

def _positive(raw: str) -> int:
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError("entier positif attendu")
    return value


def _natural(raw: str) -> int:
    value = int(raw)
    if value < 0:
        raise argparse.ArgumentTypeError("entier positif ou nul attendu")
    return value


def paged(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--limit", type=_positive, help="taille de page (total dans X-Total-Count)")
    parser.add_argument("--offset", type=_natural, help="rang du premier élément")
    return parser


def window(args: argparse.Namespace) -> dict:
    given = {"limit": getattr(args, "limit", None), "offset": getattr(args, "offset", None)}
    return {key: value for key, value in given.items() if value is not None}
