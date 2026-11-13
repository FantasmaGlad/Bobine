import base64
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packaging" / "common"))

from dearmor import dearmor  # noqa: E402

PRIMARY = "B77D96D72F84F36ACAA3F8729CBF497D829EE15A"
KEYRING = ROOT / "packaging" / "linux" / "keyring"


def _packets(data: bytes):
    i = 0
    while i < len(data):
        head = data[i]
        if head & 0x40:
            tag, first = head & 0x3F, data[i + 1]
            if first < 192:
                length, i = first, i + 2
            elif first < 224:
                length, i = ((first - 192) << 8) + data[i + 2] + 192, i + 3
            else:
                length, i = int.from_bytes(data[i + 2:i + 6], "big"), i + 6
        else:
            tag, size = (head >> 2) & 0x0F, [1, 2, 4][head & 3]
            length, i = int.from_bytes(data[i + 1:i + 1 + size], "big"), i + 1 + size
        yield tag, data[i:i + length]
        i += length


def _rsa_modulus(body: bytes) -> bytes:
    assert body[0] == 4 and body[5] == 1
    bits = int.from_bytes(body[6:8], "big")
    return body[8:8 + (bits + 7) // 8]


def _fingerprint(body: bytes) -> str:
    return hashlib.sha1(b"\x99" + len(body).to_bytes(2, "big") + body).hexdigest().upper()


def _certificate():
    return list(_packets(dearmor((KEYRING / "bobine.asc").read_text(encoding="ascii"))))


def test_bundled_key_is_the_pinned_primary():
    primaries = [body for tag, body in _certificate() if tag == 6]
    assert [_fingerprint(body) for body in primaries] == [PRIMARY]


def test_install_ps1_accepts_exactly_the_bundled_subkeys():
    subkeys = {base64.b64encode(_rsa_modulus(body)).decode() for tag, body in _certificate() if tag == 14}
    script = (ROOT / "packaging" / "windows" / "install.ps1").read_text(encoding="utf-8")
    block = re.search(r"\$SigningKeyModuli = @\((.*?)\)", script, re.S).group(1)
    assert set(re.findall(r"'([A-Za-z0-9+/=]+)'", block)) == subkeys


def test_refresh_script_and_packages_use_the_same_primary():
    refresh = (KEYRING / "refresh-release-keyring").read_text(encoding="utf-8")
    assert f"PRIMARY={PRIMARY}" in refresh
    for hook in ("packaging/linux/DEBIAN/postinst", "packaging/rpm/bobine.spec", "packaging/arch/bobine.install"):
        assert "/usr/lib/bobine/refresh-release-keyring" in (ROOT / hook).read_text(encoding="utf-8"), hook
