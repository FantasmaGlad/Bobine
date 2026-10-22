"""The license gate for the bobine-media dependency graph."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def checker():
    spec = importlib.util.spec_from_file_location("check_media_licenses", ROOT / "scripts" / "ci" / "check-media-licenses.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("expression", [
    "MIT", "MIT OR Apache-2.0", "Unlicense OR MIT", "0BSD OR MIT OR Apache-2.0",
    "(MIT OR Apache-2.0) AND Unicode-3.0", "MIT/Apache-2.0", "GPL-3.0-only OR MIT",
])
def test_permissive_expressions_are_accepted(checker, expression):
    assert checker.satisfied(expression)


@pytest.mark.parametrize("expression", [
    "GPL-3.0-only", "MIT AND GPL-3.0-only", "(MIT OR Apache-2.0) AND SSPL-1.0", "Proprietary",
])
def test_restrictive_or_unknown_expressions_are_rejected(checker, expression):
    assert not checker.satisfied(expression)


@pytest.mark.parametrize("expression", ["", "MIT OR", "(MIT", "MIT)", "AND MIT"])
def test_malformed_expressions_are_errors_not_silent_passes(checker, expression):
    with pytest.raises(ValueError):
        checker.satisfied(expression)
