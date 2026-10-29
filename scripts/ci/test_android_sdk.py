"""Offline failure cases for SDK acquisition; never touches an installed SDK."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import zipfile

SPEC = importlib.util.spec_from_file_location("android_sdk", Path(__file__).with_name("setup-android-sdk.py"))
sdk = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sdk)


def archive(entries=None):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as z:
        for name, body in (entries or {"android-ndk-r28c/source.properties": "Pkg.Revision = 28.2.13676358\n"}).items():
            z.writestr(name, body)
    return output.getvalue()


def specification(data):
    return {"archive": "android-ndk-r28c-linux.zip", "directory": "android-ndk-r28c",
            "version": "28.2.13676358", "sha1": hashlib.sha1(data).hexdigest(), "size": len(data)}


def ndk_tree(root):
    root.mkdir(parents=True)
    (root / "source.properties").write_text("Pkg.Revision = 28.2.13676358\n")
    tools = root / "toolchains/llvm/prebuilt/linux-x86_64/bin"
    tools.mkdir(parents=True)
    for tool in ("clang", "llvm-readelf", "llvm-strip", "aarch64-linux-android34-clang", "armv7a-linux-androideabi34-clang"):
        (tools / tool).write_text("tool")
        (tools / tool).chmod(0o755)


class AndroidSdkTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="bobine sdk test ")
        self.root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)

    def test_pinned_config_is_valid(self):
        config = sdk.read_config(sdk.DEFAULT_CONFIG)
        self.assertEqual(config["compile_sdk"], 37)
        self.assertEqual(config["target_sdk"], 36)
        self.assertEqual(config["platform"], "android-37.0")
        self.assertEqual(config["min_sdk"], 34)

    def test_config_rejects_url_or_path_in_archive(self):
        config = json.loads(sdk.DEFAULT_CONFIG.read_text())
        config["ndk"]["archive"] = "../../other.zip"
        path = self.root / "toolchain.json"
        path.write_text(json.dumps(config))
        with self.assertRaises(ValueError):
            sdk.read_config(path)

    def test_complete_ndk_is_reused_without_network(self):
        target = self.root / "ndk/28.2.13676358"
        ndk_tree(target)
        with patch.object(sdk.subprocess, "run"), patch.object(sdk, "download_archive") as download:
            self.assertEqual(sdk.ensure_ndk(self.root, specification(archive())), target)
        download.assert_not_called()

    def test_properties_alone_do_not_prove_an_installation(self):
        target = self.root / "ndk/28.2.13676358"
        target.mkdir(parents=True)
        (target / "source.properties").write_text("Pkg.Revision = 28.2.13676358\n")
        with self.assertRaisesRegex(ValueError, "tool missing"):
            sdk.ensure_ndk(self.root, specification(archive()), check_only=True)

    def test_wrong_revision_is_rejected(self):
        ndk_tree(self.root / "ndk")
        with self.assertRaisesRegex(ValueError, "revision differs"):
            sdk.validate_ndk(self.root / "ndk", "27.0.0")

    def test_broken_executable_is_rejected(self):
        ndk_tree(self.root / "ndk")
        with patch.object(sdk.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "clang")):
            with self.assertRaises(subprocess.CalledProcessError):
                sdk.validate_ndk(self.root / "ndk", "28.2.13676358")

    def test_truncated_download_is_retried_and_verified(self):
        data = archive()
        with patch.object(sdk.urllib.request, "urlopen", side_effect=[io.BytesIO(data[:5]), io.BytesIO(data)]) as request, patch.object(sdk.time, "sleep"):
            sdk.download_archive(specification(data), self.root / "ndk.zip")
        self.assertEqual(request.call_count, 2)
        self.assertEqual((self.root / "ndk.zip").read_bytes(), data)

    def test_same_size_wrong_checksum_never_passes(self):
        data = archive()
        with patch.object(sdk.urllib.request, "urlopen", side_effect=lambda *a, **kw: io.BytesIO(b"x" * len(data))), patch.object(sdk.time, "sleep"):
            with self.assertRaisesRegex(ValueError, "checksum"):
                sdk.download_archive(specification(data), self.root / "ndk.zip", attempts=2)

    def test_invalid_zip_with_matching_digest_never_passes(self):
        data = b"this is not a zip"
        with patch.object(sdk.urllib.request, "urlopen", side_effect=lambda *a, **kw: io.BytesIO(data)), patch.object(sdk.time, "sleep"):
            with self.assertRaises(zipfile.BadZipFile):
                sdk.download_archive(specification(data), self.root / "ndk.zip", attempts=2)

    def test_permanent_http_error_is_not_retried(self):
        error = urllib.error.HTTPError("https://dl.google.com/", 404, "missing", {}, None)
        self.addCleanup(error.close)
        with patch.object(sdk.urllib.request, "urlopen", side_effect=error) as request:
            with self.assertRaises(urllib.error.HTTPError):
                sdk.download_archive(specification(archive()), self.root / "ndk.zip")
        self.assertEqual(request.call_count, 1)

    def test_disk_full_is_not_retried(self):
        with patch.object(sdk.urllib.request, "urlopen", side_effect=OSError(28, "full")) as request:
            with self.assertRaises(OSError):
                sdk.download_archive(specification(archive()), self.root / "ndk.zip")
        self.assertEqual(request.call_count, 1)

    def test_archive_cannot_escape_its_root(self):
        for name in ("../escape", "/escape", "android-ndk-r28c/../escape", "different-root/file"):
            with self.subTest(name=name):
                source = self.root / "input.zip"
                source.write_bytes(archive({name: "x"}))
                with self.assertRaises(ValueError):
                    sdk.extract_archive(source, self.root / "extraction", "android-ndk-r28c")

    def test_executable_permissions_and_safe_symlinks_are_preserved(self):
        source = self.root / "input.zip"
        with zipfile.ZipFile(source, "w") as z:
            binary = zipfile.ZipInfo("android-ndk-r28c/bin/clang")
            binary.external_attr = (stat.S_IFREG | 0o755) << 16
            z.writestr(binary, b"binary")
            link = zipfile.ZipInfo("android-ndk-r28c/bin/clang++")
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(link, "clang")
        result = sdk.extract_archive(source, self.root / "out", "android-ndk-r28c")
        self.assertTrue((result / "bin/clang").stat().st_mode & stat.S_IXUSR)
        self.assertTrue((result / "bin/clang++").is_symlink())
        self.assertEqual((result / "bin/clang++").read_bytes(), b"binary")

    def test_symlink_cannot_escape_the_installed_ndk(self):
        source = self.root / "input.zip"
        with zipfile.ZipFile(source, "w") as z:
            link = zipfile.ZipInfo("android-ndk-r28c/link")
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(link, "../elsewhere")
        with self.assertRaises(ValueError):
            sdk.extract_archive(source, self.root / "out", "android-ndk-r28c")

    def test_unvalidated_download_never_replaces_existing_installation(self):
        target = self.root / "ndk/28.2.13676358"
        target.mkdir(parents=True)
        sentinel = target / "diagnostic"
        sentinel.write_text("keep")
        with patch.object(sdk, "download_archive", side_effect=ValueError("checksum")):
            with self.assertRaises(ValueError):
                sdk.ensure_ndk(self.root, specification(archive()))
        self.assertEqual(sentinel.read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
