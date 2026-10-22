"""The row comparison that decides whether a faster import produced the same library."""
import base64
import importlib.util
import io
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def bench():
    spec = importlib.util.spec_from_file_location("media_import_bench", ROOT / "scripts" / "media-bench" / "import_bench.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def row(title="A", duration=1.37, **extra):
    base = {"title": title, "artist": "X", "album": None, "album_artist": None, "track_number": 1,
            "disc_number": None, "year": 2024, "genre": None, "duration_seconds": duration}
    base.update(extra)
    return base


def jpeg(color=(30, 60, 120), size=(120, 90)):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", size, color)
    ImageDraw.Draw(image).ellipse([10, 10, 80, 70], outline=(250, 250, 0), width=5)
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def run(rows, covers=()):
    return {"rows": rows, "covers": [{"file": name, "data": data} for name, data in covers]}


def test_identical_libraries_have_no_difference_even_if_row_order_differs(bench):
    cover = jpeg()
    left = run([row("A"), row("B", 2.0)], [("a.mp3", cover)])
    right = run([row("B", 2.0), row("A")], [("a.mp3", cover)])
    assert bench.compare_rows(left, right) == []


def test_duration_tolerance_is_fifty_milliseconds(bench):
    assert bench.compare_rows(run([row(duration=1.37)]), run([row(duration=1.419)])) == []
    assert bench.compare_rows(run([row(duration=1.37)]), run([row(duration=1.421)]))
    assert bench.compare_rows(run([row(duration=None)]), run([row(duration=1.0)]))


@pytest.mark.parametrize("change", [{"artist": "Y"}, {"year": 2023}, {"genre": "G"}, {"track_number": 2}])
def test_any_other_field_difference_is_reported(bench, change):
    assert bench.compare_rows(run([row()]), run([row(**change)]))


def test_missing_rows_and_different_covers_are_reported(bench):
    assert bench.compare_rows(run([row("A"), row("B")]), run([row("A")]))
    assert bench.compare_rows(run([row()], [("a.mp3", jpeg())]), run([row()], []))
    # Same file name, picture that is visibly different: not equivalent.
    assert bench.compare_rows(run([row()], [("a.mp3", jpeg())]), run([row()], [("a.mp3", jpeg((255, 255, 255)))]))


def test_a_slightly_different_encoding_of_the_same_cover_is_equivalent(bench):
    from PIL import Image

    original = base64.b64decode(jpeg())
    out = io.BytesIO()
    Image.open(io.BytesIO(original)).save(out, "JPEG", quality=80)
    other = base64.b64encode(out.getvalue()).decode("ascii")
    assert other != jpeg()
    assert bench.compare_rows(run([row()], [("a.mp3", jpeg())]), run([row()], [("a.mp3", other)])) == []
