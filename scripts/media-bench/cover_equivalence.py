"""Definition of the cover equivalence between the reference and the native pipelines.

The reference pipeline (ffmpeg re-encodes the embedded picture to JPEG, then Pillow
converts to RGB, shrinks to 600x600 and saves a quality-85 JPEG) and the native one (Pillow
reads the raw embedded bytes) cannot give identical files: ffmpeg's re-encode is lossy and
is the stage the native path skips. Two final covers are *equivalent* when, once decoded to
RGB, they have exactly the same dimensions, a PSNR of at least MIN_PSNR_DB and a mean
absolute error (all channels, 0-255) of at most MAX_MEAN_ABSOLUTE_ERROR.

Measured on development images: real artwork 38-48 dB (MAE 0.4-1.6); a deliberately harsh
fractal image with sharp edges 34.5-36 dB (MAE up to 3.5). The thresholds sit just under
the harshest measurement. Needs Pillow (the backend environment).
"""
import io
import math

MIN_PSNR_DB = 33.0
MAX_MEAN_ABSOLUTE_ERROR = 4.0


def measure(reference, candidate):
    """Compare two JPEG byte strings; returns the measurements and the verdict."""
    from PIL import Image, ImageChops, ImageStat

    with Image.open(io.BytesIO(reference)) as first, Image.open(io.BytesIO(candidate)) as second:
        first, second = first.convert("RGB"), second.convert("RGB")
        if first.size != second.size:
            return {"equivalent": False, "reason": "dimensions", "reference_size": list(first.size),
                    "candidate_size": list(second.size)}
        difference = ImageChops.difference(first, second)
        mean_error = sum(ImageStat.Stat(difference).mean) / 3
        mean_square = sum(ImageStat.Stat(difference.point(lambda value: value * value)).mean) / 3
        peak = max(extreme[1] for extreme in difference.getextrema())
    psnr = math.inf if mean_square == 0 else 10 * math.log10(255 ** 2 / mean_square)
    equivalent = psnr >= MIN_PSNR_DB and mean_error <= MAX_MEAN_ABSOLUTE_ERROR
    return {"equivalent": equivalent, "psnr_db": None if psnr == math.inf else round(psnr, 2),
            "mean_absolute_error": round(mean_error, 3), "peak_error": peak, "size": list(first.size)}
