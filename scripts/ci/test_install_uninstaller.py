import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

INSTALL_SH = Path(__file__).resolve().parents[2] / "install.sh"
FUNCTION = re.compile(r"^step_uninstaller\(\) \{\n.*?^\}\n", re.S | re.M)
STUBS = 'step() { :; }\nok() { :; }\nstep_done() { :; }\nrun() { :; }\nwrite_file() { cat >"$OUT"; }\n'


class UninstallerQuotingTest(unittest.TestCase):
    def test_repository_path_survives_spaces_and_shell_syntax(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            repo = str(work / "Projet Bobine;$(touch pwned)")
            out = work / "bobine-uninstall"
            (work / "bin").mkdir()
            fake = work / "bin" / "systemd-run"
            fake.write_text('#!/bin/sh\nfor arg in "$@"; do printf "%s\\n" "$arg"; done\n')
            fake.chmod(0o755)
            body = FUNCTION.search(INSTALL_SH.read_text(encoding="utf-8")).group(0)
            env = {**os.environ, "OUT": str(out), "REPO_DIR": repo, "PATH": f"{work / 'bin'}:{os.environ['PATH']}"}
            subprocess.run(["bash", "-c", f"set -euo pipefail\n{STUBS}{body}step_uninstaller"], env=env, check=True)
            args = subprocess.run(["bash", str(out)], env=env, cwd=work, check=True,
                                  capture_output=True, text=True).stdout.splitlines()
            self.assertIn(f"{repo}/install.sh", args)
            self.assertFalse((work / "pwned").exists())


if __name__ == "__main__":
    unittest.main()
