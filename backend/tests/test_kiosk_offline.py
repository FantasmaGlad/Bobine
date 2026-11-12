from pathlib import Path

from app.desktop.chromium import OFFLINE_FLAGS
from app.desktop.displays import Monitor, build_projector_command

INSTALL_SH = Path(__file__).resolve().parents[2] / "install.sh"


def test_projector_kiosk_never_calls_vendor_services():
    command = build_projector_command("chromium", "http://127.0.0.1:1903/kiosk", Monitor("HDMI-1", 0, 0, 1920, 1080), "/tmp/p")
    assert set(OFFLINE_FLAGS) <= set(command)


def test_appliance_kiosk_uses_the_same_flags():
    script = INSTALL_SH.read_text(encoding="utf-8")
    assert all(flag in script for flag in OFFLINE_FLAGS)
