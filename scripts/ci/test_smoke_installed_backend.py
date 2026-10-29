"""Le script de fumée du backend installé doit réussir sur un backend sain et échouer sinon (sinon le job CI ne prouve rien)."""
import os
import socket
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SMOKE = Path(__file__).with_name("smoke-installed-backend.sh")

HEALTHY = """\
    import http.server, os
    assert os.environ["BOBINE_USE_XDG"] == "1" and os.environ["XDG_DATA_HOME"].startswith(os.environ["HOME"].rsplit("/", 1)[0])
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200 if self.path == "/api/health" else 404)
            self.end_headers()
            self.wfile.write(b"{}")
        def log_message(self, *args):
            pass
    http.server.HTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
"""
UNHEALTHY = """\
    import http.server
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(503)
            self.end_headers()
        def log_message(self, *args):
            pass
    http.server.HTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
"""
EXITS = "    raise SystemExit(0)\n"


def port_8000_is_free() -> bool:
    with socket.socket() as probe:
        return probe.connect_ex(("127.0.0.1", 8000)) != 0


@unittest.skipUnless(sys.platform.startswith("linux") and port_8000_is_free(), "Linux et port 8000 libre requis")
class SmokeInstalledBackendTests(unittest.TestCase):
    def run_smoke(self, body: str, attempts: int = 8) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            backend = Path(tmp) / "BobineBackend"
            backend.write_text(f"#!{sys.executable}\n" + textwrap.dedent(body))
            backend.chmod(backend.stat().st_mode | stat.S_IXUSR)
            env = dict(os.environ, BOBINE_SMOKE_ATTEMPTS=str(attempts))
            return subprocess.run(["bash", str(SMOKE), str(backend)], env=env, capture_output=True, text=True, timeout=120)

    def test_healthy_backend_passes(self):
        result = self.run_smoke(HEALTHY)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("opérationnel", result.stdout)

    def test_backend_that_exits_fails(self):
        result = self.run_smoke(EXITS)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("s'est arrêté", result.stderr)

    def test_backend_without_http_200_fails(self):
        result = self.run_smoke(UNHEALTHY, attempts=3)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("503", result.stderr)

    def test_missing_executable_fails(self):
        result = subprocess.run(["bash", str(SMOKE), "/nonexistent/BobineBackend"], capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)

    def test_busy_port_is_refused(self):
        with socket.socket() as occupant:
            occupant.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            occupant.bind(("127.0.0.1", 8000))
            occupant.listen()
            result = self.run_smoke(HEALTHY)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("occupé", result.stderr)


if __name__ == "__main__":
    unittest.main()
