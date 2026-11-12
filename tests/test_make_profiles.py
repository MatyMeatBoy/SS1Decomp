"""Check the user-facing profile dispatch without compiling or reading a ROM."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAKE = shutil.which('make')


@unittest.skipUnless(MAKE, 'GNU make is required for profile-dispatch checks')
class MakeProfiles(unittest.TestCase):
    def dry(self, *args):
        return subprocess.run([MAKE, '-n', *args], cwd=ROOT, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_default_compare_is_europe(self):
        result = self.dry('compare')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('eu_build.py', result.stdout)
        self.assertIn('baserom_eu.gba', result.stdout)
        self.assertNotIn('sha1sum -c shiningsoul.sha1', result.stdout)

    def test_usa_remains_explicit_and_uses_original_hash_gate(self):
        result = self.dry('REGION=us', '-o', 'baserom.gba', 'compare')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('sha1sum -c shiningsoul.sha1', result.stdout)
        self.assertNotIn('eu_build.py', result.stdout)

    def test_unknown_region_is_not_silently_accepted(self):
        result = self.dry('REGION=unknown', 'compare')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Unsupported REGION', result.stderr)


if __name__ == '__main__':
    unittest.main()
