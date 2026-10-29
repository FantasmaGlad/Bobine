import importlib.util
import io
import struct
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("check_elf_alignment", Path(__file__).with_name("check-elf-alignment.py"))
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def elf64(*aligns, loads_only=True):
    header = bytearray(64)
    header[:7] = b"\x7fELF\x02\x01\x01"
    struct.pack_into("<Q", header, 0x20, 64)
    struct.pack_into("<HH", header, 0x36, 56, len(aligns) + 1)
    body = struct.pack("<IIQQQQQQ", 6, 0, 0, 0, 0, 0, 0, 8)  # PT_PHDR : ignoré
    for align in aligns:
        body += struct.pack("<IIQQQQQQ", 1, 5, 0, 0, 0, 0, 0, align)
    return bytes(header) + body


def elf32(*aligns):
    header = bytearray(52)
    header[:7] = b"\x7fELF\x01\x01\x01"
    struct.pack_into("<I", header, 0x1C, 52)
    struct.pack_into("<HH", header, 0x2A, 32, len(aligns))
    body = b"".join(struct.pack("<IIIIIIII", 1, 0, 0, 0, 0, 0, 5, align) for align in aligns)
    return bytes(header) + body


def run(argv):
    out = io.StringIO()
    with redirect_stdout(out):
        code = checker.main(argv)
    return code, out.getvalue()


class AlignmentTests(unittest.TestCase):
    def test_alignements_lus_sur_elf64_et_elf32(self):
        self.assertEqual(checker.load_alignments(elf64(16384, 65536)), [16384, 65536])
        self.assertEqual(checker.load_alignments(elf32(4096)), [4096])

    def test_seuil_16_kio(self):
        self.assertTrue(checker.is_aligned([16384, 65536]))
        self.assertFalse(checker.is_aligned([16384, 4096]))
        self.assertFalse(checker.is_aligned([20000]))

    def test_fichier_invalide(self):
        for data in (b"MZ", elf64()[:10] + b"\x03" + elf64()[11:]):
            with self.assertRaises((ValueError, struct.error)):
                checker.load_alignments(data)

    def make_apk(self, libs):
        path = Path(self.tmp.name) / "app.apk"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("classes.dex", b"dex")
            for name, data in libs.items():
                archive.writestr(name, data)
        return path

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_apk_arm64_aligne_passe(self):
        apk = self.make_apk({
            "lib/arm64-v8a/libpython3.13.so": elf64(16384),
            "lib/arm64-v8a/libffmpeg.so": elf64(65536),
            "lib/arm64-v8a/libffprobe.so": elf64(16384),
        })
        code, out = run(["--apk", str(apk)])
        self.assertEqual(code, 0, out)
        self.assertEqual(out.count("alignés sur 16 Kio"), 3)

    def test_apk_arm64_une_bibliotheque_4_kio_echoue_et_est_nommee(self):
        apk = self.make_apk({"lib/arm64-v8a/libffmpeg.so": elf64(4096), "lib/arm64-v8a/libffprobe.so": elf64(16384)})
        code, out = run(["--apk", str(apk)])
        self.assertEqual(code, 1)
        self.assertIn("arm64-v8a/libffmpeg.so", out)
        self.assertIn("4096", out)

    def test_abi_32_bits_et_emulateur_sont_signalees_sans_echec(self):
        apk = self.make_apk({
            "lib/arm64-v8a/libffmpeg.so": elf64(16384),
            "lib/armeabi-v7a/libffmpeg.so": elf32(4096),
            "lib/x86_64/libpython3.13.so": elf64(4096),
        })
        code, out = run(["--apk", str(apk)])
        self.assertEqual(code, 0, out)
        self.assertIn("::notice::armeabi-v7a/libffmpeg.so", out)
        code, _ = run(["--apk", str(apk), "--enforce-abi", "arm64-v8a", "--enforce-abi", "x86_64"])
        self.assertEqual(code, 1)

    def test_apk_sans_bibliotheque_echoue(self):
        self.assertEqual(run(["--apk", str(self.make_apk({}))])[0], 1)

    def test_dossier_jnilibs(self):
        root = Path(self.tmp.name) / "jniLibs"
        (root / "arm64-v8a").mkdir(parents=True)
        (root / "arm64-v8a" / "libbobine_media.so").write_bytes(elf64(16384))
        self.assertEqual(run(["--dir", str(root)])[0], 0)
        (root / "arm64-v8a" / "libffmpeg.so").write_bytes(elf64(4096))
        self.assertEqual(run(["--dir", str(root)])[0], 1)


if __name__ == "__main__":
    unittest.main()
