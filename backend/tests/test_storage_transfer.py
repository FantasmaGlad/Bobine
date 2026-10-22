"""Stockage externe : copie vérifiée (intégrité, reprise, annulation, source modifiée), plan d'import, export, appareils portables."""

import hashlib
import os
from pathlib import Path

import pytest

os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")

from app.storage import portable, transfer  # noqa: E402
from app.storage.transfer import Cancelled, TransferError, copy_verified, export_file, plan_import  # noqa: E402


@pytest.fixture()
def staging(tmp_path, monkeypatch):
    monkeypatch.setattr(transfer, "staging_root", lambda: _mk(tmp_path / "staging"))
    return _mk(tmp_path / "staging")


def _mk(path: Path) -> Path:
    (path / "parts").mkdir(parents=True, exist_ok=True)
    return path


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture()
def source(tmp_path):
    data = os.urandom(3 * 1024 * 1024 + 123)
    path = tmp_path / "usb" / "cours.mp4"
    path.parent.mkdir()
    path.write_bytes(data)
    return path


def part_for(source, staging):
    st = source.stat()
    return transfer.part_path_for("U-1", "cours.mp4", st.st_size, st.st_mtime_ns)


def test_copy_is_exact_and_leaves_the_source_alone(source, staging, tmp_path):
    before = (sha(source), source.stat().st_mtime_ns)
    seen = []
    result = copy_verified(str(source), str(tmp_path / "out.mp4"), part=part_for(source, staging), on_bytes=seen.append, chunk=1024 * 1024)
    assert sha(tmp_path / "out.mp4") == before[0] == result["sha256"] and result["size"] == source.stat().st_size
    assert sum(seen) == result["size"] and result["resumed_from"] == 0
    assert (sha(source), source.stat().st_mtime_ns) == before
    assert not part_for(source, staging).exists() and not Path(str(part_for(source, staging)) + ".json").exists()


def test_cancel_removes_partial_files_and_keeps_source(source, staging, tmp_path):
    calls = {"n": 0}

    def cancelled():
        calls["n"] += 1
        return calls["n"] > 2

    with pytest.raises(Cancelled):
        copy_verified(str(source), str(tmp_path / "out.mp4"), part=part_for(source, staging), is_cancelled=cancelled, chunk=512 * 1024)
    assert not (tmp_path / "out.mp4").exists() and not part_for(source, staging).exists()
    assert source.exists()


def test_interrupted_copy_resumes_at_the_byte_and_verifies(source, staging, tmp_path):
    """Retrait brutal en cours de copie : le `.part` est conservé et la reprise ne recopie pas le début."""
    original = open

    state = {"reads": 0}

    class Flaky:
        def __init__(self, handle):
            self.handle = handle

        def read(self, n=-1):
            state["reads"] += 1
            if state["reads"] == 3:
                raise OSError(5, "Input/output error")
            return self.handle.read(n)

        def seek(self, *a):
            return self.handle.seek(*a)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            self.handle.close()

    import builtins

    def fake_open(path, mode="r", *a, **k):
        handle = original(path, mode, *a, **k)
        return Flaky(handle) if str(path) == str(source) and "rb" in mode else handle

    part = part_for(source, staging)
    builtins.open = fake_open
    try:
        with pytest.raises(TransferError) as exc:
            copy_verified(str(source), str(tmp_path / "out.mp4"), part=part, chunk=1024 * 1024)
    finally:
        builtins.open = original
    assert exc.value.code == "source_io" and part.exists() and part.stat().st_size == 2 * 1024 * 1024  # début conservé

    seen = []
    result = copy_verified(str(source), str(tmp_path / "out.mp4"), part=part, on_bytes=seen.append, chunk=1024 * 1024)
    assert result["resumed_from"] == 2 * 1024 * 1024 and sha(tmp_path / "out.mp4") == sha(source)
    assert sum(seen) == source.stat().st_size  # la progression compte aussi la partie déjà copiée


def test_resume_is_refused_when_source_changed_or_prefix_differs(source, staging, tmp_path):
    part = part_for(source, staging)
    part.write_bytes(source.read_bytes()[:1000])
    Path(str(part) + ".json").write_text('{"size": 1, "mtime_ns": 1}')  # source différente de celle du `.part`
    result = copy_verified(str(source), str(tmp_path / "out.mp4"), part=part)
    assert result["resumed_from"] == 0 and sha(tmp_path / "out.mp4") == sha(source)

    st = source.stat()
    part2 = transfer.part_path_for("U-2", "cours.mp4", st.st_size, st.st_mtime_ns)
    part2.write_bytes(b"corrompu" * 200)  # préfixe qui ne correspond pas à la source
    Path(str(part2) + ".json").write_text(f'{{"size": {st.st_size}, "mtime_ns": {st.st_mtime_ns}}}')
    result = copy_verified(str(source), str(tmp_path / "out2.mp4"), part=part2)
    assert result["resumed_from"] == 0 and sha(tmp_path / "out2.mp4") == sha(source)


