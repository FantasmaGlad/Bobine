#!/usr/bin/env python3
"""Require signed AABs with exactly the production ABI set and native components."""
import argparse
from pathlib import Path
import subprocess
import zipfile


def verify(path: Path, tv: bool):
    expected = {"arm64-v8a", "armeabi-v7a"} if tv else {"arm64-v8a"}
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        entries = set(names)
        if len(entries) != len(names):
            raise ValueError(f"Duplicate ZIP entries in {path}")
        if "base/manifest/AndroidManifest.xml" not in entries:
            raise ValueError(f"Missing Android bundle manifest in {path}")
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
    result = subprocess.run(["jarsigner", "-J-Duser.language=en", "-verify", "-strict", str(path)],
                            text=True, capture_output=True)
    # Exit 4 is expected for the self-signed upload certificate without a CA
    # trust store. Other strict flags (unsigned entries, invalid key usage) and
    # signature/digest errors must fail. Plain -verify also succeeds when an
    # attacker adds unsigned files, so its "jar verified" message is insufficient.
    verified = any(line in ("jar verified.", "jar verified, with signer errors.")
                   for line in result.stdout.splitlines())
    if result.returncode not in (0, 4) or not verified:
        raise ValueError(f"Bundle signature or signed entry coverage not verified: {path}")
    print(f"{path}: signed AAB, expected ABI set, Python and native components verified")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--tv", action="store_true")
    args = parser.parse_args()
    verify(args.bundle, args.tv)


if __name__ == "__main__":
    main()
