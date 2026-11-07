"""Liste unique des extensions d'import : parité avec le frontend et import d'archives de médias."""
import re
import tarfile
import zipfile
from pathlib import Path

import pytest

from app.utils import media_formats
from app.utils.archive_import import import_media_archive

FRONTEND = Path(__file__).resolve().parents[2] / "frontend/src/lib/mediaFiles.ts"


def frontend_list(name):
    source = FRONTEND.read_text(encoding="utf-8")
    body = re.search(rf"export const {name} = \[(.*?)\]", source, re.S).group(1)
    return re.findall(r'"([^"]+)"', body)


@pytest.mark.skipif(not FRONTEND.exists(), reason="frontend absent de cette arborescence")
def test_frontend_lists_equal_the_backend_lists():
    assert set(frontend_list("RADIO_AUDIO_EXTENSIONS")) == set(media_formats.RADIO_AUDIO)
    assert set(frontend_list("COURSE_AUDIO_EXTENSIONS")) == set(media_formats.COURSE_AUDIO)
    assert tuple(frontend_list("ARCHIVE_EXTENSIONS")) == media_formats.ARCHIVE
    # le frontend reconnaît plus de vidéos (détection avant envoi) ; tout ce que le serveur importe doit y figurer
    assert {"." + ext for ext in frontend_list("VIDEO_EXTENSIONS")} >= set(media_formats.VIDEO)
    assert {"." + ext for ext in frontend_list("SUBTITLE_EXTENSIONS")} == set(media_formats.SUBTITLE)


def test_importers_share_the_single_lists():
    from app.storage import paths
    from app.utils import audio_importer, importer, radio_utils, zip_safety
    assert radio_utils.AUDIO_EXTENSIONS is media_formats.RADIO_AUDIO
    assert audio_importer.AUDIO_EXTENSIONS is media_formats.COURSE_AUDIO
    assert importer.SUPPORTED_EXTENSIONS is media_formats.VIDEO
    assert zip_safety.ARCHIVE_EXTENSIONS is media_formats.ARCHIVE
    assert paths.VIDEO_EXTENSIONS is media_formats.VIDEO and paths.AUDIO_EXTENSIONS == media_formats.SUPPORT_AUDIO


def make_zip(path):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("a.mp4", b"1")
        z.writestr("dossier/b.MKV", b"2")
        z.writestr("notes.txt", b"x")
        z.writestr(".cache.mp4", b"3")
        z.writestr("__MACOSX/c.mp4", b"4")
        z.writestr("mauvais.avi", b"5")


def test_archive_imports_each_media_file_and_survives_one_failure(tmp_path):
    archive = tmp_path / "lot.zip"
    make_zip(archive)
    seen = []

    def one(path, name):
        if name == "mauvais.avi":
            raise ValueError("illisible")
        seen.append(name)
        return object()

    result = import_media_archive(str(archive), None, media_formats.VIDEO, one, "vidéo")
    assert sorted(seen) == ["a.mp4", "b.MKV"] and len(result) == 2
    assert not archive.exists()


def test_archive_reads_a_tar_too(tmp_path):
    archive = tmp_path / "lot.tar.gz"
    (tmp_path / "x.mp4").write_bytes(b"1")
    with tarfile.open(archive, "w:gz") as t:
        t.add(tmp_path / "x.mp4", arcname="x.mp4")
    seen = []
    import_media_archive(str(archive), None, media_formats.VIDEO, lambda p, n: seen.append(n) or object(), "vidéo")
    assert seen == ["x.mp4"]


def test_archive_without_media_or_with_only_failures_is_an_error(tmp_path):
    empty = tmp_path / "vide.zip"
    with zipfile.ZipFile(empty, "w") as z:
        z.writestr("notes.txt", b"x")
    with pytest.raises(ValueError, match="Aucun fichier vidéo"):
        import_media_archive(str(empty), None, media_formats.VIDEO, lambda p, n: object(), "vidéo")
    broken = tmp_path / "casse.zip"
    make_zip(broken)

    def always_fails(path, name):
        raise RuntimeError("non")

    with pytest.raises(ValueError, match="Aucun fichier de l'archive"):
        import_media_archive(str(broken), None, media_formats.VIDEO, always_fails, "vidéo")
    assert not broken.exists()


def test_archive_cancelled_between_files_stops(tmp_path, monkeypatch):
    archive = tmp_path / "lot.zip"
    make_zip(archive)
    from app.utils import archive_import
    from app.utils.import_jobs import JobCancelledError
    monkeypatch.setattr(archive_import, "is_job_cancelled", lambda job_id: True)
    with pytest.raises(JobCancelledError):
        import_media_archive(str(archive), "job", media_formats.VIDEO, lambda p, n: object(), "vidéo")


def test_7z_is_refused_with_an_explicit_message(tmp_path):
    from app.utils.zip_safety import InvalidArchiveError, safe_extract_archive
    archive = tmp_path / "lot.7z"
    archive.write_bytes(b"7z\xbc\xaf\x27\x1c" + b"\x00" * 20)
    with pytest.raises(InvalidArchiveError, match="7z"):
        safe_extract_archive(archive, tmp_path / "out")
