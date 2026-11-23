"""Décodage par ImageDecoder d'Android (AVIF, HEIC), appelé depuis Python par Chaquopy."""
from __future__ import annotations

from pathlib import Path

MAX_PIXELS = 40_000_000


def sample_size(width: int, height: int, max_pixels: int = MAX_PIXELS) -> int:
    """Plus petit facteur de réduction (puissance de 2) qui ramène l'image sous la borne de pixels."""
    size = 1
    while (width // size) * (height // size) > max_pixels:
        size *= 2
    return size


def decode(source: Path, dest: Path, extension: str) -> None:
    from java import dynamic_proxy, jclass

    image_decoder = jclass("android.graphics.ImageDecoder")
    bitmap_class = jclass("android.graphics.Bitmap")

    class Header(dynamic_proxy(image_decoder.OnHeaderDecodedListener)):
        def onHeaderDecoded(self, decoder, info, _source):
            decoder.setAllocator(image_decoder.ALLOCATOR_SOFTWARE)
            dimensions = info.getSize()
            decoder.setTargetSampleSize(sample_size(dimensions.getWidth(), dimensions.getHeight()))

    bitmap = image_decoder.decodeBitmap(image_decoder.createSource(jclass("java.io.File")(str(source))), Header())
    stream = jclass("java.io.FileOutputStream")(str(dest))
    try:
        if not bitmap.compress(bitmap_class.CompressFormat.PNG, 100, stream):
            raise ValueError("Android n'a pas pu réécrire l'image")
    finally:
        stream.close()
        bitmap.recycle()
