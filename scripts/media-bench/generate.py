#!/usr/bin/env python3
"""Generate synthetic audio fixtures, never inside the source checkout."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]


def run(command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if result.returncode:
        # Keep generated reports portable: no absolute paths in diagnostics.
        raise RuntimeError(f"{Path(command[0]).name} exited {result.returncode}")
    return result.stdout


def png(path):
    """Small RGBA cover with transparency using only the standard library."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    pixels = b"".join(b"\0" + bytes((200, 50, 90, y * 4)) * 96 for y in range(64))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 96, 64, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))


def generate(output, ffmpeg):
    if output == ROOT or ROOT in output.parents:
        raise ValueError("Choose an output directory outside the checkout")
    output.mkdir(parents=True, exist_ok=False)
    media = output / "media"
    media.mkdir()
    png(output / "cover.png")
    run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(output / "cover.png"),
         "-frames:v", "1", "-threads", "1", str(output / "cover.jpg")])
    families = [
        ("mp3-cbr-xing", "mp3", ["-c:a", "libmp3lame", "-b:a", "128k", "-write_xing", "1"]),
        ("mp3-vbr-xing", "mp3", ["-c:a", "libmp3lame", "-q:a", "3", "-write_xing", "1"]),
        ("mp3-cbr-no-xing", "mp3", ["-c:a", "libmp3lame", "-b:a", "128k", "-write_xing", "0"]),
        ("mp3-vbr-no-xing", "mp3", ["-c:a", "libmp3lame", "-q:a", "3", "-write_xing", "0"]),
        ("flac", "flac", ["-c:a", "flac"]),
        ("wav", "wav", ["-c:a", "pcm_s16le"]),
        ("aac-adts", "aac", ["-c:a", "aac", "-b:a", "96k"]),
        ("aac-m4a", "m4a", ["-c:a", "aac", "-b:a", "96k"]),
        ("ogg-vorbis", "ogg", ["-c:a", "libvorbis", "-q:a", "3"]),
        ("ogg-opus", "opus", ["-c:a", "libopus", "-b:a", "96k"]),
        ("wma", "wma", ["-c:a", "wmav2", "-b:a", "128k"]),
        ("aiff", "aiff", ["-c:a", "pcm_s16be"]),
    ]
    variants = [
        ("absent", {}, "01 - No_tags"),
        ("unicode", {"title": "Été 東京 🎵", "artist": "Björk synthétique", "album": "À demain"}, "éspace 東京"),
        ("numbers", {"title": "Numbers", "track": "03/12", "disc": "02/04", "date": "2024-06-17",
                     "album_artist": "Ensemble", "genre": "Synthetic"}, "03_numbers"),
        ("atypical", {"title": "  Padded title  ", "artist": "", "date": "recorded in 1999"}, "-leading [brackets] & quote's"),
    ]
    entries, failures = [], []

    def record(identity, kind, path, expected):
        entries.append({"id": identity, "type": kind, "path": path.relative_to(output).as_posix(),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "expected": expected})

    for family, extension, codec in families:
        for variant, tags, filename in variants:
            identity = f"{family}-{variant}"
            path = media / f"{identity} {filename}.{extension}"
            command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                       "sine=frequency=440:sample_rate=44100:duration=1.37", "-map_metadata", "-1", *codec]
            for key, value in tags.items():
                command += ["-metadata", f"{key}={value}"]
            try:
                run([*command, str(path)])
            except (RuntimeError, subprocess.TimeoutExpired) as exc:
                failures.append({"id": identity, "reason": str(exc) if not isinstance(exc, subprocess.TimeoutExpired) else "ffmpeg timeout"})
                print(f"FAILED {identity}: {failures[-1]['reason']}", file=sys.stderr)
                continue
            record(identity, family, path, {"source_seconds": 1.37, "requested_tags": tags, "cover": None})

    # Both opaque JPEG and transparent PNG in two common cover containers.
    for family, extension in [("mp3-cbr-xing", "mp3"), ("flac", "flac")]:
        source = next((entry for entry in entries if entry["id"] == f"{family}-numbers"), None)
        if source is None:
            failures.append({"id": f"{family}-covers", "reason": "source encoder unavailable"})
            continue
        for image_format in ("jpg", "png"):
            identity = f"{family}-cover-{image_format}"
            path = media / f"{identity}.{extension}"
            try:
                run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(output / source["path"]),
                     "-i", str(output / f"cover.{image_format}"), "-map", "0:a", "-map", "1:v",
                     "-c", "copy", "-disposition:v", "attached_pic", str(path)])
            except (RuntimeError, subprocess.TimeoutExpired) as exc:
                failures.append({"id": identity, "reason": str(exc) if not isinstance(exc, subprocess.TimeoutExpired) else "ffmpeg timeout"})
                print(f"FAILED {identity}: {failures[-1]['reason']}", file=sys.stderr)
                continue
            record(identity, family, path, {"source_seconds": 1.37, "cover": image_format})

    for identity, data in [("empty", b""), ("garbage", b"not an audio file\0" * 8),
                           ("truncated-id3", b"ID3\x04\0\0\0\0\x7f\x7fbroken")]:
        path = media / f"corrupt-{identity}.mp3"
        path.write_bytes(data)
        record(f"corrupt-{identity}", "corrupt", path, {"readable": False, "cover": None})
    manifest = {"schema_version": 1, "generator": "synthetic-sine-v1", "ffmpeg_version": run([ffmpeg, "-version"]).splitlines()[0],
                "entries": entries, "failures": failures,
                "limitations": ["No VBRI fixture: ffmpeg libmp3lame generates Xing/Info, not VBRI",
                                "Requested tags may not survive every container; baseline captures actual behavior",
                                "Encoded bytes can vary between ffmpeg versions; hashes bind this generated corpus"]}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"files": len(entries), "failures": len(failures)}))
    if len(entries) < 40:
        raise RuntimeError("Corpus has fewer than 40 files; consult manifest failures")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New directory outside the checkout")
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg") or "ffmpeg")
    args = parser.parse_args()
    generate(args.output.resolve(), args.ffmpeg)


if __name__ == "__main__":
    main()
