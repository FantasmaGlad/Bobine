#!/usr/bin/env python3
"""Check package transitions with dpkg, rpm or libalpm's real comparator."""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys

SPEC = importlib.util.spec_from_file_location("package_channels", Path(__file__).resolve().parents[2] / "backend/app/release_channel.py")
registry = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = registry
SPEC.loader.exec_module(registry)


def native(base, channel="stable", build=None, family="debian"):
    version = registry.package_version(base, channel, build)
    if family == "debian":
        return version.debian
    if family == "rpm":
        return f"{version.base}-{version.rpm_release}"
    return f"{version.arch_version}-1"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", choices=("debian", "rpm", "arch"), required=True)
    family = parser.parse_args().family
    def value(channel, build=None, base="5.0.6"):
        return native(base, channel, build, family)
    pairs = [
        (value("stable", base="5.0.5"), value("canary", "1")),
        (value("canary", "9"), value("canary", "10")),
        (value("canary", "999"), value("beta", "1")),
        (value("beta", "9"), value("beta", "10")),
        (value("beta", "999"), value("stable")),
        (value("stable"), value("canary", "1", "5.0.7")),
    ]
    legacy = {"debian": "5.0.5+canary.999", "rpm": "5.0.5-1.canary.999", "arch": "5.0.5-1.999"}
    pairs.append((legacy[family], value("canary", "1")))
    for before, after in pairs:
        if family == "debian":
            subprocess.run(["dpkg", "--compare-versions", before, "lt", after], check=True)
        else:
            command = ["vercmp", before, after] if family == "arch" else ["rpm", "--eval", f'%{{lua:print(rpm.vercmp("{before}", "{after}"))}}']
            comparison = subprocess.check_output(command, text=True).strip()
            if comparison != "-1":
                raise SystemExit(f"Invalid {family} upgrade: {before} -> {after} ({comparison})")
        print(f"{family}: {before} < {after}")


if __name__ == "__main__":
    main()
