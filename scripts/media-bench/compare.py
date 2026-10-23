#!/usr/bin/env python3
"""Compare the experimental executable through the actual Python MediaClient."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cover_equivalence  # noqa: E402
EXPECTED_FALLBACKS = frozenset(("unsupported", "corrupt", "ambiguous_metadata", "ambiguous_cover", "limit_exceeded"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def duration_equal(actual, expected):
    if actual is None or expected is None:
        return actual is expected
    return abs(actual - expected) <= 0.05


def compare(corpus, baseline_path, binary, output, repeats):
    if output.exists():
        raise FileExistsError("Comparison output already exists")
    if output == ROOT or ROOT in output.parents:
        raise ValueError("Comparison output must stay outside the checkout")
    manifest_path = corpus / "manifest.json"
    manifest, baseline = json.loads(manifest_path.read_bytes()), json.loads(baseline_path.read_bytes())
    if manifest.get("schema_version") != 1 or baseline.get("schema_version") != 1:
        raise ValueError("Unsupported manifest or baseline version")
    if sha(manifest_path) != baseline.get("manifest_sha256"):
        raise ValueError("Baseline is not bound to this manifest")
    references = {entry["id"]: entry for entry in baseline["entries"]}
    if len(references) != len(baseline["entries"]) or set(references) != {entry["id"] for entry in manifest["entries"]}:
        raise ValueError("Manifest and baseline ids differ or are duplicated")
    source_paths = {"binary": binary, "manifest": manifest_path, "baseline": baseline_path,
                    "radio_utils.py": ROOT / "backend/app/utils/radio_utils.py",
                    "audio_utils.py": ROOT / "backend/app/utils/audio_utils.py",
                    "media_metadata.py": ROOT / "backend/app/utils/media_metadata.py",
                    "media_sidecar.py": ROOT / "backend/app/utils/media_sidecar.py"}
    source_before = {name: sha(path) for name, path in source_paths.items()}
    summaries = {profile: Counter() for profile in ("radio", "course", "cover")}
    all_results, differences, unexpected = [], [], []
    maximum_delta = 0.0
    with tempfile.TemporaryDirectory(prefix="bobine-media-compare-") as temporary:
        os.environ.update({"BOBINE_USE_XDG": "1", "XDG_DATA_HOME": temporary,
                           "BOBINE_DATABASE_URL": f"sqlite:///{Path(temporary) / 'unused.db'}"})
        sys.path.insert(0, str(ROOT / "backend"))
        from app.utils.media_sidecar import MediaClient
        from app.utils.radio_utils import clean_filename_label
        from app.utils.media_metadata import render_cover
        reference_covers = baseline_path.parent / "reference-covers"
        client = MediaClient(command=[str(binary)], enabled=True)
        try:
            for entry in manifest["entries"]:
                identity = entry["id"]
                path = (corpus / entry["path"]).resolve()
                if corpus not in path.parents:
                    raise ValueError(f"Corpus path escapes root: {identity}")
                before = sha(path)
                reference = references[identity]
                if before != entry["sha256"] or before != reference["sha256"]:
                    raise ValueError(f"Corpus hash mismatch: {identity}")
                observation = {"id": identity, "type": entry["type"], "sha256_before": before, "calls": {}}
                for profile, native_profile in (("radio", "radio-v1"), ("course", "course-duration-v1"), ("cover", None)):
                    timings, outcomes = [], []
                    for _ in range(repeats):
                        started = time.perf_counter_ns()
                        value = client.extract_cover(path) if profile == "cover" else client.probe_audio(path, native_profile)
                        timings.append((time.perf_counter_ns() - started) / 1e6)
                        failure = client.last_failure
                        available = value.available if profile == "cover" else value is not None
                        outcome = {"status": "native" if available else "fallback", "reason": failure}
                        if available:
                            if profile == "cover":
                                outcome["value"] = {"present": value.data is not None, "mime": value.mime,
                                                    "sha256": hashlib.sha256(value.data).hexdigest() if value.data is not None else None}
                                if value.data is not None:
                                    outcome["raw"] = value.data
                            else:
                                if profile == "radio" and value["title"] is None:
                                    value["title"] = clean_filename_label(str(path))
                                outcome["value"] = value if profile == "radio" else value["duration_seconds"]
                        outcomes.append(outcome)
                    for item in outcomes:
                        item_raw = item.pop("raw", None)
                        item["_raw"] = item_raw
                    raw = outcomes[0].pop("_raw")
                    for item in outcomes[1:]:
                        item.pop("_raw", None)
                    current = outcomes[0]
                    if any(item != current for item in outcomes[1:]):
                        differences.append({"id": identity, "profile": profile, "field": "repeat_stability"})
                    current["elapsed_ms"] = {"samples": timings, "median": statistics.median(timings)}
                    observation["calls"][profile] = current
                    if current["status"] == "fallback":
                        reason = current["reason"] or "missing_reason"
                        summaries[profile][f"fallback:{reason}"] += 1
                        if reason not in EXPECTED_FALLBACKS:
                            unexpected.append({"id": identity, "profile": profile, "reason": reason})
                        continue
                    summaries[profile]["native"] += 1
                    actual = current["value"]
                    if profile == "cover":
                        if actual["present"]:
                            reference_file = reference_covers / f"{identity}.jpg"
                            if not reference["cover"]["present"] or not reference_file.is_file():
                                differences.append({"id": identity, "profile": profile, "field": "cover_without_reference"})
                            else:
                                measure = cover_equivalence.measure(reference_file.read_bytes(), render_cover(raw))
                                current["equivalence"] = measure
                                summaries[profile]["equivalent" if measure["equivalent"] else "not_equivalent"] += 1
                                if not measure["equivalent"]:
                                    differences.append({"id": identity, "profile": profile, "field": "cover_equivalence", "measure": measure})
                        elif reference["cover"]["present"]:
                            differences.append({"id": identity, "profile": profile, "field": "false_absence"})
                        continue
                    expected = reference["profiles"][profile]["value"]
                    actual_fields = actual if profile == "radio" else {"duration_seconds": actual}
                    expected_fields = expected if profile == "radio" else {"duration_seconds": expected}
                    for field, expected_value in expected_fields.items():
                        actual_value = actual_fields[field]
                        if field == "duration_seconds":
                            equal = duration_equal(actual_value, expected_value)
                            if actual_value is not None and expected_value is not None:
                                maximum_delta = max(maximum_delta, abs(actual_value - expected_value))
                        else:
                            equal = actual_value == expected_value
                        if not equal:
                            differences.append({"id": identity, "profile": profile, "field": field,
                                                "native": actual_value, "reference": expected_value})
                after = sha(path)
                observation["sha256_after"] = after
                if before != after:
                    differences.append({"id": identity, "field": "source_mutated"})
                all_results.append(observation)
        finally:
            client.close()
    source_after = {name: sha(path) for name, path in source_paths.items()}
    if source_before != source_after:
        differences.append({"field": "source_code_or_reference_mutated"})
    if "app.database" in sys.modules:
        unexpected.append({"reason": "database_imported"})
    result = {"schema_version": 1, "transport": "MediaClient", "enabled_explicitly": True,
              "entries": all_results, "repeats": repeats, "tolerance_seconds": 0.05,
              "summary": {profile: dict(counts) for profile, counts in summaries.items()},
              "source_sha256_before": source_before, "source_sha256_after": source_after,
              "max_accepted_duration_delta_seconds": maximum_delta,
              "differences": differences, "unexpected_failures": unexpected,
              "passed": not differences and not unexpected,
              "limitations": ["Experimental native subset only; fallbacks are not native coverage",
                              "Fallback reasons are observed; reference fallback execution is not timed here",
                              "A native cover is judged by cover_equivalence.py (same size, PSNR >= 33 dB, MAE <= 4), not byte for byte",
                              "Development host only; no device or end-to-end import validation",
                              "Times include the actual client; first request includes process startup and handshake"]}
    with output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: result[key] for key in ("passed", "summary", "max_accepted_duration_delta_seconds", "differences", "unexpected_failures")},
                     ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("--binary", type=Path, required=True, help="Executable to enable explicitly for this run")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    raise SystemExit(compare(args.corpus.resolve(), args.baseline.resolve(), args.binary.resolve(), args.output.resolve(), args.repeats))


if __name__ == "__main__":
    main()
