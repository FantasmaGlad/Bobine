#!/usr/bin/env python3
"""Build bobine-media for the host (or a target), check it, and stage it in a directory.

This is the single step the packaging jobs call to put the audio component next to
BobineBackend (Linux .deb, Windows) or inside the macOS bundle (Contents/MacOS). The
component is optional for the application: a package built without it works, and the
`media_native` setting then reports it as absent. Android uses
scripts/ci/build-media-android.sh instead.

`--check PATH` only starts an already installed executable (for example the one a package
installed) and applies the same `hello` and exit-on-EOF checks.

After copying, the staged executable is started and must answer `hello` with protocol
version 1 and exit with status 0 when its stdin closes; a cross-compiled executable
cannot run here, so use --no-smoke for it and run the check on the target.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[2]
EXE = "bobine-media.exe" if os.name == "nt" else "bobine-media"


def smoke(binary, timeout=5.0):
    """Start the executable, require a v1 `hello` answer, then a clean exit on EOF."""
    process = subprocess.Popen([str(binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    answers = queue.Queue()
    threading.Thread(target=lambda: answers.put(process.stdout.readline()), daemon=True).start()
    try:
        process.stdin.write(b'{"jsonrpc":"2.0","id":1,"method":"hello","params":{}}\n')
        process.stdin.flush()
        try:
            line = answers.get(timeout=timeout)
        except queue.Empty:
            raise RuntimeError("no answer to hello before the deadline") from None
        reply = json.loads(line)
        result = reply.get("result", {})
        if reply.get("id") != 1 or result.get("protocol_version") != 1:
            raise RuntimeError(f"unexpected hello answer: {reply}")
        process.stdin.close()
        if process.wait(timeout=timeout) != 0:
            raise RuntimeError(f"exit status {process.returncode} after EOF")
        return result
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", type=Path, help="start this executable, check hello and exit on EOF, print the summary")
    parser.add_argument("--dest", type=Path, help="existing directory that receives the executable")
    parser.add_argument("--target", help="Rust target triple for a cross build")
    parser.add_argument("--skip-build", action="store_true", help="stage the executable that is already built")
    parser.add_argument("--no-smoke", action="store_true", help="do not run the staged executable (cross build)")
    args = parser.parse_args()
    if args.check is not None:
        hello = smoke(args.check)
        print(json.dumps({"path": str(args.check), "bytes": args.check.stat().st_size, "protocol_version": hello["protocol_version"],
                          "binary_version": hello["binary_version"], "formats": hello["formats"]}, indent=2))
        return
    if args.dest is None or not args.dest.is_dir():
        parser.error("--dest must be an existing directory (or use --check)")
    manifest = ROOT / "media" / "Cargo.toml"
    if not args.skip_build:
        command = ["cargo", "build", "--release", "--locked", "--manifest-path", str(manifest)]
        if args.target:
            command += ["--target", args.target]
        subprocess.run(command, check=True)
    release = ROOT / "media" / "target" / (args.target or "") / "release"
    built = release / ("bobine-media.exe" if (args.target or "").endswith("windows-msvc") or (not args.target and os.name == "nt") else "bobine-media")
    if not built.is_file():
        sys.exit(f"Executable not found: {built}")
    staged = args.dest / built.name
    shutil.copy2(built, staged)
    staged.chmod(0o755)
    summary = {"path": str(staged), "bytes": staged.stat().st_size, "sha256": hashlib.sha256(staged.read_bytes()).hexdigest()}
    if not args.no_smoke:
        hello = smoke(staged)
        summary.update({"protocol_version": hello["protocol_version"], "binary_version": hello["binary_version"],
                        "formats": hello["formats"]})
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
