"""Stockage externe : sécurité de chemin (traversée, liens symboliques), exploration paginée, ensembles média."""

import os

import pytest

from app.storage import paths
from app.storage.paths import PathError, clean_rel_path, list_directory, resolve_within, walk_media


@pytest.mark.parametrize("bad", ["../etc/passwd", "a/../../b", "/etc/passwd", "C:/x", "a\\b", "a\x00b", "x/" * 20 + "y", "a" * 5000])
def test_hostile_paths_are_rejected(bad):
    with pytest.raises(PathError) as exc:
        clean_rel_path(bad)
    assert exc.value.code == "bad_path"


def test_clean_rel_path_normalizes():
    assert clean_rel_path("") == "" and clean_rel_path(None) == ""
    assert clean_rel_path("a//b/./c/") == "a/b/c"
    assert clean_rel_path("Cours RPM/101 été.mp4") == "Cours RPM/101 été.mp4"


@pytest.fixture()
def volume(tmp_path):
    root = tmp_path / "vol"
    (root / "Cours" / "RPM").mkdir(parents=True)
    (root / "Musique").mkdir()
    for name in ("b.mp4", "A.mkv", "notes.txt", ".hidden.mp4", "z.mp3", "cover.jpg", "sub.srt"):
        (root / "Cours" / name).write_bytes(b"x" * 10)
    (root / "Cours" / "RPM" / "101.mp4").write_bytes(b"y" * 20)
    (root / "Musique" / "t1.flac").write_bytes(b"z" * 5)
    (root / "$RECYCLE.BIN").mkdir()
    (root / "System Volume Information").mkdir()
    (root / "lost+found").mkdir()
    return root


def test_listing_dirs_first_sorted_hidden_filtered(volume):
    listing = list_directory(str(volume), "")
    assert [e.name for e in listing.entries] == ["Cours", "Musique"]
    cours = list_directory(str(volume), "Cours")
    names = [e.name for e in cours.entries]
    assert names == ["RPM", "A.mkv", "b.mp4", "cover.jpg", "notes.txt", "sub.srt", "z.mp3"]  # dossiers d'abord, insensible à la casse
    media = {e.name: e.media for e in cours.entries}
    assert media["A.mkv"] == "video" and media["z.mp3"] == "audio" and media["cover.jpg"] == "image" and media["notes.txt"] is None
    assert list_directory(str(volume), "Cours", show_hidden=True).total == cours.total + 1
    only = list_directory(str(volume), "Cours", media_only=True)
    assert [e.name for e in only.entries] == ["RPM", "A.mkv", "b.mp4", "cover.jpg", "z.mp3"]
    assert cours.parent == "" and list_directory(str(volume), "Cours/RPM").parent == "Cours"


def test_pagination(volume):
    page1 = list_directory(str(volume), "Cours", offset=0, limit=3)
    page2 = list_directory(str(volume), "Cours", offset=3, limit=3)
    assert page1.total == 7 and len(page1.entries) == 3 and len(page2.entries) == 3
    assert not set(e.name for e in page1.entries) & set(e.name for e in page2.entries)
    assert list_directory(str(volume), "Cours", limit=10_000).limit == paths.MAX_PAGE


def test_scan_cap_marks_truncated(volume, monkeypatch):
    monkeypatch.setattr(paths, "MAX_SCAN_ENTRIES", 3)
    assert list_directory(str(volume), "Cours").truncated is True


def test_symlink_escape_is_not_followed(volume, tmp_path):
    secret = tmp_path / "secret"
    secret.mkdir()
    (secret / "pwd.mp4").write_bytes(b"s")
    os.symlink(secret, volume / "Cours" / "lien_dehors")
    os.symlink("/etc", volume / "Cours" / "lien_etc")
    os.symlink(volume / "Musique", volume / "Cours" / "lien_dedans")
    listing = list_directory(str(volume), "Cours")
    names = {e.name for e in listing.entries}
    assert "lien_dehors" not in names and "lien_etc" not in names and "lien_dedans" in names
    assert listing.skipped_links == 2
    with pytest.raises(PathError) as exc:
        resolve_within(str(volume), "Cours/lien_dehors/pwd.mp4")
    assert exc.value.code == "outside_volume" and exc.value.status == 403
    assert resolve_within(str(volume), "Cours/lien_dedans").endswith("Musique")


def test_missing_and_non_directory(volume):
    with pytest.raises(PathError) as exc:
        list_directory(str(volume), "inexistant")
    assert exc.value.code == "not_found"
    with pytest.raises(PathError) as exc:
        list_directory(str(volume), "Cours/b.mp4")
    assert exc.value.code == "not_a_directory"


def test_walk_media_selection_recursive_bounded_and_deduplicated(volume, tmp_path):
    os.symlink(tmp_path, volume / "Cours" / "evil")
    result = walk_media(str(volume), ["Cours", "Cours/b.mp4"], {"video"})
    rels = [r[0] for r in result.files]
    assert rels == ["Cours/A.mkv", "Cours/b.mp4", "Cours/RPM/101.mp4"] and result.skipped == 1
    assert [r[3] for r in result.files] == ["video"] * 3
    assert [r[0] for r in walk_media(str(volume), ["Musique"], {"audio"}).files] == ["Musique/t1.flac"]
    with pytest.raises(PathError):
        walk_media(str(volume), ["../.."], {"video"})


def test_walk_media_file_cap(volume, monkeypatch):
    monkeypatch.setattr(paths, "MAX_WALK_FILES", 2)
    result = walk_media(str(volume), ["Cours"], {"video", "audio"})
    assert result.truncated and len(result.files) == 2


def test_extension_sets_match_the_importers():
    from app.utils.audio_importer import AUDIO_EXTENSIONS as AUDIO_COURSE
    from app.utils.importer import IMAGE_EXTENSIONS, SUPPORTED_EXTENSIONS
    from app.utils.radio_utils import AUDIO_EXTENSIONS as RADIO

    assert paths.VIDEO_EXTENSIONS == SUPPORTED_EXTENSIONS
    assert paths.AUDIO_EXTENSIONS == (RADIO | AUDIO_COURSE) - {".mp4", ".webm"}
    assert paths.IMAGE_EXTENSIONS == IMAGE_EXTENSIONS


def test_ensure_dir_within_creates_only_inside(volume, tmp_path):
    target = paths.ensure_dir_within(str(volume), "Export/Bobine/2026")
    assert os.path.isdir(target) and paths.inside(str(volume), target)
    os.symlink(tmp_path, volume / "evil")
    with pytest.raises(PathError):
        paths.ensure_dir_within(str(volume), "evil/dedans")
    with pytest.raises(PathError):
        paths.ensure_dir_within(str(volume), "../dehors")


def test_unique_dest_never_overwrites(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"1")
    (tmp_path / "a (2).mp4").write_bytes(b"2")
    assert paths.unique_dest(str(tmp_path), "a.mp4").endswith("a (3).mp4")
    assert paths.safe_dest_name("../../a:b*c?.mp4") == "abc.mp4"
    assert "/" not in paths.safe_dest_name("x/y\\z") and ":" not in paths.safe_dest_name("a:b")
