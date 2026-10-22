#!/usr/bin/env python3
"""End-to-end import benchmark: reference path (ffprobe/ffmpeg) against bobine-media.

Each run imports the same staged files through the real importers (radio or audio
course), in a fresh child Python process with an isolated data directory, a new
SQLite database and a copy of the corpus. The parent samples the whole process tree
while the child works. Nothing touches an installed Bobine, a real library or the
network, and the corpus itself is never modified (importers move files, so every
run stages its own copy).

Reported per run: wall time, CPU time of the child and of every reaped sub-process
(ffprobe, ffmpeg, the native component), peak resident memory (largest single
process and sum over the tree; proportional set size on Linux when readable), peak
number of processes, bytes written to the data directory, and the imported rows.
After the runs the rows of both modes are compared field by field, so a faster
result is never reported without proving that the library it produced is the same.

Scope and honesty: figures are measured on the machine that runs the script and
say nothing about any other device. `--cache cold` is a best effort
(`posix_fadvise(DONTNEED)` on the staged files; it cannot drop caches without root
and is a no-op on Windows/macOS). Cancellation and concurrent playback are not
exercised here.

    backend/.venv/bin/python scripts/media-bench/generate.py /var/tmp/corpus --scale 540
    backend/.venv/bin/python scripts/media-bench/import_bench.py /var/tmp/corpus \
        --binary media/target/release/bobine-media --output /var/tmp/corpus/import-bench.json
"""
import argparse
import base64
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cover_equivalence  # noqa: E402
MODES = ("reference", "native")
DROP_SYSTEM_CACHE = False


def _tree_size(path):
    return sum(item.stat().st_size for item in Path(path).rglob("*") if item.is_file())


def _cpu(usage):
    return usage.ru_utime + usage.ru_stime


def _peak_kb(usage):
    # ru_maxrss is KiB on Linux and bytes on macOS.
    return usage.ru_maxrss / 1024 if sys.platform == "darwin" else usage.ru_maxrss


# --------------------------------------------------------------------------- child

def worker(spec):
    """Runs inside the child: import the staged files and print one JSON object."""
    import resource
    sys.path.insert(0, str(ROOT / "backend"))
    from app.database import SessionLocal, init_db
    from app.utils import media_metadata, media_sidecar, radio_utils

    counts = Counter()
    original_probe, original_reference = media_metadata._probe, radio_utils.extract_radio_metadata
    original_cover = radio_utils.extract_embedded_cover

    def probe(file_path, profile):
        value = original_probe(file_path, profile)
        counts["native_probe" if value is not None else "probe_returned_none"] += 1
        return value

    def reference_metadata(file_path):
        counts["reference_metadata"] += 1
        return original_reference(file_path)

    def reference_cover(*args):
        counts["reference_cover"] += 1
        return original_cover(*args)

    media_metadata._probe = probe
    media_metadata.radio_utils.extract_radio_metadata = reference_metadata
    media_metadata.radio_utils.extract_embedded_cover = reference_cover

    init_db()
    paths = [str(Path(spec["staging"]) / name) for name in spec["names"]]
    before_children = resource.getrusage(resource.RUSAGE_CHILDREN)
    before_self = resource.getrusage(resource.RUSAGE_SELF)
    started = time.perf_counter()
    if spec["kind"] == "radio":
        from app.utils.radio_importer import import_radio_tracks_from_files
        imported = import_radio_tracks_from_files(paths)
    else:
        from app.utils.audio_importer import import_audio_course_from_files
        import_audio_course_from_files(paths, "Benchmark course")
        imported = []
    wall = time.perf_counter() - started
    rows = []
    covers = []
    if spec["kind"] == "radio":
        # Rows are created one after the other in staging order, so the id order is the input order:
        # the position identifies the same source file in both modes.
        for position, track in enumerate(sorted(imported, key=lambda item: item.id)):
            row = {key: getattr(track, key) for key in ("title", "artist", "album", "album_artist", "track_number",
                                                        "disc_number", "year", "genre", "duration_seconds")}
            row["position"] = position
            rows.append(row)
            if track.cover_path:
                # The native cover pipeline is judged by cover_equivalence, not by identical bytes.
                covers.append({"file": str(position), "data": base64.b64encode(Path(track.cover_path).read_bytes()).decode("ascii")})
    else:
        db = SessionLocal()
        try:
            from app.models import AudioTrack
            for track in db.query(AudioTrack).all():
                rows.append({"title": track.title, "number": track.number, "duration_seconds": track.duration_seconds})
        finally:
            db.close()
    # Reap the long-lived native component before reading child CPU time.
    media_sidecar.close_current_media_client()
    after_children = resource.getrusage(resource.RUSAGE_CHILDREN)
    after_self = resource.getrusage(resource.RUSAGE_SELF)
    print(json.dumps({
        "wall_s": wall, "imported": len(rows),
        "cpu_self_s": _cpu(after_self) - _cpu(before_self),
        "cpu_children_s": _cpu(after_children) - _cpu(before_children),
        "maxrss_self_kb": _peak_kb(after_self), "maxrss_largest_child_kb": _peak_kb(after_children),
        "counts": dict(counts), "rows": rows, "covers": covers,
    }, ensure_ascii=False), flush=True)


