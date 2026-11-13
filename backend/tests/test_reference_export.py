import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_published_reference_matches_the_code():
    result = subprocess.run([sys.executable, str(REPO / "scripts" / "export_reference.py"), "--check"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
