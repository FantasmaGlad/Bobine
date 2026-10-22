#!/usr/bin/env python3
"""Run the native audio component on an Android device (adb) or locally, and check it.

The executable is pushed to /data/local/tmp (never installed as an application, nothing else
on the device is touched), started once with a file of JSON-RPC requests on its standard
input, and its answers are compared with those of a reference executable run on this machine
(`--reference`, normally the desktop build): same fields, same duration, same cover bytes.
Wall time of the whole batch, per-file time, the executable's peak resident memory (VmHWM)
and its size are reported. Files come from a corpus made by generate.py.

    device_probe.py <corpus> --binary android/app/src/main/jniLibs/armeabi-v7a/libbobine_media.so \\
        --reference media/target/release/bobine-media --adb 192.168.1.13:5555 --output report.json

`--local` runs `--binary` on this machine instead of through adb (used to test the script).
This measures the component alone on that device, not an import: the device's Python, ffmpeg
and storage are not involved.
"""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

REMOTE_DIR = "/data/local/tmp/bobine-media-probe"


class Local:
    name = "local"

    def __init__(self, binary):
        self.binary = Path(binary)
        self.folder = None

    def info(self):
        return {"abi": "host", "model": "local", "android": None}

    def prepare(self, files, requests):
        self.folder = Path(tempfile.mkdtemp(prefix="bobine-device-probe-local-", dir="/var/tmp" if os.name != "nt" else None))
        for source, remote in files:
            (self.folder / remote).write_bytes(Path(source).read_bytes())
        self.requests = requests.replace(f"{REMOTE_DIR}/media/".encode(), f"{self.folder}/".encode())

    def run(self):
        import resource
        started = time.perf_counter()
        done = subprocess.run([str(self.binary)], input=self.requests, capture_output=True, timeout=600)
        peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        return done.stdout, time.perf_counter() - started, peak, done.returncode

    def cleanup(self):
        if self.folder is not None:
            for item in self.folder.glob("*"):
                item.unlink()
            self.folder.rmdir()


class Adb:
    name = "adb"

    def __init__(self, binary, target, timeout=600):
        self.binary, self.target, self.timeout = Path(binary), target, timeout

    def _adb(self, *args, **kwargs):
        command = ["adb", *(["-s", self.target] if self.target else []), *args]
        return subprocess.run(command, capture_output=True, text=kwargs.pop("text", True), timeout=self.timeout, **kwargs)

    def shell(self, script):
        done = self._adb("shell", script)
        return done.stdout, done.returncode

    def info(self):
        abi, _ = self.shell("getprop ro.product.cpu.abilist")
        model, _ = self.shell("getprop ro.product.model")
        release, _ = self.shell("getprop ro.build.version.release")
        return {"abi": abi.strip(), "model": model.strip(), "android": release.strip()}

    def prepare(self, files, requests):
        self.shell(f"rm -rf {REMOTE_DIR}; mkdir -p {REMOTE_DIR}/media")
        self._push(self.binary, f"{REMOTE_DIR}/bobine-media")
        self.shell(f"chmod 755 {REMOTE_DIR}/bobine-media")
        for source, remote in files:
            self._push(source, f"{REMOTE_DIR}/media/{remote}")
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.write(requests)
        handle.close()
        self._push(handle.name, f"{REMOTE_DIR}/requests.jsonl")
        os.unlink(handle.name)

    def _push(self, source, remote):
        done = self._adb("push", str(source), remote)
        if done.returncode:
            raise RuntimeError(f"adb push failed for {Path(source).name}: {done.stderr.strip()[-200:]}")

    def run(self):
        # The executable reads the file of requests, exits at its end of file; the shell loop reads
        # the peak resident memory (VmHWM) of its process until it disappears.
        script = (f"cd {REMOTE_DIR}; s=$(date +%s%N); ./bobine-media < requests.jsonl > answers.jsonl & p=$!; peak=0; "
                  "while [ -d /proc/$p ]; do h=$(grep VmHWM /proc/$p/status 2>/dev/null | tr -dc 0-9); "
                  "[ -n \"$h\" ] && peak=$h; done; wait $p; code=$?; e=$(date +%s%N); echo \"RESULT $code $peak $(( (e - s) / 1000000 ))\"")
        started = time.perf_counter()
        out, _ = self.shell(script)
        wall = time.perf_counter() - started
        line = next((item for item in out.splitlines() if item.startswith("RESULT ")), None)
        if line is None:
            raise RuntimeError(f"unexpected shell output: {out[-200:]}")
        _, code, peak_kib, device_ms = line.split()
        answers = self._adb("exec-out", f"cat {REMOTE_DIR}/answers.jsonl", text=False).stdout
        return answers, int(device_ms) / 1000, int(peak_kib), int(code)

    def cleanup(self):
        self.shell(f"rm -rf {REMOTE_DIR}")


