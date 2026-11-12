"""Definition of the cover equivalence between the reference and the native pipelines."""
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
