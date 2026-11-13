import io
import tarfile

import pytest

from app.utils import zip_safety


def _tar(name: str) -> tarfile.TarFile:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tf:
        info = tarfile.TarInfo(name)
        info.size = 1
        tf.addfile(info, io.BytesIO(b"x"))
    buffer.seek(0)
    return tarfile.open(fileobj=buffer, mode="r")


@pytest.mark.parametrize("name", ["CON", "dossier/com1.txt", "Lpt9", "nul.mp4", "a/AUX/b.txt", "video.mp4:flux", "fin."])
def test_windows_rejects_reserved_names_and_streams(monkeypatch, tmp_path, name):
    monkeypatch.setattr(zip_safety, "_WINDOWS", True)
    with pytest.raises(zip_safety.UnsafeZipError, match="Windows"):
        zip_safety.safe_extract_tar(_tar(name), tmp_path)


@pytest.mark.parametrize("name", ["console.mp4", "comptes/com10.txt", "Cours 10h30.mp4"])
def test_windows_keeps_ordinary_names(monkeypatch, tmp_path, name):
    monkeypatch.setattr(zip_safety, "_WINDOWS", True)
    zip_safety.safe_extract_tar(_tar(name), tmp_path)
    assert (tmp_path / name).read_bytes() == b"x"


def test_other_systems_keep_colons(monkeypatch, tmp_path):
    monkeypatch.setattr(zip_safety, "_WINDOWS", False)
    zip_safety.safe_extract_tar(_tar("Cours 10:30.mp4"), tmp_path)
    assert (tmp_path / "Cours 10:30.mp4").exists()