# -------------------------------------------------------------------------- parent

def _drop_system_cache():
    """Really empty the page cache (Linux, root). The password comes from the environment, never from a file."""
    password = os.environ.get("BOBINE_BENCH_SUDO_PASSWORD")
    command = ["sudo", "-S", "-p", "", "sh", "-c", "sync; echo 3 > /proc/sys/vm/drop_caches"]
    result = subprocess.run(command, input=(password or "") + "\n", capture_output=True, text=True, timeout=60)
    return result.returncode == 0


def _drop_cache(paths):
    if not hasattr(os, "posix_fadvise"):
        return False
    for path in paths:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)  # dirty pages cannot be dropped before they are written
            os.posix_fadvise(descriptor, 0, 0, os.POSIX_FADV_DONTNEED)
        finally:
            os.close(descriptor)
    return True


def _sample(process, stop):
    import psutil
    peaks = {"rss_largest_kb": 0, "rss_sum_kb": 0, "pss_sum_kb": None, "processes": 0, "samples": 0}
    try:
        root = psutil.Process(process.pid)
    except psutil.NoSuchProcess:
        return peaks
    while not stop.is_set():
        try:
            tree = [root, *root.children(recursive=True)]
        except psutil.NoSuchProcess:
            break
        rss_total, pss_total, pss_ok, largest = 0, 0, True, 0
        for member in tree:
            try:
                info = member.memory_full_info() if sys.platform.startswith("linux") else member.memory_info()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            rss_total += info.rss
            largest = max(largest, info.rss)
            pss = getattr(info, "pss", None)
            if pss is None:
                pss_ok = False
            else:
                pss_total += pss
        peaks["samples"] += 1
        peaks["processes"] = max(peaks["processes"], len(tree))
        peaks["rss_largest_kb"] = max(peaks["rss_largest_kb"], largest / 1024)
        peaks["rss_sum_kb"] = max(peaks["rss_sum_kb"], rss_total / 1024)
        if pss_ok:
            peaks["pss_sum_kb"] = max(peaks["pss_sum_kb"] or 0, pss_total / 1024)
        stop.wait(0.02)
    return peaks


def run_once(corpus, entries, kind, mode, cache, binary, workdir):
    import threading
    run_dir = Path(tempfile.mkdtemp(prefix="bobine-import-bench-", dir=workdir))
    try:
        staging, data = run_dir / "staging", run_dir / "data"
        staging.mkdir()
        data.mkdir()
        names = []
        for index, entry in enumerate(entries):
            name = Path(entry["path"]).name
            # Keep the original name: it is the radio title fallback and the course title.
            target = staging / name
            if target.exists():
                target = staging / f"{index:04d}-{name}"
            shutil.copy2(corpus / entry["path"], target)
            names.append(target.name)
        staged_bytes = _tree_size(staging)
        cache_dropped = _drop_cache([staging / name for name in names]) if cache == "cold" else None
        if cache == "cold" and DROP_SYSTEM_CACHE:
            cache_dropped = "system" if _drop_system_cache() else "system-failed"
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(("BOBINE_", "XDG_"))}
        environment.update({"BOBINE_USE_XDG": "1", "XDG_DATA_HOME": str(data), "XDG_CONFIG_HOME": str(run_dir / "config"),
                            "BOBINE_DATABASE_URL": f"sqlite:///{data / 'bench.db'}"})
        if mode == "native":
            environment.update({"BOBINE_MEDIA_NATIVE": "1", "BOBINE_MEDIA_BIN": str(binary)})
        spec = {"staging": str(staging), "names": names, "kind": kind}
        started = time.perf_counter()
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker", json.dumps(spec)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=environment)
        stop = threading.Event()
        result = {}
        sampler = threading.Thread(target=lambda: result.update(_sample(process, stop)), daemon=True)
        sampler.start()
        stdout, stderr = process.communicate(timeout=3600)
        total_wall = time.perf_counter() - started
        stop.set()
        sampler.join(timeout=2)
        if process.returncode:
            raise RuntimeError(f"worker failed ({process.returncode}): {stderr.strip().splitlines()[-1:]}")
        report = json.loads(stdout.strip().splitlines()[-1])
        report.update({"mode": mode, "cache": cache, "cache_drop_attempted": cache_dropped, "kind": kind,
                       "process_wall_s": total_wall, "tree": result, "files": len(names),
                       "staged_input_bytes": staged_bytes, "data_dir_bytes": _tree_size(data)})
        return report
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def _key(row):
    return tuple(str(row.get(key)) for key in ("title", "number", "album", "artist", "track_number", "genre", "year"))