def test_resume_disabled_for_portable_sources(source, staging, tmp_path):
    part = part_for(source, staging)
    part.write_bytes(source.read_bytes()[:1000])
    Path(str(part) + ".json").write_text(f'{{"size": {source.stat().st_size}, "mtime_ns": {source.stat().st_mtime_ns}}}')
    assert copy_verified(str(source), str(tmp_path / "o.mp4"), part=part, verify_source=False)["resumed_from"] == 0


def test_source_modified_during_copy_is_detected(source, staging, tmp_path):
    first = {"done": False}

    def mutate(n):
        if not first["done"]:
            first["done"] = True
            os.utime(source, ns=(1, 1))

    with pytest.raises(TransferError) as exc:
        copy_verified(str(source), str(tmp_path / "out.mp4"), part=part_for(source, staging), on_bytes=mutate, chunk=1024 * 1024)
    assert exc.value.code == "source_changed" and not (tmp_path / "out.mp4").exists()


def test_corrupted_write_is_caught_by_the_verification(source, staging, tmp_path, monkeypatch):
    real = transfer._sha_of_file
    monkeypatch.setattr(transfer, "_sha_of_file", lambda path: "0" * 64 if str(path).endswith(".part") else real(path))
    with pytest.raises(TransferError) as exc:
        copy_verified(str(source), str(tmp_path / "out.mp4"), part=part_for(source, staging))
    assert exc.value.code == "verify_failed" and not (tmp_path / "out.mp4").exists()


def test_space_check_keeps_a_reserve():
    with pytest.raises(TransferError) as exc:
        transfer.check_space(10**9, free=10**9)
    assert exc.value.code == "insufficient_space" and exc.value.extra["needed_bytes"] > 10**9 and exc.value.status == 409
    transfer.check_space(10**9, free=transfer.needed_bytes(10**9))
    transfer.check_space(10**9, already=10**9 - 10, free=transfer.RESERVE_BYTES + 100)  # le début déjà copié ne compte pas


def test_purge_staging_removes_stale_parts_and_orphan_workdirs(staging):
    old, fresh = staging / "parts" / "old.part", staging / "parts" / "new.part"
    old.write_bytes(b"1")
    fresh.write_bytes(b"2")
    os.utime(old, (1, 1))
    (staging / "jobabc").mkdir()
    (staging / "jobabc" / "x").write_bytes(b"3")
    assert transfer.purge_staging() == 2
    assert not old.exists() and fresh.exists() and not (staging / "jobabc").exists()


