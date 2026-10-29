#!/usr/bin/env python3
"""Prepare the pinned Android SDK on Linux builders, validating the NDK before use.

sdkmanager installs the small SDK packages. The NDK ZIP is checked against Google's
repository checksum and size, tested, extracted privately and only then published.
An incomplete existing NDK is retained under a diagnostic name, never reused.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import zipfile

REPOSITORY = "https://dl.google.com/android/repository/"
DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "android/toolchain.json"


def read_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    ndk = config["ndk"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", ndk["version"]):
        raise ValueError("Invalid pinned NDK revision")
    if not re.fullmatch(r"android-ndk-r[0-9]+[a-z]?-linux\.zip", ndk["archive"]):
        raise ValueError("NDK archive must be an official Linux archive basename")
    if ndk["directory"] != ndk["archive"].removesuffix("-linux.zip"):
        raise ValueError("Invalid NDK archive root")
    if not re.fullmatch(r"[a-f0-9]{40}", ndk["sha1"]) or not isinstance(ndk["size"], int) or ndk["size"] <= 0:
        raise ValueError("Missing official NDK checksum/size")
    if not re.fullmatch(r"\d+\.\d+\.\d+", config["build_tools"]):
        raise ValueError("Invalid build-tools version")
    if not 23 <= config["min_sdk"] <= config["target_sdk"] <= config["compile_sdk"] <= 99:
        raise ValueError("Invalid SDK levels")
    if not re.fullmatch(rf"android-{config['compile_sdk']}(\.\d+)?", config["platform"]):
        raise ValueError("Invalid platform directory name")
    return config


def validate_ndk(root: Path, expected: str) -> None:
    properties = (root / "source.properties").read_text(encoding="utf-8")
    revision = re.search(r"^Pkg.Revision\s*=\s*(\S+)\s*$", properties, re.M)
    if revision is None or revision[1] != expected:
        raise ValueError(f"NDK revision differs from {expected}")
    tools = root / "toolchains/llvm/prebuilt/linux-x86_64/bin"
    for name in ("clang", "llvm-readelf", "llvm-strip", "aarch64-linux-android34-clang", "armv7a-linux-androideabi34-clang"):
        tool = tools / name
        if not tool.is_file() or not os.access(tool, os.X_OK):
            raise ValueError(f"NDK tool missing or not executable: {name}")
    subprocess.run([str(tools / "clang"), "--version"], check=True, capture_output=True, timeout=30)
    subprocess.run([str(tools / "llvm-readelf"), "--version"], check=True, capture_output=True, timeout=30)


def download_archive(spec: dict, destination: Path, attempts: int = 3) -> None:
    for attempt in range(1, attempts + 1):
        try:
            digest = hashlib.sha1()  # Google's pinned repository checksum; transport uses HTTPS.
            size = 0
            with urllib.request.urlopen(REPOSITORY + spec["archive"], timeout=120) as response, destination.open("wb") as output:
                while block := response.read(1024 * 1024):
                    size += len(block)
                    if size > spec["size"]:
                        raise ValueError("NDK download exceeds the official archive size")
                    digest.update(block)
                    output.write(block)
            if size != spec["size"] or digest.hexdigest() != spec["sha1"]:
                raise ValueError("NDK download is truncated or its official checksum differs")
            with zipfile.ZipFile(destination) as archive:
                if archive.testzip() is not None:
                    raise zipfile.BadZipFile("NDK ZIP CRC mismatch")
            return
        except (OSError, ValueError, zipfile.BadZipFile, urllib.error.URLError) as exc:
            # Permanent HTTP errors and filesystem failures do not improve on retry.
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in (408, 429, 500, 502, 503, 504):
                raise
            if isinstance(exc, OSError) and getattr(exc, "errno", None) in (13, 28, 30):
                raise
            if attempt == attempts:
                raise
            print(f"NDK acquisition failed ({type(exc).__name__}), attempt {attempt}/{attempts}; retrying verified download.", flush=True)
            time.sleep(attempt * 2)


def extract_archive(source: Path, destination: Path, expected_root: str) -> Path:
    root = (destination / expected_root).resolve()
    with zipfile.ZipFile(source) as archive:
        for member in archive.infolist():
            parts = Path(member.filename).parts
            if not parts or parts[0] != expected_root or ".." in parts or "\\" in member.filename:
                raise ValueError("Unexpected or unsafe NDK ZIP entry")
            target = destination / member.filename
            if not target.resolve().is_relative_to(root):
                raise ValueError("NDK ZIP escapes extraction directory")
            mode = member.external_attr >> 16
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif stat.S_ISLNK(mode):
                link = archive.read(member).decode("utf-8")
                if Path(link).is_absolute() or not (target.parent / link).resolve().is_relative_to(root):
                    raise ValueError("Unsafe NDK ZIP symlink")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(link)
            else:
                if stat.S_IFMT(mode) not in (0, stat.S_IFREG):
                    raise ValueError("Unexpected NDK ZIP file type")
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as content, target.open("wb") as output:
                    shutil.copyfileobj(content, output)
                target.chmod((mode & 0o777) or 0o644)
    return destination / expected_root


def ensure_ndk(sdk: Path, spec: dict, check_only: bool = False) -> Path:
    target = sdk / "ndk" / spec["version"]
    try:
        validate_ndk(target, spec["version"])
        print(f"NDK {spec['version']}: installed toolchain verified.", flush=True)
        return target
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        if check_only:
            raise ValueError(f"Installed NDK is not usable: {exc}") from exc
        print(f"NDK {spec['version']}: acquisition required ({type(exc).__name__}).", flush=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".bobine-ndk-", dir=target.parent) as temporary:
        temporary = Path(temporary)
        archive = temporary / spec["archive"]
        download_archive(spec, archive)
        staged = extract_archive(archive, temporary / "extracted", spec["directory"])
        validate_ndk(staged, spec["version"])
        if target.exists():
            diagnostic = target.with_name(f"{target.name}.invalid-{uuid.uuid4().hex[:8]}")
            target.rename(diagnostic)
            print(f"Incomplete NDK retained for diagnosis: {diagnostic.name}", flush=True)
        staged.rename(target)
    print(f"NDK {spec['version']}: official ZIP and extracted toolchain verified.", flush=True)
    return target


def prepare(sdk: Path, config: dict, check_only: bool, skip_ndk: bool, ndk_only: bool) -> dict[str, str]:
    if sys.platform != "linux":
        raise ValueError("This SDK preparation targets the Linux Android CI builders")
    build_tools = sdk / "build-tools" / config["build_tools"]
    if not ndk_only:
        if not check_only:
            manager = shutil.which("sdkmanager")
            if manager is None:
                raise ValueError("sdkmanager is missing")
            subprocess.run([manager, f"--sdk_root={sdk}", f"platforms;{config['platform']}", f"build-tools;{config['build_tools']}"], check=True)
        if not (sdk / f"platforms/{config['platform']}/android.jar").is_file():
            raise ValueError("Pinned Android platform is missing")
        for name in ("aapt2", "apksigner", "zipalign"):
            path = build_tools / name
            if not path.is_file() or not os.access(path, os.X_OK):
                raise ValueError(f"Pinned Android build tool missing: {name}")
        subprocess.run([str(build_tools / "aapt2"), "version"], check=True, capture_output=True, timeout=30)
        subprocess.run([str(build_tools / "apksigner"), "version"], check=True, capture_output=True, timeout=30)
    result = {"BOBINE_ANDROID_BUILD_TOOLS": str(build_tools)}
    if not skip_ndk:
        result["ANDROID_NDK_HOME"] = str(ensure_ndk(sdk, config["ndk"], check_only))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--sdk-root", type=Path, default=os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT"))
    parser.add_argument("--check", action="store_true")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--skip-ndk", action="store_true")
    group.add_argument("--ndk-only", action="store_true")
    args = parser.parse_args()
    if args.sdk_root is None:
        parser.error("ANDROID_HOME or --sdk-root is required")
    result = prepare(args.sdk_root.resolve(), read_config(args.config), args.check, args.skip_ndk, args.ndk_only)
    if env_file := os.environ.get("GITHUB_ENV"):
        with open(env_file, "a", encoding="utf-8") as output:
            for key, value in result.items():
                if "\n" in value or "\r" in value:
                    raise ValueError("Invalid SDK path for GITHUB_ENV")
                output.write(f"{key}={value}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        raise SystemExit(f"Android SDK preparation failed: {exc}") from exc
