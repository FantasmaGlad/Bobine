"""Exercise AAB verification with actual JDK signatures and archive corruption."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

SPEC = importlib.util.spec_from_file_location("android_bundles", Path(__file__).with_name("verify-android-bundles.py"))
bundles = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bundles)


@unittest.skipUnless(shutil.which("keytool") and shutil.which("jarsigner"), "JDK signing tools required")
class BundleSignatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="bobine-aab-signature-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.keystore = cls.root / "test.p12"
        # Disposable fixture key, never used to build or sign a Bobine release.
        subprocess.run(["keytool", "-genkeypair", "-alias", "test", "-keyalg", "RSA", "-keysize", "2048",
                        "-dname", "CN=Bundle Test", "-validity", "1", "-keystore", str(cls.keystore),
                        "-storepass", "fixture-only", "-keypass", "fixture-only"],
                       check=True, capture_output=True)
        cls.original = cls.root / "signed.aab"
        with zipfile.ZipFile(cls.original, "w") as archive:
            archive.writestr("base/manifest/AndroidManifest.xml", b"fixture")
            for name in ("libpython3.13.so", "libffmpeg.so", "libffprobe.so", "libbobine_media.so"):
                archive.writestr("base/lib/arm64-v8a/" + name, b"fixture")
        subprocess.run(["jarsigner", "-keystore", str(cls.keystore), "-storepass", "fixture-only",
                        str(cls.original), "test"], check=True, capture_output=True)

    def copy_bundle(self, name):
        path = self.root / name
        shutil.copyfile(self.original, path)
        return path

    def test_self_signed_upload_certificate_is_accepted(self):
        bundles.verify(self.original, tv=False)

    def test_wrong_abi_set_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unexpected ABI"):
            bundles.verify(self.original, tv=True)

    def test_added_unsigned_entry_is_rejected(self):
        path = self.copy_bundle("unsigned-entry.aab")
        with zipfile.ZipFile(path, "a") as archive:
            archive.writestr("base/assets/added-after-signing", b"unsigned")
        with self.assertRaisesRegex(ValueError, "signed entry coverage"):
            bundles.verify(path, tv=False)

    def test_duplicate_entries_are_rejected(self):
        import warnings
        path = self.copy_bundle("duplicate-entry.aab")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(path, "a") as archive:
                archive.writestr("base/lib/arm64-v8a/libffmpeg.so", b"fixture")
        with self.assertRaisesRegex(ValueError, "Duplicate ZIP entries"):
            bundles.verify(path, tv=False)

    def test_modified_signed_entry_is_rejected(self):
        path = self.root / "tampered.aab"
        with zipfile.ZipFile(self.original) as source, zipfile.ZipFile(path, "w") as target:
            for name in source.namelist():
                data = b"tampered" if name.endswith("libbobine_media.so") else source.read(name)
                target.writestr(name, data)
        with self.assertRaisesRegex(ValueError, "signature"):
            bundles.verify(path, tv=False)
