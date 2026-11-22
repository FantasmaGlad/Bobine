import subprocess
import sys
from pathlib import Path

from app.inputs import bindings

REPO = Path(__file__).resolve().parents[2]


def test_generated_frontend_table_is_up_to_date():
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "generators" / "sync_remote_bindings.py"), "--check"], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_every_binding_names_known_actions_without_repeats():
    for source, chain in bindings.DEFAULT_BINDINGS.items():
        assert chain, source
        assert len(set(chain)) == len(chain), source
        assert set(chain) <= set(bindings.REMOTE_ACTIONS), source


def test_gamepad_directions_and_triggers_are_bound_buttons():
    pads = {int(source.split(":")[1]) for source in bindings.DEFAULT_BINDINGS if source.startswith("pad:")}
    assert set(bindings.GAMEPAD_DIRECTIONS) <= pads
    assert set(bindings.ANALOG_TRIGGERS) <= pads
    for button, action in bindings.GAMEPAD_DIRECTIONS.items():
        assert bindings.DEFAULT_BINDINGS[f"pad:{button}"] == (action,)
