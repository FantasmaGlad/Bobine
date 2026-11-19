#!/usr/bin/env python3
"""Generate synthetic audio fixtures, never inside the source checkout."""
import argparse
import base64
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
        raise RuntimeError(f"{Path(command[0]).name} exited {result.returncode}")
    return result.stdout


def png(path):
    """Small RGBA cover with transparency using only the standard library."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    pixels = b"".join(b"\0" + bytes((200, 50, 90, y * 4)) * 96 for y in range(64))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 96, 64, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))


_MPEG1_L3_BITRATES = (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320)
_MPEG1_SAMPLE_RATES = (44100, 48000, 32000)


def _mp3_frames(data, start):
    frames, position = [], start
    while position + 4 <= len(data):
        header = int.from_bytes(data[position:position + 4], "big")
        bitrate_index, rate_index = (header >> 12) & 0xF, (header >> 10) & 0x3
        if (header >> 21) != 0x7FF or (header >> 19) & 3 != 3 or (header >> 17) & 3 != 1 \
                or not 0 < bitrate_index < 15 or rate_index == 3:
            break
        length = 144 * _MPEG1_L3_BITRATES[bitrate_index] * 1000 // _MPEG1_SAMPLE_RATES[rate_index] + ((header >> 9) & 1)
        if position + length > len(data):
            break
        frames.append((position, length))
        position += length
    return start, frames


def build_vbri_mp3(data):
    """Insert a genuine VBRI frame after the ID3v2 tag of a CBR MPEG-1 Layer III stream."""
    start = 0
    if data[:3] == b"ID3":
        start = 10 + (data[6] << 21 | data[7] << 14 | data[8] << 7 | data[9])
    _, frames = _mp3_frames(data, start)
    if not frames:
        raise ValueError("No MPEG-1 Layer III frames found")
    first_offset, first_length = frames[0]
    header = data[first_offset:first_offset + 4]
    audio_bytes = sum(length for _, length in frames)
    vbri = (b"VBRI" + struct.pack(">HHH", 1, 0, 0) + struct.pack(">II", audio_bytes, len(frames))
            + struct.pack(">HHHH", 0, 1, 1, 1))
    frame = (header + b"\0" * 32 + vbri).ljust(first_length, b"\0")
    return data[:first_offset] + frame + data[first_offset:]


def flac_picture_block(image, mime, picture_type=3):
    """FLAC METADATA_BLOCK_PICTURE body: the same layout serves Ogg Vorbis and Opus comments."""
    description = b""
    return (struct.pack(">II", picture_type, len(mime)) + mime + struct.pack(">I", len(description)) + description
            + struct.pack(">IIII", 0, 0, 24, 0) + struct.pack(">I", len(image)) + image)


def ogg_picture_comment(image_path, image_format):
    """ffmpeg's Ogg muxer cannot mux an attached picture; the comment is the real on-disk form."""
    mime = b"image/jpeg" if image_format == "jpg" else b"image/png"
    return "METADATA_BLOCK_PICTURE=" + base64.b64encode(flac_picture_block(Path(image_path).read_bytes(), mime)).decode("ascii")


def patch_mp4_creation_time(data, seconds_1904):
    """Set a creation time in mvhd and mdhd (version 0): ffmpeg then exposes a creation_time tag."""
    data = bytearray(data)
    for box in (b"mvhd", b"mdhd"):
        index = bytes(data).find(box)
        if index < 0 or data[index + 4] != 0:
            raise ValueError("Unexpected MP4 layout")
        data[index + 8:index + 12] = struct.pack(">I", seconds_1904)
    return bytes(data)


