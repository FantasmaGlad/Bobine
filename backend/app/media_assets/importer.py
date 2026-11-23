"""Import d'un média visuel (vidéo ou image) dans son espace."""
import logging
import shutil
import uuid
from pathlib import Path

from app.config import settings
from app.models import ImportSource
from app.utils.import_jobs import update_job
from app.utils.importer.formats import IMAGE_EXTENSIONS, is_image_background
from app.utils.importer.pipeline import Target, import_media, save, thumbnail_or_placeholder, wait_if_watched
from app.utils.media_formats import PLATFORM_DECODED_IMAGE as PLATFORM_DECODED

from .collection import AssetCollection

logger = logging.getLogger(__name__)


def _target(collection: AssetCollection) -> Target:
    return Target(directory=collection.directory, prefix=collection.file_prefix, label=collection.label,
                  strict_codec=True, placeholder=True)


def _title(original_filename: str) -> str:
    return Path(original_filename).stem.replace("_", " ").replace("-", " ")


def _image_thumbnail(source: Path, file_id: str) -> str:
    from PIL import Image

    with Image.open(source) as img:
        img = img.convert("RGB")
        img.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
        dest = Path(settings.thumbnails_dir) / f"thumb_{file_id}.jpg"
        img.save(dest, "JPEG", quality=92, optimize=True)
    return str(dest)


def _flat(img):
    if img.mode.startswith("I;16") or img.mode in ("I", "F"):
        return img.convert("I").point(lambda value: value * (1 / 256)).convert("L")
    alpha = "A" in img.getbands() or "transparency" in img.info
    return img.convert("RGBA" if alpha else "RGB")


def _store_image(collection: AssetCollection, source: Path, original_filename: str, file_id: str) -> Path:
    from PIL import Image

    stem = Path(collection.directory()) / f"{collection.file_prefix}_{file_id}"
    if is_image_background(original_filename):
        dest = stem.with_suffix(Path(original_filename).suffix.lower())
        shutil.move(source, dest)
        return dest
    dest = stem.with_suffix(".webp")
    try:
        with Image.open(source) as img:
            if getattr(img, "n_frames", 1) > 1:
                img.save(dest, "WEBP", save_all=True, quality=90, method=4, loop=img.info.get("loop", 0))
            else:
                _flat(img).save(dest, "WEBP", quality=92, method=4)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    source.unlink()
    logger.info("%s %s converti en WebP pour l'affichage", collection.label, original_filename)
    return dest


def _decoded_by_platform(source: Path, original_filename: str, pillow_error: Exception) -> Path:
    from app.utils.image_decode import decode_to_png

    if Path(original_filename).suffix.lower() not in PLATFORM_DECODED:
        raise ValueError(f"Le fichier {original_filename} n'est pas une image valide : {pillow_error}")
    try:
        decoded = decode_to_png(source, original_filename)
    except ValueError as e:
        raise ValueError(f"Le fichier {original_filename} n'a pas pu être lu : {e}") from e
    source.unlink(missing_ok=True)
    logger.info("Image %s décodée par la plateforme", original_filename)
    return decoded


def import_asset_image(collection: AssetCollection, src_path: str, original_filename: str, job_id: str | None = None):
    """Image : pipeline dédié, sans ffmpeg ; un format que les navigateurs n'affichent pas est converti en WebP."""
    from PIL import Image, UnidentifiedImageError

    update_job(job_id, stage="probing")
    Path(collection.directory()).mkdir(parents=True, exist_ok=True)
    Path(settings.thumbnails_dir).mkdir(parents=True, exist_ok=True)

    source = Path(src_path)
    try:
        with Image.open(source) as img:
            img.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        source = _decoded_by_platform(source, original_filename, e)

    file_id = uuid.uuid4().hex
    try:
        dest_path = _store_image(collection, source, original_filename, file_id)
    except (OSError, ValueError, Image.DecompressionBombError) as e:
        raise ValueError(f"Le fichier {original_filename} n'a pas pu être converti : {e}")

    update_job(job_id, stage="thumbnail")
    thumbnail_path = thumbnail_or_placeholder(lambda: _image_thumbnail(dest_path, file_id), dest_path,
                                              original_filename, True, settings.thumbnails_dir)
    update_job(job_id, stage="saving")
    asset = collection.model(file_path=str(dest_path), title=_title(original_filename), duration_seconds=None,
                             thumbnail_path=thumbnail_path)
    return save(asset, collection.imported_event, lambda row: row.title, [dest_path, thumbnail_path],
                f"{collection.label} (image)", original_filename)


def import_asset(collection: AssetCollection, src_path: str, original_filename: str, source: ImportSource,
                 job_id: str | None = None):
    """Importe un média visuel dans son espace : même chaîne que import_video, image traitée à part."""
    wait_if_watched(src_path, original_filename, source)
    if Path(src_path).suffix.lower() in IMAGE_EXTENSIONS:
        return import_asset_image(collection, src_path, original_filename, job_id=job_id)
    title = _title(original_filename)

    def build(dest: Path, meta: dict, thumbnail: str | None):
        return collection.model(file_path=str(dest), title=title, duration_seconds=meta["duration_seconds"], thumbnail_path=thumbnail)

    return import_media(src_path, original_filename, source, job_id, _target(collection), settings.thumbnails_dir, build,
                        collection.imported_event, lambda asset: asset.title)
