"""Contrôle le contrat du dispatch sans réseau ni identifiant réel."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('notify-web-release.sh')
SHA = 'a' * 40


class NotificationTest(unittest.TestCase):
    def run_script(self, **values):
        env = os.environ.copy()
        env.pop('BOBINE_WEB_DISPATCH_TOKEN', None)
        env.update(RELEASE_CHANNEL='stable', RELEASE_SHA=SHA)
        env.update(values)
        return subprocess.run(['bash', str(SCRIPT)], env=env, text=True, capture_output=True)

    def test_missing_token_warns_without_blocking_release(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('::warning::', result.stdout)
        self.assertNotIn('transmise', result.stdout)

    def test_invalid_channel_or_revision_never_dispatches(self):
        for values in ({'RELEASE_CHANNEL': 'other'}, {'RELEASE_SHA': 'main'}, {'RELEASE_SHA': SHA + '\n'}):
            result = self.run_script(**values)
            self.assertNotEqual(result.returncode, 0)

    def test_exact_destination_and_payload_for_all_channels(self):
        with tempfile.TemporaryDirectory(prefix='bobine-dispatch-') as folder:
            root = Path(folder)
            curl = root / 'curl'
            curl.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args=sys.argv[1:]
assert args[-1]=='https://api.github.com/repos/FantasmaGlad/BobineWeb/dispatches'
assert 'Authorization: Bearer fixture-dispatch-token' in args
Path(os.environ['DISPATCH_FIXTURE']).write_text(args[args.index('--data')+1])
''')
            curl.chmod(0o700)
            for channel in ('stable', 'beta', 'canary'):
                result = self.run_script(RELEASE_CHANNEL=channel, BOBINE_WEB_DISPATCH_TOKEN='fixture-dispatch-token', PATH=folder+os.pathsep+os.environ['PATH'], DISPATCH_FIXTURE=str(root/'payload.json'))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn('fixture-dispatch-token', result.stdout+result.stderr)
                self.assertEqual(json.loads((root/'payload.json').read_text()), {'event_type':'bobine-release','client_payload':{'repository':'FantasmaGlad/Bobine','channel':channel,'sha':SHA}})


if __name__ == '__main__':
    unittest.main()