FAMILIES = [
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
SCALE_FAMILIES = [family for family in FAMILIES if family[0] not in ("aac-adts", "wma")] + [
    ("mp3-cbr-no-xing-48k-192", "mp3", ["-c:a", "libmp3lame", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-write_xing", "0"]),
    ("mp3-cbr-no-xing-22k-64", "mp3", ["-c:a", "libmp3lame", "-b:a", "64k", "-ar", "22050", "-write_xing", "0"]),
    ("mp3-cbr-xing-32k-96", "mp3", ["-c:a", "libmp3lame", "-b:a", "96k", "-ar", "32000", "-write_xing", "1"]),
]
VARIANTS = [
    ("absent", {}, "01 - No_tags"),
    ("unicode", {"title": "Été 東京 Ω", "artist": "Björk synthétique", "album": "À demain"}, "éspace 東京"),
    ("numbers", {"title": "Numbers", "track": "03/12", "disc": "02/04", "date": "2024-06-17",
                 "album_artist": "Ensemble", "genre": "Synthetic"}, "03_numbers"),
    ("atypical", {"title": "  Padded title  ", "artist": "", "date": "recorded in 1999"}, "-leading [brackets] & quote's"),
    ("plain-numbers", {"title": "Plain", "track": "5", "disc": "1", "date": "1987"}, "plain numbers"),
    ("zero-numbers", {"title": "Zero", "track": "0/9", "disc": "0", "year": "2001"}, "zero numbers"),
]
LAYOUTS = [
    ("mp3-cbr-xing-id3v24", "mp3", "mp3-cbr-xing", ["-id3v2_version", "4"], "numbers"),
    ("mp3-cbr-xing-id3v1", "mp3", "mp3-cbr-xing", ["-write_id3v1", "1"], "numbers"),
    ("mp3-cbr-no-xing-id3v24", "mp3", "mp3-cbr-no-xing", ["-id3v2_version", "4"], "numbers"),
]
SINE = "sine=frequency=440:sample_rate=44100:duration=1.37"
LIMITATIONS = ["VBRI fixtures are synthesized by build_vbri_mp3 (ffmpeg writes Xing/Info only)",
               "No path with non-UTF-8 bytes: JSON reports cannot carry it; the transport tests cover it",
               "Requested tags may not survive every container; baseline captures actual behavior",
               "Encoded bytes can vary between ffmpeg versions; hashes bind this generated corpus"]


def _gallery_base():
    from PIL import Image, ImageDraw, ImageFilter
    import random
    random.seed(7)
    base = Image.effect_mandelbrot((800, 600), (-2.2, -1.5, 0.8, 1.5), 80).convert("RGB").filter(ImageFilter.GaussianBlur(1))
    draw = ImageDraw.Draw(base)
    for _ in range(60):
        x0, y0 = random.randint(0, 600), random.randint(0, 400)
        draw.ellipse([x0, y0, x0 + random.randint(20, 190), y0 + random.randint(20, 190)],
                     outline=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)), width=3)
    return base


def _gallery_variants(base):
    from PIL import Image
    exif = Image.Exif()
    exif[0x0112] = 6
    exif_flat = Image.Exif()
    exif_flat[0x0112] = 1
    gradient = Image.linear_gradient("L").resize((800, 600))
    return {
        "jpg-baseline": (base, "JPEG", {"quality": 90}),
        "jpg-progressive": (base, "JPEG", {"quality": 85, "progressive": True}),
        "jpg-gray": (base.convert("L"), "JPEG", {"quality": 90}),
        "jpg-444": (base, "JPEG", {"quality": 90, "subsampling": 0}),
        "jpg-odd-size": (base.crop((0, 0, 333, 201)), "JPEG", {"quality": 90}),
        "jpg-small": (base.resize((96, 64)), "JPEG", {"quality": 90}),
        "jpg-large": (base.resize((3000, 2250)), "JPEG", {"quality": 92}),
        "jpg-cmyk": (base.convert("CMYK"), "JPEG", {"quality": 90}),
        "jpg-exif-rotated": (base, "JPEG", {"quality": 90, "exif": exif.tobytes()}),
        "jpg-exif-upright": (base, "JPEG", {"quality": 90, "exif": exif_flat.tobytes()}),
        "png-rgb": (base, "PNG", {}),
        "png-rgba": (Image.merge("RGBA", (*base.split(), gradient)), "PNG", {}),
        "png-palette": (base.quantize(64), "PNG", {}),
        "png-palette-transparent": (base.quantize(32), "PNG", {"transparency": 3}),
        "png-gray": (base.convert("L"), "PNG", {}),
        "png-gray-alpha": (Image.merge("LA", (base.convert("L"), gradient)), "PNG", {}),
        "png-interlaced": (base, "PNG", {"interlace": 1}),
        "png-small-rgba": (Image.merge("RGBA", (*base.resize((96, 64)).split(), Image.new("L", (96, 64), 128))), "PNG", {}),
    }


def cover_gallery(output):
    """Image varieties that exercise the cover equivalence."""
    try:
        import PIL  # noqa: F401
    except ImportError:
        return {}
    import io
    gallery = {}
    folder = output / "gallery"
    folder.mkdir()
    for name, (image, fmt, options) in _gallery_variants(_gallery_base()).items():
        buffer = io.BytesIO()
        try:
            image.save(buffer, fmt, **options)
        except (OSError, ValueError, TypeError):
            continue
        extension = "jpg" if fmt == "JPEG" else "png"
        path = folder / f"{name}.{extension}"
        path.write_bytes(buffer.getvalue())
        gallery[name] = (path, extension)
    return gallery


def _failure_reason(exc):
    return str(exc) if not isinstance(exc, subprocess.TimeoutExpired) else "ffmpeg timeout"


class _Draw:
    def __init__(self):
        self.state = 12345

    def __call__(self):
        self.state = (self.state * 1103515245 + 12345) & 0x7FFFFFFF
        return self.state / 0x7FFFFFFF


def _scale_command(output, ffmpeg, index, family, codec, duration, tags, cover):
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
               f"sine=frequency={220 + index % 440}:sample_rate=44100:duration={duration}"]
    ogg_family = family.startswith("ogg")
    if cover and not ogg_family:
        command += ["-i", str(output / f"cover.{cover}"), "-map", "0:a", "-map", "1:v",
                    "-c:v", "copy", "-disposition:v", "attached_pic"]
    command += ["-map_metadata", "-1", *codec]
    for key, value in tags.items():
        command += ["-metadata", f"{key}={value}"]
    if cover and ogg_family:
        command += ["-metadata", ogg_picture_comment(output / f"cover.{cover}", cover)]
    return command


