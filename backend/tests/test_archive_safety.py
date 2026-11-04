"""Extraction sûre des archives d'import : ZIP et tar reconnus au contenu, aucun fichier écrit hors de la destination,
liens et fichiers spéciaux refusés avant toute écriture."""
import io
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.utils.zip_safety import InvalidArchiveError, UnsafeZipError, safe_extract_archive  # noqa: E402


def _tar(path: Path, mode: str, members: list[tuple[tarfile.TarInfo, bytes | None]]) -> Path:
    with tarfile.open(path, mode) as tf:
        for info, data in members:
            tf.addfile(info, io.BytesIO(data) if data is not None else None)
    return path


def _file(name: str, data: bytes) -> tuple[tarfile.TarInfo, bytes]:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    return info, data


@pytest.mark.parametrize("suffix,mode", [(".tar", "w"), (".tar.gz", "w:gz"), (".tar.xz", "w:xz"), (".tar.bz2", "w:bz2")])
def test_tar_formats_are_extracted(tmp_path, suffix, mode):
    archive = _tar(tmp_path / f"cours{suffix}", mode, [_file("cours/01 - Intro.mp3", b"mp3"), _file("cours/02.flac", b"flac")])
    dest = tmp_path / "dest"
    dest.mkdir()
    safe_extract_archive(archive, dest)
    assert (dest / "cours/01 - Intro.mp3").read_bytes() == b"mp3"
    assert (dest / "cours/02.flac").read_bytes() == b"flac"


def test_zip_is_recognised_by_content_whatever_its_name(tmp_path):
    archive = tmp_path / "upload.tmp"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("a.mp3", b"x")
    dest = tmp_path / "dest"
    dest.mkdir()
    safe_extract_archive(archive, dest)
    assert (dest / "a.mp3").read_bytes() == b"x"


def test_tar_traversal_is_refused_before_any_write(tmp_path):
    archive = _tar(tmp_path / "x.tar", "w", [_file("ok.mp3", b"ok"), _file("../evade.mp3", b"bad")])
    dest = tmp_path / "dest"
    dest.mkdir()
    with pytest.raises(UnsafeZipError):
        safe_extract_archive(archive, dest)
    assert list(dest.iterdir()) == []
    assert not (tmp_path / "evade.mp3").exists()


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE])
def test_links_and_special_files_are_refused(tmp_path, kind):
    info = tarfile.TarInfo("piège")
    info.type = kind
    info.linkname = "/etc/passwd"
    archive = _tar(tmp_path / "x.tar", "w", [(info, None)])
    dest = tmp_path / "dest"
    dest.mkdir()
    with pytest.raises(UnsafeZipError):
        safe_extract_archive(archive, dest)
    assert list(dest.iterdir()) == []


def test_absolute_member_is_refused(tmp_path):
    archive = _tar(tmp_path / "x.tar", "w", [_file("/tmp/absolu.mp3", b"x")])
    dest = tmp_path / "dest"
    dest.mkdir()
    with pytest.raises(UnsafeZipError):
        safe_extract_archive(archive, dest)


def test_unknown_format_is_a_clear_error(tmp_path):
    archive = tmp_path / "x.7z"
    archive.write_bytes(b"7z\xbc\xaf\x27\x1c pas un tar")
    with pytest.raises(InvalidArchiveError):
        safe_extract_archive(archive, tmp_path)