@pytest.fixture()
def tree(tmp_path):
    root = tmp_path / "vol"
    for rel in ("Cours/a.mp4", "Cours/b.mkv", "Cours/RPM/c.mp4", "Album/01 - a.mp3", "Album/02 - b.mp3", "Radio/x.flac", "Radio/y.mp3", "doc.txt"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(b"data-" + rel.encode())
    return root


def test_plan_import_groups_by_kind(tree):
    videos = plan_import(str(tree), [{"path": "Cours"}], "video", "U-1")
    assert [u.key for u in videos.units] == ["Cours/a.mp4", "Cours/b.mkv", "Cours/RPM/c.mp4"] or sorted(u.key for u in videos.units) == sorted(["Cours/a.mp4", "Cours/b.mkv", "Cours/RPM/c.mp4"])
    assert all(len(u.files) == 1 and u.kind == "video" for u in videos.units) and videos.total_files == 3
    course = plan_import(str(tree), [{"path": "Album"}], "audio_course", "U-1")
    assert len(course.units) == 1 and course.units[0].title == "Album" and len(course.units[0].files) == 2
    radio = plan_import(str(tree), [{"path": "Radio"}, {"path": "Radio/x.flac"}], "radio", "U-1")
    assert sorted(u.key for u in radio.units) == ["Radio/x.flac", "Radio/y.mp3"]  # pas de doublon
    none = plan_import(str(tree), [{"path": "doc.txt"}], "video", "U-1")
    assert none.units == [] and none.skipped == [{"path": "doc.txt", "reason": "no_media"}]
    with pytest.raises(TransferError):
        plan_import(str(tree), [{"path": "Cours"}], "bogus", "U-1")
    with pytest.raises(Exception):
        plan_import(str(tree), [{"path": "../x"}], "video", "U-1")


def test_export_never_overwrites_and_writes_atomically(tmp_path):
    src = tmp_path / "local.mp4"
    src.write_bytes(os.urandom(200_000))
    dest = tmp_path / "vol"
    dest.mkdir()
    (dest / "Mon cours.mp4").write_bytes(b"existant")
    seen = []
    result = export_file(str(src), str(dest), "Mon cours.mp4", on_bytes=seen.append, chunk=50_000)
    assert Path(result["path"]).name == "Mon cours (2).mp4" and sha(result["path"]) == sha(src) and sum(seen) == 200_000
    assert (dest / "Mon cours.mp4").read_bytes() == b"existant" and not list(dest.glob(".bobine-*"))
    with pytest.raises(Cancelled):
        export_file(str(src), str(dest), "annule.mp4", is_cancelled=lambda: True)
    assert not (dest / "annule.mp4").exists() and not list(dest.glob(".bobine-*"))


# ---------------------------------------------------------------------------------------------------------
# Appareils portables (analyseurs testés sur des sorties types : NON validés sur matériel)
# ---------------------------------------------------------------------------------------------------------

GIO = """Drive(0): SAMSUNG MZVL2512HDJD
  Type: GProxyDrive (GProxyVolumeMonitorUDisks2)
  ids:
   unix-device: '/dev/nvme0n1'
Volume(0): Pixel 7
  Type: GProxyVolume (GProxyVolumeMonitorMTP)
  ids:
   unix-device: '/dev/bus/usb/001/007'
  can_mount=1
  should_automount=1
  activation_root=mtp://Google_Pixel_7_ABC123/
Volume(1): iPhone de Léa
  Type: GProxyVolume (GProxyVolumeMonitorAfc)
  ids:
   unix-device: '/dev/bus/usb/001/009'
  activation_root=afc://00008110-000A1234/
Volume(2): partage
  activation_root=smb://nas/partage/
Mount(0): Pixel 7 -> mtp://Google_Pixel_7_ABC123/
  Type: GDaemonMount
  default_location=mtp://Google_Pixel_7_ABC123/
Mount(1): malefique sur 192.168.1.72 -> sftp://malefique@192.168.1.72/
  default_location=sftp://malefique@192.168.1.72/home/malefique
"""


def test_gio_output_lists_only_portable_devices():
    devices = {d.name: d for d in portable.parse_gio_mounts(GIO)}
    assert set(devices) == {"Pixel 7", "iPhone de Léa"}  # ni le SMB ni le SFTP ni le NVMe
    pixel = devices["Pixel 7"]
    assert pixel.scheme == "mtp" and pixel.state == "mounted" and pixel.bus == "001" and pixel.dev == "007"
    assert devices["iPhone de Léa"].scheme == "afc" and devices["iPhone de Léa"].state == "ready"
    public = pixel.as_dict()
    assert public["read_only"] is True and public["direct_playback"] is False and "uri" not in public and "root" not in public


def test_fuse_root_matches_decoded_host(tmp_path):
    gvfs = tmp_path / "gvfs"
    (gvfs / "mtp:host=Google_Pixel_7_ABC123").mkdir(parents=True)
    (gvfs / "mtp:host=%5Busb%3A001%2C008%5D").mkdir()
    assert portable.fuse_root_for("mtp://Google_Pixel_7_ABC123/", str(gvfs)).endswith("Google_Pixel_7_ABC123")
    assert portable.fuse_root_for("mtp://[usb:001,008]/", str(gvfs)).endswith("%5Busb%3A001%2C008%5D")
    assert portable.fuse_root_for("mtp://autre/", str(gvfs)) is None


@pytest.mark.parametrize("message,state,hint", [
    ("Error mounting location: The device is locked", "locked", "unlock_device"),
    ("Error: Could not connect to lockdownd. Exiting. (pair)", "needs_approval", "accept_on_device"),
    ("Device or resource busy", "busy", "close_other_app"),
    ("Error mounting location: Unable to open MTP device “[usb:001,007]”", "not_ready", "unlock_and_transfer_mode"),
])
def test_mount_error_states(message, state, hint):
    assert portable.classify_mount_error(message) == (state, hint)
    assert hint in portable.HINT_MESSAGES


def test_usb_candidates_detected_without_gvfs_and_merged():
    candidates = portable.parse_sysfs_usb([
        {"busnum": "1", "devnum": "7", "idVendor": "18d1", "idProduct": "4ee1", "product": "Pixel 7", "manufacturer": "Google",
         "interfaces": [{"class": "ff", "subclass": "ff", "protocol": "00", "name": "MTP"}]},
        {"busnum": "1", "devnum": "9", "idVendor": "05ac", "idProduct": "12a8", "product": "iPhone", "manufacturer": "Apple Inc.",
         "interfaces": [{"class": "ff", "subclass": "fe", "protocol": "02", "name": None}]},
        {"busnum": "1", "devnum": "3", "idVendor": "046d", "idProduct": "c077", "product": "Souris", "manufacturer": "Logitech",
         "interfaces": [{"class": "03", "subclass": "01", "protocol": "02", "name": None}]},
        {"busnum": "1", "devnum": "4", "idVendor": "04a9", "idProduct": "3139", "product": "Appareil photo", "manufacturer": "Canon",
         "interfaces": [{"class": "06", "subclass": "01", "protocol": "01", "name": None}]},
    ])
    assert [(d.name, d.scheme, d.state) for d in candidates] == [
        ("Google Pixel 7", "mtp", "detected"), ("Apple Inc. iPhone", "afc", "detected"), ("Canon Appareil photo", "mtp", "detected")]
    merged = portable.merge(portable.parse_gio_mounts(GIO), candidates)
    names = [d.name for d in merged]
    assert "Pixel 7" in names and "Google Pixel 7" not in names  # déjà proposé par GVFS : pas de doublon
    assert "Canon Appareil photo" in names