def _scale_tags(index):
    return {"title": f"Titre synthétique {index:04d}", "artist": f"Artiste {index % 37}", "album": f"Album {index % 53}",
            "track": f"{index % 14 + 1}/14", "date": str(1990 + index % 35), "genre": ("Synthetic", "Test", "Démo")[index % 3]}


def generate_scale(output, media, ffmpeg, count, cover_ratio, failures):
    """Extra unique tracks with varied durations, for large-library measurements."""
    scale_dir = media / "scale"
    scale_dir.mkdir()
    draw, produced = _Draw(), []
    for index in range(count):
        family, extension, codec = SCALE_FAMILIES[index % len(SCALE_FAMILIES)]
        duration = round(0.5 + draw() * 11.5, 2)
        with_cover = family.startswith(("mp3", "flac", "aac-m4a", "ogg")) and draw() < cover_ratio
        image = "jpg" if draw() < 0.7 else "png"
        tags = _scale_tags(index)
        identity = f"scale-{index:04d}-{family}"
        path = scale_dir / f"{index:04d} - {tags['title']}.{extension}"
        try:
            run([*_scale_command(output, ffmpeg, index, family, codec, duration, tags, image if with_cover else None), str(path)])
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            failures.append({"id": identity, "reason": _failure_reason(exc)})
            continue
        produced.append((identity, family, path, {"source_seconds": duration, "requested_tags": tags,
                                                   "cover": image if with_cover else None, "scale": True}))
    return produced


class Corpus:
    def __init__(self, output, ffmpeg):
        self.output, self.media, self.ffmpeg = output, output / "media", ffmpeg
        self.entries, self.failures = [], []

    def record(self, identity, kind, path, expected):
        self.entries.append({"id": identity, "type": kind, "path": path.relative_to(self.output).as_posix(),
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "expected": expected})

    def source(self, identity):
        return next((entry for entry in self.entries if entry["id"] == identity), None)

    def source_path(self, entry):
        return str(self.output / entry["path"])

    def encode(self, identity, arguments, echo=True):
        try:
            run([self.ffmpeg, "-hide_banner", "-loglevel", "error", *arguments])
            return True
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            self.failures.append({"id": identity, "reason": _failure_reason(exc)})
            if echo:
                print(f"FAILED {identity}: {self.failures[-1]['reason']}", file=sys.stderr)
            return False


