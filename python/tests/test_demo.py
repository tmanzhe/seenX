"""The documented demo must work in a new process without personal inputs."""

from importlib.util import find_spec
import subprocess
import sys
import unittest


class DemoTests(unittest.TestCase):
    @unittest.skipUnless(find_spec("mcp") is not None, 'Install the optional "mcp" extra for the demo')
    def test_offline_demo_exercises_real_mcp_and_saved_pixels(self):
        result = subprocess.run([sys.executable, "-B", "-m", "seenx.demo"],
                                capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Payload crop: schema=1; PNG=30x32; pixels verified", result.stdout)
        self.assertIn("Payload full: schema=1; PNG=100x80; pixels verified", result.stdout)
        self.assertIn("After grant revoke: access_denied", result.stdout)
        self.assertIn("PASS: offline demo", result.stdout)
