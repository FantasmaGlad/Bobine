#!/usr/bin/env python3
"""Capture the existing Python audio contract for a generated corpus."""
import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import statistics
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]


def capture(corpus, output, repeats):
    manifest_bytes = (corpus / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported manifest version")
    if output.exists():
        raise FileExistsError("Baseline output already exists")
    if output == ROOT or ROOT in output.parents:
        raise ValueError("Baseline output must stay outside the checkout")
    with tempfile.TemporaryDirectory(prefix="bobine-media-oracle-") as temporary:
        isolated = Path(temporary)
        os.environ.update({"BOBINE_USE_XDG": "1", "XDG_DATA_HOME": temporary,
                           "BOBINE_DATABASE_URL": f"sqlite:///{isolated / 'unused.db'}"})
        sys.path.insert(0, str(ROOT / "backend"))
        # These modules have no database import. Never import app.main or database.
        from app.utils.audio_utils import extract_audio_duration
        from app.utils.radio_utils import extract_radio_metadata, extract_embedded_cover
        from app.utils.ffmpeg_binaries import FFPROBE_BIN, FFMPEG_BIN
        from PIL import Image
        logging.getLogger("app.utils.audio_utils").setLevel(logging.CRITICAL)
        logging.getLogger("app.utils.radio_utils").setLevel(logging.CRITICAL)
        results = []
        # Final JPEGs of the reference pipeline (ffmpeg, then Pillow) next to the report: the native
        # cover pipeline is judged against them by compare.py without running ffmpeg a second time.
        reference_covers = output.parent / "reference-covers"
        reference_covers.mkdir(exist_ok=True)
        for entry in manifest["entries"]:
            path = (corpus / entry["path"]).resolve()
            if corpus not in path.parents:
                raise ValueError(f"Corpus path escapes root: {entry['id']}")
            if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError(f"Corpus hash mismatch: {entry['id']}")
            observation = {"id": entry["id"], "sha256": entry["sha256"], "profiles": {}}
            for profile, function in [("radio", extract_radio_metadata), ("course", extract_audio_duration)]:
                durations, values = [], []
                for _ in range(repeats):
                    start = time.perf_counter_ns()
                    values.append(function(str(path)))
                    durations.append((time.perf_counter_ns() - start) / 1e6)
                if any(value != values[0] for value in values[1:]):
                    raise RuntimeError(f"Non-deterministic oracle: {entry['id']} {profile}")
                value = values[0]
                observation["profiles"][profile] = {
                    "value": value, "presence": {key: item is not None for key, item in value.items()} if isinstance(value, dict) else value is not None,
                    "elapsed_ms": {"samples": durations, "median": statistics.median(durations)},
                }
            cover_start = time.perf_counter_ns()
            cover = extract_embedded_cover(str(path), str(isolated / "covers"), entry["id"])
            observation["cover"] = {"present": cover is not None, "elapsed_ms": (time.perf_counter_ns() - cover_start) / 1e6}
            if cover:
                with Image.open(cover) as image:
                    observation["cover"].update({"format": image.format, "mode": image.mode, "size": list(image.size)})
                observation["cover"]["sha256"] = hashlib.sha256(Path(cover).read_bytes()).hexdigest()
                shutil.copyfile(cover, reference_covers / f"{entry['id']}.jpg")
            probe = subprocess.run([FFPROBE_BIN, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                                   capture_output=True, text=True, timeout=30)
            raw = json.loads(probe.stdout) if probe.returncode == 0 else None
            if raw is not None and "format" in raw:
                raw["format"]["filename"] = entry["path"]
            observation["ffprobe"] = {"returncode": probe.returncode, "data": raw}
            results.append(observation)
        if "app.database" in sys.modules:
            raise RuntimeError("Oracle unexpectedly imported database")
        report = {"schema_version": 1, "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                  "oracle": "existing-python-utils", "python": sys.version.split()[0],
                  "ffprobe_version": subprocess.run([FFPROBE_BIN, "-version"], capture_output=True, text=True, check=True).stdout.splitlines()[0],
                  "ffmpeg_version": subprocess.run([FFMPEG_BIN, "-version"], capture_output=True, text=True, check=True).stdout.splitlines()[0],
                  "repeats": repeats, "entries": results,
                  "limitations": ["Development-host measurements only; not validated on devices",
                                  "Per-function timings exclude import, SQL and transcode",
                                  "Cover bytes represent ffmpeg plus Pillow output, not the original attached image",
                                  "Filesystem cache state is uncontrolled; do not label these samples cold-cache"]}
        with output.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        print(json.dumps({"entries": len(results), "covers": sum(item["cover"]["present"] for item in results),
                          "database_imported": "app.database" in sys.modules}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    capture(args.corpus.resolve(), args.output.resolve(), args.repeats)


if __name__ == "__main__":
    main()