def _encode_families(corpus):
    for family, extension, codec in FAMILIES:
        for variant, tags, filename in VARIANTS:
            identity = f"{family}-{variant}"
            path = corpus.media / f"{identity} {filename}.{extension}"
            metadata = [argument for key, value in tags.items() for argument in ("-metadata", f"{key}={value}")]
            if corpus.encode(identity, ["-f", "lavfi", "-i", SINE, "-map_metadata", "-1", *codec, *metadata, str(path)]):
                corpus.record(identity, family, path, {"source_seconds": 1.37, "requested_tags": tags, "cover": None})


def _attach_covers(corpus):
    for family, extension in [("mp3-cbr-xing", "mp3"), ("flac", "flac"), ("aac-m4a", "m4a"), ("ogg-vorbis", "ogg"), ("ogg-opus", "opus")]:
        source = corpus.source(f"{family}-numbers")
        if source is None:
            corpus.failures.append({"id": f"{family}-covers", "reason": "source encoder unavailable"})
            continue
        for image_format in ("jpg", "png"):
            identity = f"{family}-cover-{image_format}"
            path = corpus.media / f"{identity}.{extension}"
            cover = corpus.output / f"cover.{image_format}"
            if extension in ("ogg", "opus"):
                arguments = ["-i", corpus.source_path(source), "-c", "copy",
                             "-metadata", ogg_picture_comment(cover, image_format), str(path)]
            else:
                arguments = ["-i", corpus.source_path(source), "-i", str(cover), "-map", "0:a", "-map", "1:v",
                             "-c", "copy", "-disposition:v", "attached_pic", str(path)]
            if corpus.encode(identity, arguments):
                corpus.record(identity, family, path, {"source_seconds": 1.37, "cover": image_format})


def _synthesize_vbri(corpus):
    for variant in ("absent", "unicode"):
        source = corpus.source(f"mp3-cbr-no-xing-{variant}")
        if source is None:
            corpus.failures.append({"id": f"mp3-vbri-{variant}", "reason": "source encoder unavailable"})
            continue
        path = corpus.media / f"mp3-vbri-{variant}.mp3"
        path.write_bytes(build_vbri_mp3((corpus.output / source["path"]).read_bytes()))
        corpus.record(f"mp3-vbri-{variant}", "mp3-vbri", path,
                      {"source_seconds": 1.37, "requested_tags": source["expected"]["requested_tags"], "cover": None})


def _double_cover_and_gallery(corpus):
    source = corpus.source("mp3-cbr-xing-numbers")
    if source is not None:
        identity = "mp3-cbr-xing-cover-double"
        path = corpus.media / f"{identity}.mp3"
        if corpus.encode(identity, ["-i", corpus.source_path(source), "-i", str(corpus.output / "cover.jpg"),
                                    "-i", str(corpus.output / "cover.png"), "-map", "0:a", "-map", "1:v", "-map", "2:v",
                                    "-c", "copy", "-disposition:v", "attached_pic", str(path)]):
            corpus.record(identity, "mp3-cbr-xing", path, {"source_seconds": 1.37, "cover": "jpg+png"})
    gallery = cover_gallery(corpus.output)
    if not gallery:
        corpus.failures.append({"id": "cover-gallery", "reason": "Pillow unavailable"})
    for name, (image_path, extension) in gallery.items():
        identity = f"mp3-cbr-xing-gallery-{name}"
        path = corpus.media / f"{identity}.mp3"
        if corpus.encode(identity, ["-i", corpus.source_path(source), "-i", str(image_path), "-map", "0:a", "-map", "1:v",
                                    "-c", "copy", "-disposition:v", "attached_pic", str(path)], echo=False):
            corpus.record(identity, "mp3-cbr-xing", path, {"source_seconds": 1.37, "cover": name})


def _rewrite_layouts(corpus):
    for identity, extension, family, arguments, variant in LAYOUTS:
        source = corpus.source(f"{family}-{variant}")
        if source is None:
            continue
        path = corpus.media / f"{identity}.{extension}"
        if corpus.encode(identity, ["-i", corpus.source_path(source), "-c", "copy", *arguments, str(path)], echo=False):
            corpus.record(identity, family, path, {"source_seconds": 1.37,
                                                   "requested_tags": source["expected"].get("requested_tags", {}), "cover": None})
    for variant, seconds in (("absent", 3786912000), ("numbers", 3786912000), ("unicode", 100)):
        source = corpus.source(f"aac-m4a-{variant}")
        if source is None:
            continue
        path = corpus.media / f"aac-m4a-creation-{variant}.m4a"
        path.write_bytes(patch_mp4_creation_time((corpus.output / source["path"]).read_bytes(), seconds))
        corpus.record(f"aac-m4a-creation-{variant}", "aac-m4a", path,
                      {"source_seconds": 1.37, "requested_tags": source["expected"].get("requested_tags", {}), "cover": None})


