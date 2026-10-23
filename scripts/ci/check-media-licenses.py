#!/usr/bin/env python3
"""Check that every crate shipped inside bobine-media is under a permissive license.

The executable is distributed with the AGPL-3.0-or-later application. Each crate of
its normal and build dependency graph must offer at least one license from ALLOWED
(an `A OR B` expression needs one allowed side, `A AND B` needs both). Development
dependencies are not shipped and are ignored. Cargo.lock pins the exact graph; this
check runs with --locked so it cannot silently resolve other versions.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ALLOWED = frozenset((
    "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Zlib", "0BSD", "Unlicense",
    "Unicode-3.0", "CC0-1.0", "AGPL-3.0-or-later",
))


def satisfied(expression, allowed=ALLOWED):
    """Evaluate a small SPDX expression (identifiers, AND, OR, parentheses)."""
    tokens = re.findall(r"\(|\)|[^\s()]+", expression.replace("/", " OR "))
    position = 0

    def parse_or():
        nonlocal position
        value = parse_and()
        while position < len(tokens) and tokens[position] == "OR":
            position += 1
            right = parse_and()
            value = value or right
        return value

    def parse_and():
        nonlocal position
        value = parse_atom()
        while position < len(tokens) and tokens[position] == "AND":
            position += 1
            right = parse_atom()
            value = value and right
        return value

    def parse_atom():
        nonlocal position
        if position >= len(tokens):
            raise ValueError(f"Incomplete license expression: {expression!r}")
        token = tokens[position]
        position += 1
        if token == "(":
            value = parse_or()
            if position >= len(tokens) or tokens[position] != ")":
                raise ValueError(f"Unbalanced license expression: {expression!r}")
            position += 1
            return value
        if token in ("AND", "OR", ")"):
            raise ValueError(f"Unexpected {token!r} in {expression!r}")
        return token in allowed

    result = parse_or()
    if position != len(tokens):
        raise ValueError(f"Trailing tokens in {expression!r}")
    return result


def shipped_packages(manifest, offline):
    command = ["cargo", "metadata", "--locked", "--format-version", "1", "--manifest-path", str(manifest)]
    if offline:
        command.append("--offline")
    metadata = json.loads(subprocess.run(command, capture_output=True, text=True, check=True, timeout=300).stdout)
    packages = {package["id"]: package for package in metadata["packages"]}
    nodes = {node["id"]: node for node in metadata["resolve"]["nodes"]}
    pending, seen = [metadata["resolve"]["root"]], set()
    while pending:
        identity = pending.pop()
        if identity in seen:
            continue
        seen.add(identity)
        for dependency in nodes[identity]["deps"]:
            if any(kind["kind"] in (None, "build") for kind in dependency["dep_kinds"]):
                pending.append(dependency["pkg"])
    return sorted((packages[identity] for identity in seen), key=lambda package: (package["name"], package["version"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "media" / "Cargo.toml")
    parser.add_argument("--offline", action="store_true", help="resolve from the local Cargo cache only")
    args = parser.parse_args()
    failures = []
    for package in shipped_packages(args.manifest, args.offline):
        license_expression = package.get("license")
        ok = bool(license_expression) and satisfied(license_expression)
        print(f"{'ok  ' if ok else 'FAIL'} {package['name']} {package['version']}: {license_expression or 'no license field'}")
        if not ok:
            failures.append(package["name"])
    if failures:
        sys.exit("License check failed for: " + ", ".join(failures))


if __name__ == "__main__":
    main()
