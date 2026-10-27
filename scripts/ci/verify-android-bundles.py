#!/usr/bin/env python3
"""Require signed AABs with exactly the production ABI set and native components."""
import argparse
from pathlib import Path
import subprocess
import zipfile


def verify(path: Path, tv: bool):
    expected = {"arm64-v8a", "armeabi-v7a"} if tv else {"arm64-v8a"}
    with zipfile.ZipFile(path) as archive:
        entries = set(archive.namelist())
        actual = {name.split("/")[2] for name in entries if name.startswith("base/lib/") and name.endswith(".so")}
        if actual != expected:
            raise ValueError(f"Unexpected ABI set in {path}: {sorted(actual)}")
        for abi in expected:
            prefix = f"base/lib/{abi}/"
            for library in ("libffmpeg.so", "libffprobe.so", "libbobine_media.so"):
                if prefix + library not in entries:
                    raise ValueError(f"Missing {prefix + library} in {path}")
            if not any(name.startswith(prefix + "libpython3.") for name in entries):
                raise ValueError(f"Missing embedded Python for {abi} in {path}")
        if not any(name.startswith("META-INF/") and name.endswith((".RSA", ".EC", ".DSA")) for name in entries):
            raise ValueError(f"Unsigned bundle: {path}")
    result = subprocess.run(["jarsigner", "-J-Duser.language=en", "-verify", str(path)], check=True, text=True, capture_output=True)
    # jarsigner can return status 0 for an unsigned archive. Require a verified signature.
    if "jar verified." not in result.stdout:
        raise ValueError(f"Bundle signature not verified: {path}")
    print(f"{path}: signed AAB, expected ABI set, Python and native components verified")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--tv", action="store_true")
    args = parser.parse_args()
    verify(args.bundle, args.tv)


if __name__ == "__main__":
    main()