def _atypical_paths(corpus):
    nested = corpus.media / "dossier été [x] 東京" / "sous dossier & 'quote'"
    nested.mkdir(parents=True)
    atypical = [("mp3-cbr-xing-nested", nested / "01 - Été.mp3", ["-c:a", "libmp3lame", "-b:a", "128k", "-write_xing", "1"]),
                ("flac-nested", nested / "02 東京.flac", ["-c:a", "flac"]),
                ("wav-nested", nested / "03 spaces  double.wav", ["-c:a", "pcm_s16le"]),
                ("wav-long-name", corpus.media / (("très long nom " * 14).strip() + ".wav"), ["-c:a", "pcm_s16le"])]
    for identity, path, codec in atypical:
        plain = identity.startswith("wav")
        tags = [] if plain else ["-metadata", "title=Chemin atypique"]
        if not corpus.encode(identity, ["-f", "lavfi", "-i", SINE, "-map_metadata", "-1", *codec, *tags, str(path)]):
            continue
        corpus.record(identity, identity.rsplit("-", 1)[0] if identity.endswith("nested") else "wav", path,
                      {"source_seconds": 1.37, "requested_tags": {} if plain else {"title": "Chemin atypique"}, "cover": None})
    for identity, data in [("empty", b""), ("garbage", b"not an audio file\0" * 8),
                           ("truncated-id3", b"ID3\x04\0\0\0\0\x7f\x7fbroken")]:
        path = corpus.media / f"corrupt-{identity}.mp3"
        path.write_bytes(data)
        corpus.record(f"corrupt-{identity}", "corrupt", path, {"readable": False, "cover": None})


def _write_manifest(corpus, scale):
    manifest = {"schema_version": 1, "generator": "synthetic-sine-v1", "scale": scale,
                "ffmpeg_version": run([corpus.ffmpeg, "-version"]).splitlines()[0],
                "entries": corpus.entries, "failures": corpus.failures, "limitations": LIMITATIONS}
    (corpus.output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"files": len(corpus.entries), "failures": len(corpus.failures)}))
    if len(corpus.entries) < 40:
        raise RuntimeError("Corpus has fewer than 40 files; consult manifest failures")


def generate(output, ffmpeg, scale=0, cover_ratio=0.25):
    if output == ROOT or ROOT in output.parents:
        raise ValueError("Choose an output directory outside the checkout")
    output.mkdir(parents=True, exist_ok=False)
    corpus = Corpus(output, ffmpeg)
    corpus.media.mkdir()
    png(output / "cover.png")
    run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(output / "cover.png"),
         "-frames:v", "1", "-threads", "1", str(output / "cover.jpg")])
    _encode_families(corpus)
    _attach_covers(corpus)
    _synthesize_vbri(corpus)
    _double_cover_and_gallery(corpus)
    _rewrite_layouts(corpus)
    _atypical_paths(corpus)
    if scale:
        for identity, kind, path, expected in generate_scale(output, corpus.media, ffmpeg, scale, cover_ratio, corpus.failures):
            corpus.record(identity, kind, path, expected)
    _write_manifest(corpus, scale)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New directory outside the checkout")
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg") or "ffmpeg")
    parser.add_argument("--scale", type=int, default=0, metavar="N",
                        help="add N unique tracks with varied durations (large-library measurements)")
    parser.add_argument("--cover-ratio", type=float, default=0.25,
                        help="share of MP3/FLAC scale tracks carrying a picture (default 0.25)")
    args = parser.parse_args()
    if args.scale < 0 or not 0 <= args.cover_ratio <= 1:
        parser.error("--scale must be >= 0 and --cover-ratio within [0, 1]")
    generate(args.output.resolve(), args.ffmpeg, args.scale, args.cover_ratio)


if __name__ == "__main__":
    main()