def compare_rows(reference, native, tolerance=0.05):
    """Return a list of human-readable differences between two imports of the same files."""
    problems = []
    if len(reference["rows"]) != len(native["rows"]):
        problems.append(f"imported rows: reference {len(reference['rows'])}, native {len(native['rows'])}")
    first = sorted(reference["rows"], key=lambda row: (_key(row), row["duration_seconds"] or 0))
    second = sorted(native["rows"], key=lambda row: (_key(row), row["duration_seconds"] or 0))
    for left, right in zip(first, second):
        for field in left:
            if field == "duration_seconds":
                a, b = left[field], right[field]
                if (a is None) != (b is None) or (a is not None and abs(a - b) > tolerance):
                    problems.append(f"{left.get('title')}: duration {a} vs {b}")
            elif left[field] != right[field]:
                problems.append(f"{left.get('title')}: {field} {left[field]!r} vs {right[field]!r}")
    ref_covers = {item["file"]: item["data"] for item in reference.get("covers", [])}
    nat_covers = {item["file"]: item["data"] for item in native.get("covers", [])}
    if set(ref_covers) != set(nat_covers):
        problems.append(f"covers present: reference {len(ref_covers)}, native {len(nat_covers)}")
    for name in sorted(set(ref_covers) & set(nat_covers)):
        if ref_covers[name] == nat_covers[name]:
            continue
        measure = cover_equivalence.measure(base64.b64decode(ref_covers[name]), base64.b64decode(nat_covers[name]))
        if not measure["equivalent"]:
            problems.append(f"{name}: cover not equivalent {measure}")
    return problems


def summarize(runs):
    summary = {}
    for mode in MODES:
        for cache in sorted({run["cache"] for run in runs}):
            group = [run for run in runs if run["mode"] == mode and run["cache"] == cache]
            if not group:
                continue
            def med(getter):
                values = [getter(run) for run in group if getter(run) is not None]
                return statistics.median(values) if values else None
            summary[f"{mode}/{cache}"] = {
                "runs": len(group), "files": group[0]["files"], "imported": group[0]["imported"],
                "wall_s_median": med(lambda r: r["wall_s"]),
                "wall_ms_per_file_median": med(lambda r: r["wall_s"] * 1000 / r["files"]),
                "cpu_s_median": med(lambda r: r["cpu_self_s"] + r["cpu_children_s"]),
                "peak_processes_max": max(r["tree"].get("processes", 0) for r in group),
                "peak_tree_pss_mib_max": med_max(group, "pss_sum_kb"),
                "peak_tree_rss_sum_mib_max": med_max(group, "rss_sum_kb"),
                "peak_single_process_rss_mib_max": med_max(group, "rss_largest_kb"),
                "data_dir_bytes": group[0]["data_dir_bytes"],
                "native_probe": group[0]["counts"].get("native_probe", 0),
                "reference_metadata_calls": group[0]["counts"].get("reference_metadata", 0),
                "reference_cover_calls": group[0]["counts"].get("reference_cover", 0),
            }
    for cache in sorted({run["cache"] for run in runs}):
        base, fast = summary.get(f"reference/{cache}"), summary.get(f"native/{cache}")
        if base and fast and base["wall_s_median"] and fast["wall_s_median"]:
            summary[f"ratio/{cache}"] = {
                "wall_reference_over_native": base["wall_s_median"] / fast["wall_s_median"],
                "cpu_reference_over_native": (base["cpu_s_median"] / fast["cpu_s_median"]) if fast["cpu_s_median"] else None,
            }
    return summary


