#!/usr/bin/env python3
"""Validate a Stable Play version against the checked-out product sources."""
import argparse
import os
from pathlib import Path
import re
import subprocess


def resolve(tag, source_version):
    if not re.fullmatch(r"V\d+\.\d+\.\d+", tag):
        raise ValueError("Google Play requires a Stable tag Vx.y.z")
    version = tag[1:]
    if version != source_version.strip():
        raise ValueError("Play tag differs from VERSION in the selected source_ref")
    return version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path.cwd())
    args = parser.parse_args()
    version = resolve(os.environ["PLAY_TAG"], (args.source / "VERSION").read_text())
    count = subprocess.check_output(["git", "rev-list", "--count", "HEAD"], cwd=args.source, text=True).strip()
    revision = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=args.source, text=True).strip()
    if not count.isdecimal() or int(count) < 1:
        raise ValueError("Invalid Android versionCode")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write(f"version_name={version}\nversion_code={count}\ncommit_short={revision}\n")


if __name__ == "__main__":
    try:
        main()
    except (KeyError, OSError, ValueError, subprocess.SubprocessError) as exc:
        raise SystemExit(f"Play version resolution failed: {exc}") from exc