def build_requests(entries):
    lines = [json.dumps({"jsonrpc": "2.0", "id": 1, "method": "hello", "params": {}})]
    identifier = 2
    plan = []
    for local_name, remote in entries:
        for method, profile in (("probe_audio", "radio-v1"), ("probe_audio", "course-duration-v1"), ("extract_cover", "radio-v1")):
            path = f"{REMOTE_DIR}/media/{remote}"
            lines.append(json.dumps({"jsonrpc": "2.0", "id": identifier, "method": method,
                                     "params": {"path": path, "profile": profile}}, ensure_ascii=False))
            plan.append((identifier, local_name, method, profile))
            identifier += 1
    return ("\n".join(lines) + "\n").encode("utf-8"), plan


def parse(answers):
    result = {}
    for line in answers.decode("utf-8").splitlines():
        if line.strip():
            message = json.loads(line)
            result[message["id"]] = message
    return result


def comparable(message):
    """Drop what legitimately differs between the two machines: nothing but the path-free payload."""
    if "error" in message:
        return {"error": message["error"]["data"]["reason"]}
    return message["result"]


def select(corpus, count):
    manifest = json.loads((corpus / "manifest.json").read_bytes())
    entries = [entry for entry in manifest["entries"] if entry["type"] != "corrupt"]
    base = [entry for entry in entries if "scale" not in entry["id"]]
    scaled = [entry for entry in entries if "scale" in entry["id"]]
    chosen = (base + scaled)[:count] if count else base + scaled
    return [(corpus / entry["path"], f"{index:04d}{Path(entry['path']).suffix.lower()}", entry["id"]) for index, entry in enumerate(chosen)]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--binary", type=Path, required=True, help="executable for the device (or the host with --local)")
    parser.add_argument("--reference", type=Path, required=True, help="desktop executable whose answers are the expected ones")
    parser.add_argument("--adb", help="adb serial or host:port (omit for the only device)")
    parser.add_argument("--local", action="store_true", help="run --binary on this machine")
    parser.add_argument("--count", type=int, default=0, help="use the first N non-corrupt files (default: all)")
    parser.add_argument("--repeats", type=int, default=3, help="batches per measurement")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    corpus = args.corpus.resolve()
    chosen = select(corpus, args.count)
    requests, plan = build_requests([(entry_id, remote) for _, remote, entry_id in chosen])
    # The reference runs on the same files, copied (the component refuses symbolic links) under the
    # names the device receives.
    reference_dir = Path(tempfile.mkdtemp(prefix="bobine-device-probe-", dir="/var/tmp" if os.name != "nt" else None))
    try:
        for source, remote, _ in chosen:
            (reference_dir / remote).write_bytes(Path(source).read_bytes())
        reference_requests = requests.replace(f"{REMOTE_DIR}/media/".encode(), f"{reference_dir}/".encode())
        expected = parse(subprocess.run([str(args.reference.resolve())], input=reference_requests,
                                        capture_output=True, timeout=600).stdout)
    finally:
        for item in reference_dir.glob("*"):
            item.unlink()
        reference_dir.rmdir()
    runner = Local(args.binary) if args.local else Adb(args.binary, args.adb)
    report = {"schema_version": 1, "device": runner.info(), "files": len(chosen), "requests": len(plan),
              "binary_bytes": args.binary.stat().st_size, "runs": []}
    try:
        runner.prepare([(source, remote) for source, remote, _ in chosen], requests)
        for _ in range(args.repeats):
            answers, seconds, peak_kib, code = runner.run()
            actual = parse(answers)
            differences = []
            for identifier, entry_id, method, profile in plan:
                if identifier not in actual:
                    differences.append({"id": entry_id, "method": method, "problem": "no answer"})
                elif comparable(actual[identifier]) != comparable(expected[identifier]):
                    differences.append({"id": entry_id, "method": method, "profile": profile,
                                        "device": comparable(actual[identifier]), "reference": comparable(expected[identifier])})
            hello = actual.get(1, {}).get("result", {})
            report["runs"].append({"exit_status": code, "batch_seconds": seconds, "ms_per_request": seconds * 1000 / len(plan),
                                   "peak_rss_kib": peak_kib, "answers": len(actual), "differences": differences,
                                   "hello_protocol": hello.get("protocol_version"), "hello_version": hello.get("binary_version")})
            print(f"batch {seconds:.3f} s, {len(actual)} answers, peak {peak_kib} KiB, {len(differences)} differences, exit {code}", file=sys.stderr)
    finally:
        runner.cleanup()
    batches = [run["batch_seconds"] for run in report["runs"]]
    report["summary"] = {"median_batch_seconds": statistics.median(batches),
                         "median_ms_per_request": statistics.median(run["ms_per_request"] for run in report["runs"]),
                         "peak_rss_kib_max": max(run["peak_rss_kib"] or 0 for run in report["runs"]),
                         "differences": sum(len(run["differences"]) for run in report["runs"]),
                         "clean_exit": all(run["exit_status"] == 0 for run in report["runs"])}
    report["passed"] = report["summary"]["differences"] == 0 and report["summary"]["clean_exit"] and \
        all(run["answers"] == len(plan) + 1 for run in report["runs"])
    with args.output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"device": report["device"], "passed": report["passed"], "summary": report["summary"]}, indent=2))
    if not report["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