def med_max(group, key):
    values = [run["tree"].get(key) for run in group if run["tree"].get(key) is not None]
    return max(values) / 1024 if values else None


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        worker(json.loads(sys.argv[2]))
        return
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("corpus", type=Path, help="corpus made by generate.py (use --scale for 500+ tracks)")
    parser.add_argument("--binary", type=Path, required=True, help="bobine-media executable under test")
    parser.add_argument("--output", type=Path, required=True, help="new JSON report, outside the checkout")
    parser.add_argument("--kind", choices=("radio", "course"), default="radio")
    parser.add_argument("--count", type=int, default=0, help="import only the first N manifest entries (default: all)")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--drop-system-cache", action="store_true",
                        help="cold runs empty the whole page cache through sudo (password in BOBINE_BENCH_SUDO_PASSWORD)")
    parser.add_argument("--cache", choices=("warm", "cold", "both"), default="both")
    parser.add_argument("--workdir", type=Path, default=Path("/var/tmp") if os.name != "nt" else Path(tempfile.gettempdir()),
                        help="disk-backed scratch directory (never a RAM-backed tmpfs for a fair disk measurement)")
    args = parser.parse_args()
    corpus, output = args.corpus.resolve(), args.output.resolve()
    if output.exists():
        parser.error("output already exists")
    if output == ROOT or ROOT in output.parents or corpus == ROOT or ROOT in corpus.parents:
        parser.error("corpus and output must live outside the checkout")
    if args.repeats < 1 or args.count < 0:
        parser.error("--repeats must be positive and --count non-negative")
    binary = args.binary.resolve()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        parser.error("--binary is not an executable file")
    manifest = json.loads((corpus / "manifest.json").read_bytes())
    entries = manifest["entries"][:args.count] if args.count else manifest["entries"]
    if len(entries) < 500:
        print(f"warning: {len(entries)} files; the B1.5 exit criterion asks for 500 or more", file=sys.stderr)
    caches = ("warm", "cold") if args.cache == "both" else (args.cache,)
    global DROP_SYSTEM_CACHE
    DROP_SYSTEM_CACHE = args.drop_system_cache
    runs = []
    for repeat in range(args.repeats):
        # Alternate the order so slow drift (thermal, background load) is not charged to one mode.
        for mode in (MODES if repeat % 2 == 0 else tuple(reversed(MODES))):
            for cache in caches:
                run = run_once(corpus, entries, args.kind, mode, cache, binary, args.workdir)
                runs.append(run)
                print(f"{mode:9} {cache:4} #{repeat + 1}: {run['wall_s']:.2f} s, imported {run['imported']}/{run['files']}, "
                      f"processes<= {run['tree'].get('processes')}", file=sys.stderr)
    differences = []
    for cache in caches:
        reference = [run for run in runs if run["mode"] == "reference" and run["cache"] == cache]
        native = [run for run in runs if run["mode"] == "native" and run["cache"] == cache]
        for left, right in zip(reference, native):
            differences.extend(f"[{cache}] {item}" for item in compare_rows(left, right))
    for run in runs:
        run.pop("rows")  # keep the report small; differences were computed above
        run["cover_count"] = len(run.pop("covers"))
    report = {
        "schema_version": 1, "kind": args.kind, "files": len(entries), "repeats": args.repeats,
        "platform": sys.platform, "python": sys.version.split()[0], "cpu_count": os.cpu_count(),
        "ffmpeg_version": subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.splitlines()[:1],
        "binary": {"bytes": binary.stat().st_size, "sha256": hashlib.sha256(binary.read_bytes()).hexdigest()},
        "manifest_sha256": hashlib.sha256((corpus / "manifest.json").read_bytes()).hexdigest(),
        "summary": summarize(runs), "differences": differences, "passed": not differences, "runs": runs,
        "limitations": [
            "Measured on the machine that ran the script; not a device validation",
            "Cold cache: `cache_drop_attempted` is `system` when the page cache was emptied through sudo, otherwise a best-effort fadvise on the staged files",
            "Peak PSS needs Linux smaps; elsewhere only RSS is available (shared pages counted per process)",
            "Cancellation and simultaneous playback are not exercised by this script",
            "Files that the native component declines run the reference path and cost both",
        ],
    }
    with output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": report["passed"], "differences": len(differences), "summary": report["summary"]}, indent=2))
    if differences:
        sys.exit(1)


if __name__ == "__main__":
    main()
