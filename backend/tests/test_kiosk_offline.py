from app.desktop.chromium import OFFLINE_FLAGS
from app.desktop.monitors import Monitor
from app.desktop.projector import build_projector_command

def test_projector_kiosk_never_calls_vendor_services():
    command = build_projector_command("chromium", "http://127.0.0.1:1903/kiosk", Monitor("HDMI-1", 0, 0, 1920, 1080), "/tmp/p")
    assert set(OFFLINE_FLAGS) <= set(command)

